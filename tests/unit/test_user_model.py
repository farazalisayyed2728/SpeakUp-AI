import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_email_is_normalized_to_lowercase():
    u = User.objects.create_user("  Ada@Example.COM ", "s3cure-passphrase")
    assert u.email == "ada@example.com"


def test_case_variant_duplicate_is_rejected_by_database():
    User.objects.create_user("ada@example.com", "s3cure-passphrase")
    # Bypass the manager so we prove the DB constraint itself, not just normalization.
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.bulk_create([User(email="ADA@example.com")])


def test_password_is_hashed_with_argon2():
    u = User.objects.create_user("a@example.com", "s3cure-passphrase")
    assert u.password.startswith("argon2")
    assert u.check_password("s3cure-passphrase")


def test_email_required():
    with pytest.raises(ValueError):
        User.objects.create_user("", "x")


def test_superuser_flags():
    su = User.objects.create_superuser("root@example.com", "s3cure-passphrase")
    assert su.is_staff and su.is_superuser


def test_superuser_cannot_be_created_without_flags():
    with pytest.raises(ValueError):
        User.objects.create_superuser("r@example.com", "x", is_staff=False)


def test_new_user_is_unverified():
    u = User.objects.create_user("n@example.com", "s3cure-passphrase")
    assert u.is_email_verified is False
