import pytest
from django.urls import reverse

from apps.accounts.models import AuditEvent

pytestmark = pytest.mark.django_db
LOGIN = "accounts:login"


def login(client, email="ada@example.com", password="correct-horse-battery", **extra):
    return client.post(reverse(LOGIN), {"email": email, "password": password, **extra})


def test_login_success_redirects_to_dashboard_and_audits(client, make_user):
    u = make_user()
    r = login(client, email="ADA@example.com")
    assert r.status_code == 302 and r.url == reverse("core:dashboard")
    assert AuditEvent.objects.filter(user=u, event_type="login_success").exists()
    assert client.get(reverse("core:dashboard")).status_code == 200


def test_wrong_password_and_unknown_email_look_identical(client, make_user):
    make_user()
    a = login(client, password="wrong-wrong-wrong")
    b = login(client, email="ghost@example.com")
    assert a.status_code == b.status_code == 200
    assert (
        b"Email or password is incorrect." in a.content
        and b"Email or password is incorrect." in b.content
    )
    assert AuditEvent.objects.filter(event_type="login_failed").count() == 2


def test_inactive_user_cannot_log_in(client, make_user):
    make_user(is_active=False)
    assert b"incorrect" in login(client).content


def test_safe_next_is_followed(client, make_user):
    make_user()
    r = login(client, next="/dashboard/")
    assert r.url == "/dashboard/"


@pytest.mark.parametrize(
    "evil", ["https://evil.example/steal", "//evil.example", "javascript:alert(1)"]
)
def test_open_redirect_is_blocked(client, make_user, evil):
    make_user()
    assert login(client, next=evil).url == reverse("core:dashboard")


def test_session_key_rotates_on_login(client, make_user):
    make_user()
    client.get(reverse(LOGIN))
    before = client.session.session_key
    login(client)
    assert client.session.session_key != before


def test_logout_requires_post_and_ends_session(client, make_user):
    make_user()
    login(client)
    assert client.get(reverse("accounts:logout")).status_code == 405
    assert client.get(reverse("core:dashboard")).status_code == 200  # GET did not log out
    r = client.post(reverse("accounts:logout"))
    assert r.status_code == 302
    assert client.get(reverse("core:dashboard")).status_code == 302
    assert AuditEvent.objects.filter(event_type="logout").exists()


def test_dashboard_requires_login_and_preserves_destination(client):
    r = client.get(reverse("core:dashboard"))
    assert r.status_code == 302 and r.url.startswith(reverse(LOGIN)) and "next=" in r.url


def test_session_cookie_flags(client, make_user):
    make_user()
    login(client)
    cookie = client.cookies["sessionid"]
    assert cookie["httponly"] and cookie["samesite"] == "Lax"
