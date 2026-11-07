from celery import shared_task


@shared_task(name="core.ping", soft_time_limit=10, time_limit=15)
def ping() -> str:
    """Trivial task used to verify the worker and broker are wired correctly."""
    return "pong"
