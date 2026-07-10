import httpx, json, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://127.0.0.1:8000"

tests = [
    {
        "label": "SEBI official circular (sebi.gov.in)",
        "payload": {
            "raw_input": "https://www.sebi.gov.in/enforcement/recovery-proceedings/jul-2026/completion-of-recovery-certificate-no-9106-of-2026-dated-may-8-2026-issued-to-amit-agarwal-pan-aeepa5456l-defaulter-in-the-matter-of-dealing-in-illiquid-stock-options-on-bse-_102772.html",
            "claimed_source": "SEBI"
        }
    },
    {
        "label": "ICICI Prudential mutual fund statement",
        "payload": {
            "raw_input": "Dear Investor, Greetings from ICICI Prudential Mutual Fund! Pursuant to SEBI circular, please find your account statement. For details visit https://www.icicipruamc.com. Never share your OTP or password.",
            "claimed_source": "ICICI Prudential Mutual Fund"
        }
    },
    {
        "label": "Legitimate broker email",
        "payload": {
            "raw_input": "Reminder from your broker: Your monthly account statement is now available. Log in at https://groww.in to view it. We never ask for your OTP or password.",
            "claimed_source": "Groww"
        }
    },
    {
        "label": "Phishing with fake SEBI domain",
        "payload": {
            "raw_input": "URGENT: Your SEBI account has been suspended due to suspicious activity. Share OTP immediately at http://sebi-verify.xyz/login to avoid permanent freeze.",
            "claimed_source": "SEBI"
        }
    },
]

for test in tests:
    print(f"\n{'='*60}")
    print(f"TEST: {test['label']}")
    print(f"{'='*60}")
    try:
        resp = httpx.post(f"{BASE}/api/analyze/text", json=test["payload"], timeout=180)
        if resp.status_code == 200:
            d = resp.json()
            risk = d["risk_score"]
            level = d["risk_level"]
            status = "✅ PASS" if (level == "low" and "phish" not in test["label"].lower()) or (level in ("medium","high") and "fake" in test["label"].lower()) else "❌ WRONG"
            print(f"  Risk: {risk}/{level}  {status}")
            print(f"  Threat: {d['threat_label']}")
            print(f"  Confidence: {d['confidence']}")
            print(f"  Latency: {d['latency_ms']}ms")
            print(f"  Summary: {d['summary'][:200]}")
        else:
            print(f"  HTTP {resp.status_code}: {resp.text[:300]}")
    except Exception as e:
        print(f"  FAILED: {e}")
