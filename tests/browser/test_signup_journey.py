"""Full browser journey. Run with:  pytest tests/browser -p no:cacheprovider"""

import os
import re

import pytest
from django.core import mail

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def page():
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        )
        ctx = browser.new_context(timezone_id="Asia/Kolkata")
        yield ctx.new_page()
        browser.close()


def test_register_verify_login_logout(live_server, page):
    base = live_server.url
    page.goto(f"{base}/accounts/register/")
    page.get_by_label("Full name").fill("Ada Lovelace")
    page.get_by_label("Email").fill("ada@example.com")
    page.locator("#id_password1").fill("violet-lantern-92")
    page.locator("#id_password2").fill("violet-lantern-92")
    page.get_by_role("button", name="Create account").click()
    page.wait_for_url("**/check-email/")

    link = (
        re.search(r"https?://\S+", mail.outbox[-1].body).group(0).replace("http://testserver", base)
    )
    # unverified login is refused
    page.goto(f"{base}/accounts/login/")
    page.get_by_label("Email").fill("ada@example.com")
    page.locator("#id_password").fill("violet-lantern-92")
    page.get_by_role("button", name="Log in").click()
    assert page.get_by_role("alert").is_visible()

    page.goto(link)
    assert page.get_by_role("heading", name="Email confirmed").is_visible()

    page.goto(f"{base}/accounts/login/")
    page.get_by_label("Email").fill("ada@example.com")
    page.locator("#id_password").fill("violet-lantern-92")
    page.get_by_role("button", name="Log in").click()
    page.wait_for_url("**/dashboard/")
    assert "Ada Lovelace" in page.content()

    page.get_by_role("button", name="Log out").click()
    page.wait_for_url(f"{base}/")
    page.goto(f"{base}/dashboard/")
    assert "/accounts/login/" in page.url


def test_password_toggle_and_error_summary(live_server, page):
    page.goto(f"{live_server.url}/accounts/register/")
    field = page.locator("#id_password1")
    assert field.get_attribute("type") == "password"
    page.get_by_role("button", name="Show password").first.click()
    assert field.get_attribute("type") == "text"
    page.get_by_role("button", name="Create account").click()
    page.wait_for_selector("[role=alert]")
    assert "Please fix the following" in page.locator("[role=alert]").inner_text()
