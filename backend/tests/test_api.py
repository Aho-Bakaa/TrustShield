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


def test_share_flow(client):
    """Create a share token for an analysis, then resolve it (roadmap 3.2)."""
    r = client.post("/api/analyze/text", json={"raw_input": "join telegram tips http://tips.top urgent"})
    assert r.status_code == 200
    analysis_id = r.json()["id"]

    s = client.post(f"/api/share/{analysis_id}")
    assert s.status_code == 200
    token = s.json()["token"]
    assert token

    resolved = client.get(f"/api/share/{token}")
    assert resolved.status_code == 200
    assert resolved.json()["id"] == analysis_id

    bad = client.get("/api/share/nonexistent-token")
    assert bad.status_code == 410


def test_whatsapp_webhook_disabled(client):
    """WhatsApp webhook returns 403 when not configured (roadmap 3.1)."""
    r = client.post("/api/whatsapp/webhook", json={"entry": []})
    assert r.status_code == 403
    r2 = client.get("/api/whatsapp/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "c"})
    assert r2.status_code == 403
