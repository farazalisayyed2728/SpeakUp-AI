from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)  # hashes; None makes an unusable password
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("email_verified_at", timezone.now())
        if not (extra["is_staff"] and extra["is_superuser"]):
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create(email, password, **extra)

    def normalize_email(self, email):  # type: ignore[override]
        # Lower-case the whole address so Ada@x.com and ada@x.com are one identity.
        return super().normalize_email(email).strip().lower()


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, max_length=254)
    full_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        constraints = [
            # Database-level guarantee: no case-variant duplicates, whatever the code does.
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
        ]

    def __str__(self) -> str:
        return self.email

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None


class AuditEvent(models.Model):
    """Append-only security trail. Never store passwords, tokens or raw emails in metadata."""

    class Type(models.TextChoices):
        REGISTERED = "registered"
        REGISTER_DUPLICATE = "register_duplicate"
        EMAIL_VERIFIED = "email_verified"
        VERIFICATION_RESENT = "verification_resent"
        LOGIN_SUCCESS = "login_success"
        LOGIN_FAILED = "login_failed"
        LOGIN_BLOCKED_UNVERIFIED = "login_blocked_unverified"
        LOGOUT = "logout"
        PASSWORD_RESET_REQUESTED = "password_reset_requested"
        PASSWORD_RESET_COMPLETED = "password_reset_completed"
        PASSWORD_CHANGED = "password_changed"
        RATE_LIMITED = "rate_limited"

    user = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    event_type = models.CharField(max_length=40, choices=Type.choices)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=200, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="audit_user_created_idx"),
            models.Index(fields=["event_type", "-created_at"], name="audit_type_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} @ {self.created_at:%Y-%m-%d %H:%M}"
