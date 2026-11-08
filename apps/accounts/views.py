from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetConfirmView
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.net import client_ip
from apps.core.ratelimit import check_all

from . import audit, ratelimits, services
from .forms import (
    EmailForm,
    LoginForm,
    RegistrationForm,
    StyledPasswordChangeForm,
    StyledSetPasswordForm,
)
from .models import AuditEvent
from .services import VerifyResult


def _page(request, status: int = 200, **ctx):
    return render(request, "accounts/page.html", ctx, status=status)


def _limited(request, wait: int, user=None):
    """429 page. The wait shown comes from the limiter's real reset time, never a guess."""
    audit.record(AuditEvent.Type.RATE_LIMITED, request, user, path=request.path)
    minutes = max(1, -(-wait // 60))
    unit = "minute" if minutes == 1 else "minutes"
    resp = _page(
        request,
        status=429,
        heading="Too many attempts",
        message=f"For your security we've paused this action. You can try again in about {minutes} {unit}.",
        actions=[("Back to home", reverse("core:landing"), True)],
    )
    resp["Retry-After"] = str(wait)
    return resp


def _safe_next(request) -> str:
    target = request.POST.get("next") or request.GET.get("next") or ""
    ok = url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    )
    return target if ok else ""


@never_cache
@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST":
        wait = check_all([(ratelimits.REGISTER_IP, client_ip(request))])
        if wait:
            return _limited(request, wait)
        if form.is_valid():
            d = form.cleaned_data
            services.register(
                email=d["email"],
                full_name=d["full_name"],
                password=d["password1"],
                tz=d["timezone"],
                request=request,
            )
            return redirect("accounts:check-email")
    return _page(
        request,
        form=form,
        heading="Create your account",
        intro="Free to start. We'll email you a link to confirm your address.",
        submit="Create account",
        hints=True,
        links=[("Already have an account? Log in", reverse("accounts:login"))],
    )


def check_email_view(request):
    return _page(
        request,
        heading="Check your email",
        message=(
            "If that address can be used, we've sent you a message with the next step. "
            "It can take a minute to arrive, so check your spam folder too."
        ),
        actions=[
            ("Resend the link", reverse("accounts:resend-verification"), False),
            ("Go to log in", reverse("accounts:login"), True),
        ],
    )


@never_cache
def verify_email_view(request, token: str):
    result = services.verify_email(token, request)
    login_action = ("Log in", reverse("accounts:login"), True)
    resend_action = ("Send a new link", reverse("accounts:resend-verification"), True)
    copy = {
        VerifyResult.VERIFIED: ("Email confirmed", "You're all set. Log in to start practising.", login_action),
        VerifyResult.ALREADY_VERIFIED: ("Already confirmed", "This email is already confirmed, so you can log in.", login_action),
        VerifyResult.EXPIRED: ("This link has expired", "Confirmation links last 24 hours. We can send you a fresh one.", resend_action),
        VerifyResult.INVALID: ("This link isn't valid", "It may have been copied incorrectly. We can send you a new one.", resend_action),
    }[result]
    status = 200 if result in (VerifyResult.VERIFIED, VerifyResult.ALREADY_VERIFIED) else 400
    return _page(request, status=status, heading=copy[0], message=copy[1], actions=[copy[2]])


@never_cache
@require_http_methods(["GET", "POST"])
def resend_verification_view(request):
    form = EmailForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data["email"]
            wait = check_all(
                [(ratelimits.RESEND_IP, client_ip(request)), (ratelimits.RESEND_EMAIL, email)]
            )
            if wait:
                return _limited(request, wait)
            services.resend_verification(email, request)
            return redirect("accounts:check-email")
    return _page(
        request,
        form=form,
        heading="Resend confirmation",
        intro="Enter your email and we'll send a new confirmation link if it needs one.",
        submit="Send link",
        links=[("Back to log in", reverse("accounts:login"))],
    )


@never_cache
@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email, password = form.cleaned_data["email"], form.cleaned_data["password"]
        wait = check_all([(ratelimits.LOGIN_IP, client_ip(request)), (ratelimits.LOGIN_EMAIL, email)])
        if wait:
            return _limited(request, wait)
        user = authenticate(request, username=email, password=password)
        if user is None:
            audit.record(AuditEvent.Type.LOGIN_FAILED, request, email=audit.fingerprint(email))
            form.add_error(None, "Email or password is incorrect.")
        elif not user.is_email_verified:
            audit.record(AuditEvent.Type.LOGIN_BLOCKED_UNVERIFIED, request, user)
            form.add_error(None, "Please confirm your email first. Use “Resend confirmation” below if you need a new link.")
        else:
            login(request, user)  # rotates the session key
            audit.record(AuditEvent.Type.LOGIN_SUCCESS, request, user)
            return redirect(_safe_next(request) or "core:dashboard")
    return _page(
        request,
        form=form,
        next=_safe_next(request),
        heading="Welcome back",
        submit="Log in",
        links=[
            ("Forgot your password?", reverse("accounts:password-forgot")),
            ("Resend confirmation", reverse("accounts:resend-verification")),
            ("New here? Create an account", reverse("accounts:register")),
        ],
    )


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        audit.record(AuditEvent.Type.LOGOUT, request, request.user)
    logout(request)
    return redirect("core:landing")


@never_cache
@require_http_methods(["GET", "POST"])
def password_forgot_view(request):
    form = EmailForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        wait = check_all([(ratelimits.RESET_IP, client_ip(request)), (ratelimits.RESET_EMAIL, email)])
        if wait:
            return _limited(request, wait)
        services.request_password_reset(email, request)
        return redirect("accounts:password-forgot-done")
    return _page(
        request,
        form=form,
        heading="Reset your password",
        intro="Enter your email and we'll send a link to choose a new password.",
        submit="Send reset link",
        links=[("Back to log in", reverse("accounts:login"))],
    )


def password_forgot_done_view(request):
    return _page(
        request,
        heading="Check your email",
        message="If an account exists for that address, a reset link is on its way. It works once and expires in 1 hour.",
        actions=[("Back to log in", reverse("accounts:login"), True)],
    )


class PasswordResetConfirmPage(PasswordResetConfirmView):
    template_name = "accounts/page.html"
    form_class = StyledSetPasswordForm
    success_url = reverse_lazy("accounts:password-reset-complete")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if ctx.get("validlink"):
            ctx.update(heading="Choose a new password", submit="Save password", hints=True)
        else:
            ctx.update(
                heading="This link can't be used",
                message="Reset links work once and expire after 1 hour. Request a new one to continue.",
                actions=[("Request a new link", reverse("accounts:password-forgot"), True)],
            )
        return ctx

    def form_valid(self, form):
        user = form.user
        if user.email_verified_at is None:  # they proved they control the inbox
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified_at"])
        response = super().form_valid(form)
        audit.record(AuditEvent.Type.PASSWORD_RESET_COMPLETED, self.request, user)
        return response


def password_reset_complete_view(request):
    return _page(
        request,
        heading="Password updated",
        message="Your password has been changed. Any other devices have been signed out.",
        actions=[("Log in", reverse("accounts:login"), True)],
    )


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def password_change_view(request):
    form = StyledPasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST":
        wait = check_all([(ratelimits.PASSWORD_CHANGE_USER, str(request.user.pk))])
        if wait:
            return _limited(request, wait, request.user)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # keep THIS device signed in
            audit.record(AuditEvent.Type.PASSWORD_CHANGED, request, user)
            return _page(
                request,
                heading="Password changed",
                message="Your password has been updated. Other devices have been signed out.",
                actions=[("Back to dashboard", reverse("core:dashboard"), True)],
            )
    return _page(
        request,
        form=form,
        heading="Change your password",
        submit="Change password",
        hints=True,
        links=[("Cancel", reverse("core:dashboard"))],
    )