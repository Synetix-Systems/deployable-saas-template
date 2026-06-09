"""Example Celery tasks — delete or replace with your own.

These demonstrate the two task shapes you get out of the box:
  * `add` — a plain on-demand task you enqueue from the API
    (`add.delay(2, 3)`), routed to the `default` queue.
  * `heartbeat` — a periodic task fired by Celery beat (see
    `beat_schedule` in `app.celery_app`).
"""

import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def add(x: int, y: int) -> int:
    """Trivial on-demand task. Enqueue with `add.delay(2, 3)`."""
    result = x + y
    logger.info("add(%s, %s) = %s", x, y, result)
    return result


@celery_app.task
def heartbeat() -> str:
    """Periodic no-op proving beat → worker wiring is alive."""
    logger.info("heartbeat")
    return "ok"
