from django.apps import AppConfig
from django.db.models.signals import post_migrate


def ensure_roles(sender, **kwargs):
    """Create the staff role groups idempotently after migrations (permissions exist by now)."""
    from django.contrib.auth.models import Group, Permission

    roles = {
        # Read-only support: can look at users and the audit trail, change nothing.
        "Support": ["view_user", "view_auditevent"],
        # Administrators manage users; full superusers are still created via createsuperuser.
        "Administrators": ["view_user", "change_user", "view_auditevent", "view_group"],
    }
    for name, codenames in roles.items():
        group, _ = Group.objects.get_or_create(name=name)
        perms = Permission.objects.filter(
            codename__in=codenames, content_type__app_label__in=["accounts", "auth"]
        )
        group.permissions.set(perms)


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    label = "accounts"

    def ready(self):
        post_migrate.connect(ensure_roles, sender=self)
