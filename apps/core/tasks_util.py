import logging

logger = logging.getLogger(__name__)


def enqueue(task, *args) -> bool:
    """Queue a Celery task without ever breaking the web request if the broker is down.

    Call this AFTER the surrounding database transaction has committed, so a worker can
    never run before the rows it needs exist. Returns False if queueing failed.
    """
    try:
        task.delay(*args)
        return True
    except Exception:
        logger.exception("Could not enqueue task %s", getattr(task, "name", task))
        return False