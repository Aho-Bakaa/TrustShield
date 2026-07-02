"""Evaluation harness for the TrustShield demo set.

Runs the full trust pipeline over labeled examples and reports:
  - per-channel + overall precision / recall / accuracy (flag = MEDIUM|HIGH)
  - authenticity-check accuracy on 'legit' items
  - latency (avg) and % escalated to deep analysis

Runs OFFLINE by default (NETWORK_ENABLED=false) for speed/determinism. Set
NETWORK_ENABLED=true to exercise live rendering.

Usage (from backend/):
    .venv/Scripts/python.exe -m eval.run_eval
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("NETWORK_ENABLED", "false")  # render off for speed/determinism
# Force rule-based (no LLM) with:  set TS_EVAL_MOCK=1
if os.environ.get("TS_EVAL_MOCK"):
    os.environ["FORCE_MOCK_LLM"] = "true"

# Ensure `app` package importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.fusion import analyze  # noqa: E402
from app.intake import build_request  # noqa: E402
from app.llm import llm_status  # noqa: E402
from app.schemas import ChannelType, RiskLevel  # noqa: E402

HERE = Path(__file__).resolve().parent


def _flagged(result) -> bool:
    return result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)


def _metrics(rows: list[dict]) -> dict:
    tp = sum(1 for r in rows if r["truth"] and r["pred"])
    fp = sum(1 for r in rows if not r["truth"] and r["pred"])
    fn = sum(1 for r in rows if r["truth"] and not r["pred"])
    tn = sum(1 for r in rows if not r["truth"] and not r["pred"])
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    acc = (tp + tn) / len(rows) if rows else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"n": len(rows), "precision": round(prec, 3), "recall": round(rec, 3),
            "f1": round(f1, 3), "accuracy": round(acc, 3), "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def run() -> None:
    data = json.loads((HERE / "demo_dataset.json").read_text(encoding="utf-8"))
    items = data["items"]

    audio_labels_path = HERE.parent / "app" / "data" / "demo_dataset" / "audio" / "labels.json"
    audio_items = []
    if audio_labels_path.exists():
        audio_items = json.loads(audio_labels_path.read_text(encoding="utf-8"))

    rows: list[dict] = []
    latencies: list[int] = []
    escalated = 0
    auth_rows: list[dict] = []

    st = llm_status()
    print(f"\nReasoning mode: {st['mode']}  ({st['provider']} · {st['model']})")

    print("\n== Per-item results ==")
    print(f"{'id':<14}{'channel':<9}{'truth':<10}{'risk':<6}{'level':<8}{'esc':<5}pred")

    for it in items:
        req = build_request(
            text=it["text"],
            channel_hint=ChannelType(it["expected_channel"]) if it.get("expected_channel") else None,
            claimed_source=it.get("claimed_source"),
        )
        res = analyze(req)
        truth = it["label"] == "malicious"
        pred = _flagged(res)
        rows.append({"channel": res.channel_type.value, "truth": truth, "pred": pred})
        latencies.append(res.latency_ms)
        escalated += 1 if res.escalated else 0
        if it["label"] == "legit":
            # For legit items, authenticity should recognise official sources when present.
            auth_rows.append({"id": it["id"], "official": res.authenticity.is_official_source,
                              "conf": res.authenticity.official_confidence})
        ok = "OK " if truth == pred else "XX "
        print(f"{it['id']:<14}{res.channel_type.value:<9}{it['label']:<10}"
              f"{res.risk_score:<6}{res.risk_level.value:<8}{'Y' if res.escalated else 'n':<5}{ok}")

    for a in audio_items:
        req = build_request(audio_path=a["file"], channel_hint=ChannelType.AUDIO,
                            original_filename=Path(a["file"]).name)
        res = analyze(req)
        truth = a["label"] == "malicious"
        pred = _flagged(res)
        rows.append({"channel": "audio", "truth": truth, "pred": pred})
        latencies.append(res.latency_ms)
        escalated += 1 if res.escalated else 0
        ok = "OK " if truth == pred else "XX "
        print(f"{a['id']:<14}{'audio':<9}{a['label']:<10}"
              f"{res.risk_score:<6}{res.risk_level.value:<8}{'Y' if res.escalated else 'n':<5}{ok}")

    total = rows
    print("\n== Metrics by channel ==")
    for ch in sorted({r["channel"] for r in total}):
        sub = [r for r in total if r["channel"] == ch]
        print(f"  {ch:<8} {_metrics(sub)}")
    print("\n== Overall ==")
    print(f"  detection {_metrics(total)}")

    if auth_rows:
        recognised = sum(1 for a in auth_rows if a["official"])
        print(f"\n== Authenticity (legit items with an official source) ==")
        print(f"  {recognised}/{len(auth_rows)} legit items recognised as official/verified source")

    print("\n== Operational ==")
    print(f"  items: {len(total)}")
    print(f"  avg latency: {round(sum(latencies)/len(latencies))} ms")
    print(f"  escalated to deep analysis: {escalated}/{len(total)} ({round(100*escalated/len(total))}%)")
    print(f"  network/render: {'ON' if os.environ.get('NETWORK_ENABLED')=='true' else 'OFF (offline eval)'}")


if __name__ == "__main__":
    run()
