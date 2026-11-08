import pytest
from django.contrib.auth.models import Group
from django.test import Client, override_settings
from django.urls import reverse

from apps.accounts.models import AuditEvent

pytestmark = pytest.mark.django_db


def test_csrf_enforced_on_login_and_logout(make_user):
    make_user()
    c = Client(enforce_csrf_checks=True)
    assert c.post(reverse("accounts:login"), {"email": "ada@example.com", "password": "x"}).status_code == 403
    assert c.post(reverse("accounts:logout")).status_code == 403
    assert c.post(reverse("accounts:register"), {}).status_code == 403


def test_login_form_contains_csrf_token(client):
    assert b"csrfmiddlewaretoken" in client.get(reverse("accounts:login")).content


def test_login_rate_limited_per_email_with_retry_after(client, make_user):
    make_user()
    url = reverse("accounts:login")
    for _ in range(5):
        assert client.post(url, {"email": "ada@example.com", "password": "bad-bad-bad-bad"}).status_code == 200
    r = client.post(url, {"email": "ada@example.com", "password": "correct-horse-battery"})
    assert r.status_code == 429 and int(r["Retry-After"]) > 0
    assert b"Too many attempts" in r.content
    assert AuditEvent.objects.filter(event_type="rate_limited").exists()
    assert "_auth_user_id" not in client.session  # even the right password is refused


def test_email_limit_is_case_insensitive(client, make_user):
    make_user()
    url = reverse("accounts:login")
    for i in range(5):
        client.post(url, {"email": ("ADA@example.com", "ada@EXAMPLE.com")[i % 2], "password": "bad-bad-bad-bad"})
    assert client.post(url, {"email": "Ada@Example.com", "password": "x"}).status_code == 429


def test_other_users_not_affected_by_one_users_lockout(client, make_user):
    make_user()
    make_user("bob@example.com")
    url = reverse("accounts:login")
    for _ in range(6):
        client.post(url, {"email": "ada@example.com", "password": "bad-bad-bad-bad"})
    r = client.post(url, {"email": "bob@example.com", "password": "correct-horse-battery"})
    assert r.status_code == 302


def test_registration_ip_limit_cannot_be_bypassed_by_spoofing_forwarded_header(client):
    url = reverse("accounts:register")
    codes = [client.post(url, {}, headers={"X-Forwarded-For": f"9.9.9.{i}"}).status_code for i in range(11)]
    assert codes[:10] == [200] * 10 and codes[10] == 429


@override_settings(TRUSTED_PROXY_COUNT=1)
def test_behind_trusted_proxy_real_client_ips_are_counted_separately(client):
    url = reverse("accounts:register")
    for _ in range(10):
        client.post(url, {}, headers={"X-Forwarded-For": "203.0.113.1"})
    assert client.post(url, {}, headers={"X-Forwarded-For": "203.0.113.1"}).status_code == 429
    assert client.post(url, {}, headers={"X-Forwarded-For": "203.0.113.2"}).status_code == 200


def test_reset_and_resend_are_rate_limited(client):
    for name in ("accounts:password-forgot", "accounts:resend-verification"):
        codes = [client.post(reverse(name), {"email": "x@example.com"}).status_code for _ in range(4)]
        assert codes[:3] == [302] * 3 and codes[3] == 429


def test_normal_user_cannot_use_admin(client, make_user):
    client.force_login(make_user())
    r = client.get("/admin/")
    assert r.status_code == 302 and "/admin/login/" in r.url
    assert client.get("/admin/accounts/user/").status_code == 302


def test_staff_without_permissions_sees_no_audit_log(client, make_user):
    client.force_login(make_user(is_staff=True))
    assert client.get("/admin/accounts/auditevent/").status_code == 403


def test_support_group_can_view_but_not_change_audit_log(client, make_user):
    u = make_user(is_staff=True)
    u.groups.add(Group.objects.get(name="Support"))
    client.force_login(u)
    assert client.get("/admin/accounts/auditevent/").status_code == 200
    assert client.get("/admin/accounts/user/").status_code == 200
    assert client.post("/admin/accounts/auditevent/add/", {}).status_code == 403


def test_roles_exist_with_expected_permissions():
    support = Group.objects.get(name="Support")
    assert set(support.permissions.values_list("codename", flat=True)) == {"view_user", "view_auditevent"}
    assert not Group.objects.get(name="Administrators").permissions.filter(codename="delete_user").exists()


def test_audit_trail_never_contains_secrets(client, make_user):
    make_user()
    client.post(reverse("accounts:login"), {"email": "ada@example.com", "password": "hunter2-secret-pw"})
    client.post(reverse("accounts:login"), {"email": "ghost@example.com", "password": "hunter2-secret-pw"})
    blob = " ".join(str(e.metadata) for e in AuditEvent.objects.all())
    assert "hunter2" not in blob and "ghost@example.com" not in blob


def test_audit_log_is_read_only_in_admin(client, make_user):
    su = make_user("root@example.com", is_staff=True, is_superuser=True)
    client.force_login(su)
    AuditEvent.objects.create(event_type="logout")
    pk = AuditEvent.objects.get().pk
    assert client.post(f"/admin/accounts/auditevent/{pk}/delete/", {"post": "yes"}).status_code == 403
    