def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "up"
    assert body["llm"] == "karnak-6b"
    assert body["embed"] == "qwen3-embedding:0.6b"
    assert "ollama" in body
