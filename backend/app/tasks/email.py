"""Async email delivery via Celery.

Wraps the synchronous `app.utils.send_email` so request handlers can hand off
email sending to a worker instead of blocking on SMTP. Routed to the `emails`
queue (see `task_routes` in `app.celery_app`).
"""

import logging

from app.celery_app import celery_app
from app.utils import send_email

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def send_email_task(
    self,
    email_to: str,
    subject: str = "",
    html_content: str = "",
) -> None:
    """Send one email, retrying with exponential backoff on failure."""
    try:
        send_email(email_to=email_to, subject=subject, html_content=html_content)
    except Exception as exc:  # noqa: BLE001 — retry any delivery failure
        logger.error("email task failed: %s", exc)
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))
