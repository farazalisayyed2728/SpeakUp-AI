def test_request_id_generated(client):
    r = client.get("/health/live/")
    assert len(r["X-Request-ID"]) == 32


def test_valid_incoming_request_id_is_reused(client):
    r = client.get("/health/live/", headers={"X-Request-ID": "abc-12345678"})
    assert r["X-Request-ID"] == "abc-12345678"


def test_unsafe_incoming_request_id_is_replaced(client):
    r = client.get("/health/live/", headers={"X-Request-ID": "x\nInjected: log line"})
    assert "Injected" not in r["X-Request-ID"] and len(r["X-Request-ID"]) == 32


def test_security_headers_present(client):
    r = client.get("/")
    assert r["X-Content-Type-Options"] == "nosniff"
    assert r["X-Frame-Options"] == "DENY"
