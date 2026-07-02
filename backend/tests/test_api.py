"""API tests via FastAPI TestClient (deterministic: mock LLM, no network)."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "llm" in body


def test_analyze_text_phishing(client):
    r = client.post("/api/analyze/text", json={
        "raw_input": "URGENT: SEBI KYC suspended, share OTP and password at http://sebi-kyc-verify.xyz/login",
        "claimed_source": "SEBI",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["risk_level"] in ("medium", "high")
    assert body["channel_type"] in ("email", "url")
    assert body["recommended_action"]
    assert len(body["trace"]) >= 3


def test_analyze_text_verified(client):
    r = client.post("/api/analyze/text", json={
        "raw_input": "SEBI Investor Charter at https://www.sebi.gov.in/x.html dkim=pass",
        "claimed_source": "SEBI",
    })
    body = r.json()
    assert body["risk_level"] == "low"
    assert body["authenticity"]["is_official_source"] is True


def test_analyze_empty_rejected(client):
    r = client.post("/api/analyze/text", json={"raw_input": "   "})
    assert r.status_code == 400


def test_recent_endpoint(client):
    client.post("/api/analyze/text", json={"raw_input": "join telegram tips http://tips.top urgent"})
    r = client.get("/api/recent")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
