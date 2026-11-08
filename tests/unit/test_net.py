from django.test import RequestFactory, override_settings

from apps.core.net import client_ip

rf = RequestFactory()


def req(xff=None, remote="10.0.0.9"):
    kw = {"REMOTE_ADDR": remote}
    if xff:
        kw["HTTP_X_FORWARDED_FOR"] = xff
    return rf.get("/", **kw)


@override_settings(TRUSTED_PROXY_COUNT=0)
def test_forwarded_header_ignored_without_trusted_proxy():
    assert client_ip(req(xff="1.2.3.4")) == "10.0.0.9"


@override_settings(TRUSTED_PROXY_COUNT=1)
def test_spoofed_left_entries_are_ignored():
    # attacker sends "6.6.6.6"; our proxy appends the real client "203.0.113.7"
    assert client_ip(req(xff="6.6.6.6, 203.0.113.7")) == "203.0.113.7"


@override_settings(TRUSTED_PROXY_COUNT=1)
def test_garbage_forwarded_value_falls_back_to_remote_addr():
    assert client_ip(req(xff="not-an-ip")) == "10.0.0.9"


@override_settings(TRUSTED_PROXY_COUNT=2)
def test_too_few_entries_falls_back():
    assert client_ip(req(xff="203.0.113.7")) == "10.0.0.9"