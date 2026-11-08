from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("check-email/", views.check_email_view, name="check-email"),
    path("verify/resend/", views.resend_verification_view, name="resend-verification"),
    path("verify/<str:token>/", views.verify_email_view, name="verify-email"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("password/forgot/", views.password_forgot_view, name="password-forgot"),
    path("password/forgot/sent/", views.password_forgot_done_view, name="password-forgot-done"),
    path(
        "password/reset/<uidb64>/<token>/",
        views.PasswordResetConfirmPage.as_view(),
        name="password-reset-confirm",
    ),
    path(
        "password/reset/complete/",
        views.password_reset_complete_view,
        name="password-reset-complete",
    ),
    path("password/change/", views.password_change_view, name="password-change"),
]
