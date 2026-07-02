# 🛡️ TrustShield — Multimodal Trust Layer for Securities-Market Communications

> **Detecting AI-generated threats in securities markets.**
> TrustShield helps retail investors and intermediaries detect AI-generated **phishing**,
> **synthetic-voice impersonation**, and **social-media manipulation**, and — the other half
> of the problem — **verify whether a purportedly official communication is genuine**.

A single trust pipeline ingests suspicious content from multiple channels, runs
modality-specific detectors, produces an **interpretable risk score**, and returns an
**action-oriented verdict**: *"Likely phishing"*, *"Suspected synthetic voice"*,
*"Social-media manipulation"*, or *"Verified official communication"*.

---

## Why this matters (problem framing)

The threat is two-sided:

1. **Attack** — generative AI produces hyper-personalised phishing, cloned voices of
   executives/regulators, deepfakes, and coordinated social manipulation aimed at retail
   investors and market integrity.
2. **Verification gap** — investors have **no practical way to tell a genuine SEBI / exchange /
   broker message from a convincing fake.**

TrustShield is framed as **trust infrastructure**, not just a classifier: detection *and*
authentication in one explainable pipeline.

---

## Target users

| User | Promise |
|------|---------|
| **Retail / first-generation investor** *(primary)* | "Before you trust an email, clip, or market post, paste/upload it into TrustShield and get a risk verdict with reasons." |
| Broker / compliance analyst *(secondary)* | Triage console to flag suspicious inbound comms or viral manipulation. |
| Regulator / ecosystem *(vision)* | The same architecture extends into a shared trust layer across apps, brokers, and market institutions. |

---

## Channels covered (MVP)

- **A — Phishing**: email / message + URL, with **rendered-page reasoning** (Playwright).
- **C — Synthetic voice**: audio clip spoof detection + impersonation-class reasoning.
- **D — Social manipulation**: post/URL with **live-page rendering** + reasoning.
- **Screenshots / documents**: upload (or **paste with Ctrl+V**, or drag & drop) an **image or
  PDF** → a **vision model** transcribes it (PDFs use embedded text when present, scanned PDFs
  are rendered and read) → it runs through the same text pipeline.
- **Authenticity layer**: domain allowlist / provenance checks for legitimate comms.

### For any URL, the LLM + Playwright *are* the engine
A user-submitted URL / social post / audio clip **always** goes to deep analysis — Playwright
renders the page and the LLM judges the rendered DOM. Heuristics are a cheap prior for the
triage score and an input to the LLM, not the verdict. So a random benign site (e.g. a movie
site) is genuinely rendered and correctly returns **LOW** with real reasoning, while a rendered
credential-capture page returns **HIGH** — the scores differ because the analysis differs, not
because of a lookup table. (Email without a link stays triage-gated to save cost.)

---

## Architecture

```
                 ┌──────────── Intake ────────────┐
  paste / upload │ classify channel · extract URLs │
  ──────────────▶│ entities (SEBI/NSE/broker…)     │
                 └───────────────┬────────────────┘
                                 ▼
                     Preprocessing (URL features,
                     manipulation heuristics, NER)
                                 ▼
        ┌───────── Triage (cheap, no network) ─────────┐
        │  preliminary risk score per modality         │
        └───────────────┬──────────────────────────────┘
              escalate if risk ≥ θ  OR  high-value entity  OR  suspicious link
                                 ▼
   ┌──────────── Deep analysis (only when needed) ────────────┐
   │  Phishing: Playwright render → DOM/forms/redirects → LLM  │
   │  Social  : live-page render → manipulation reasoning → LLM│
   │  Voice   : signal-feature spoof proxy → LLM explanation   │
   └───────────────┬──────────────────────────────────────────┘
                    ▼                      ▼
             Authenticity layer     Trust Score Engine (fusion)
             (allowlist/provenance) ──▶ risk 0-100 · level · confidence
                                        · evidence · recommended action
                                 ▼
                          Dashboard (Next.js)
              risk badge (🟢🟡🔴) · evidence · analyst trace
```

**Feasibility/scalability by design:** cheap triage first, expensive rendering + LLM
reasoning only for ambiguous/high-value cases (measured: see eval output).

---

## Tech stack

- **Backend:** FastAPI + Pydantic, SQLite. Sync pipeline
  run in a threadpool; FastAPI handles concurrency.
- **Reasoning:** provider-agnostic via **LiteLLM** — default **Groq `openai/gpt-oss-20b`**
  (`gpt-oss-120b` selectable), or OpenRouter / Gemini. In **deep mode the LLM's probability
  drives the score** (heuristics + rendered evidence are given to it as input); it falls back
  to rule-based scoring only when no key is present, so it always runs.
- **Rendering:** Playwright (Chromium) with an automatic **HTTP-fetch fallback**. Demo phishing
  pages are **real local fixtures the browser genuinely renders** (see `/fixtures`).
- **Voice:** continuous **logistic model over normalized signal features** (prosody variation,
  noise floor, dynamics, pauses, spectral flatness) — no filename/label peeking. Swap in a
  trained AASIST/wav2vec2 model behind the same `_score_features` signature.
- **Frontend:** Next.js 14 (App Router) + Tailwind — polished dark dashboard.

---

## Run it (no Docker — two terminals)

### Backend — Terminal 1
```powershell
cd TrustShield\backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium   
copy .env.example .env        
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```
API at http://127.0.0.1:8000 · interactive docs at `/docs`.

### Frontend — Terminal 2
```powershell
cd TrustShield\frontend
npm install
npm run dev
```
UI at http://localhost:3000.

> Shortcut: from the `TrustShield` folder run `./run_backend.ps1` and `./run_frontend.ps1`.

### Observability
The backend logs every request through the pipeline to the terminal, tagged with a short id:
```
ts.api    | POST /analyze/text channel_hint=email len=182
ts.fusion | [a1b2c3] channel=email entities=['SEBI'] links=1
ts.fusion | [a1b2c3] triage=0.34 -> ESCALATE (message contains link(s) to inspect)
ts.render | [a1b2c3] render http://... via playwright ok=True captures=True title='SEBI KYC...'
ts.llm    | groq/openai/gpt-oss-20b live 1455ms (rf=True)
ts.fusion | [a1b2c3] VERDICT risk=100 high 'Phishing impersonation' llm=True render=True 2100ms
```
So you can see, per request: the channel, the escalation decision **and why**, whether Playwright
actually rendered (`via playwright` vs `via http_fetch` vs `skipped`), each LLM call + latency,
and the final verdict. `/health` reports live LLM/vision status and call counts.

### Image / PDF input
Vision defaults to **Groq `meta-llama/llama-4-scout-17b-16e-instruct`** — works with the same
`GROQ_API_KEY`, no extra key needed (override with `LLM_VISION_MODEL`, e.g.
`gemini/gemini-2.5-flash` + `GEMINI_API_KEY`). In the **Image / PDF** tab you can **click,
drag & drop, or paste (Ctrl+V)** a screenshot or PDF. Text PDFs use their embedded text;
scanned/image PDFs are rendered and read by the vision model. Everything then flows through the
normal detection pipeline.

---

## Demo narrative (4 clicks)

Each demo scenario is a one-click chip in the UI:

1. **Phishing** — SEBI-impersonation email → TrustShield **actually renders** the linked page
   (a local fixture), the LLM reads the rendered DOM and reports the PAN/password/OTP capture
   form → **HIGH**, "Phishing impersonation targeting SEBI". Open the analyst trace to see
   `render: playwright` and the LLM reasoning.
2. **Broker login phishing** — fake Kite reactivation page → rendered login-form capture.
3. **Social** — "guaranteed 200% returns, join VIP" post → advisory page rendered →
   **manipulation**, false authority + fraudulent CTA.
4. **Voice** — upload a clip → continuous spoof probability from prosody/noise-floor/dynamics
   features + "no provenance (C2PA)".
5. **Verified** — official `sebi.gov.in` communication → **LOW / green**, "Verified official
   communication", high official-source confidence.

Together these prove **both** attack detection **and** authenticity verification.

---

## Test methodology

Three independent layers so nothing is graded on its own homework:

**1. Unit + integration tests (`pytest`)** — deterministic, offline, no key needed
(`FORCE_MOCK_LLM=true`, `NETWORK_ENABLED=false` set in `tests/conftest.py`):
```powershell
cd TrustShield\backend
.\.venv\Scripts\python.exe -m pytest        # 37 tests
```
Covers URL feature extraction, entity NER, manipulation heuristics, channel classification,
authenticity logic, and fusion (incl. a `test_scores_are_not_constant` guard against hardcoded
scores). `tests/test_render.py` parses the fixture HTML **and** drives real **Playwright**
against `file://` fixtures (auto-skips if Chromium is absent). `tests/test_voice.py` asserts the
spoof score is **continuous** (blended synthetic↔natural signals produce distinct values).

**2. Benchmark eval on a labeled set** — `backend/eval/demo_dataset.json` (37 items: emails,
URLs, social posts, verified official comms, audio) including a `difficulty: borderline|subtle`
band of adversarial cases (subtle phishing with no keywords, legit messages that *mention*
"guaranteed returns", allowlisted broker logins):
```powershell
.\.venv\Scripts\python.exe -m eval.make_demo_audio    # first time: generate clips
.\.venv\Scripts\python.exe -m eval.run_eval           # live LLM if a key is set
set TS_EVAL_MOCK=1 && .\.venv\Scripts\python.exe -m eval.run_eval   # force rule-based
```
Reports per-channel + overall **precision / recall / F1 / accuracy**, **authenticity accuracy**,
and **operational metrics** (avg latency, % escalated). Labels: `malicious` = should flag
MEDIUM/HIGH; `legit` = should be LOW. Detection metrics are computed at the flag boundary.

---

## Non-goals (scope honesty)

- Not a production replacement for SEBI/exchange infrastructure.
- Not an internet-scale social crawler or real-time detector.
- Not perfect attribution of an unknown voice/video generator.
- Not a legal authenticity framework. **Verdicts are advisory.**
- The MVP voice detector is a **signal-feature proxy**, not a trained spoof model (interface is
  ready for one). The domain allowlist is a **demo registry**, not exhaustive.

---

## Repo layout

```
TrustShield/
├─ backend/
│  ├─ app/
│  │  ├─ main.py            FastAPI app + CORS
│  │  ├─ config.py          settings / provider selection
│  │  ├─ schemas.py         shared data contracts
│  │  ├─ intake.py          channel classification + normalization
│  │  ├─ llm.py             provider-agnostic reasoning (+ mock fallback)
│  │  ├─ render.py          Playwright render (+ HTTP fallback)
│  │  ├─ fusion.py          Trust Score Engine (triage → deep → fuse)
│  │  ├─ store.py           SQLite persistence
│  │  ├─ preprocessing/     urls · entities · manipulation heuristics
│  │  ├─ detectors/         phishing · voice · social · authenticity
│  │  ├─ routes/            /api/analyze/*  ·  /health
│  │  └─ data/              allowlist.json · demo audio
│  └─ eval/                 demo_dataset.json · run_eval.py · make_demo_audio.py
└─ frontend/                Next.js + Tailwind dashboard
```

---


