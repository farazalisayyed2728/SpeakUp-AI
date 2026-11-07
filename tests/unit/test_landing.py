import re


def test_landing_renders(client):
    r = client.get("/")
    html = r.content.decode()
    assert r.status_code == 200
    assert html.count("<h1") == 1
    assert "dist/app.js" in html and "dist/app.css" in html


def test_all_seven_modes_present(client):
    html = client.get("/").content.decode()
    assert len(re.findall(r"data-tilt", html)) == 7


def test_mic_not_requested_on_load(client):
    # Permission must only ever be requested from a click handler, never at page load.
    html = client.get("/").content.decode()
    assert "getUserMedia" not in html
    assert '@click="toggle()"' in html


def test_no_secrets_or_provider_keys_in_page(client):
    html = client.get("/").content.decode().lower()
    assert "api_key" not in html and "gemini" not in html
