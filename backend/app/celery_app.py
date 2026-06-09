"""Celery application configuration.

The same backend image runs the web API, the Celery workers, and Celery beat —
only the container command differs (see the chart's workers-rollout.yaml). Add
your task modules to `include` and route them to a queue in `task_routes`.
"""

from celery import Celery

from app.core.config import settings

# Redis visibility timeout (seconds), set on BOTH the broker and the result
# backend transport options. Redis has no native ack: an unacked task is
# redelivered to another worker once visibility_timeout elapses. With
# task_acks_late the ack lands only after the task finishes, so this MUST
# exceed your longest-running task or a long task is redelivered and runs
# twice. Default is 3600s; raise it if you have tasks that run longer.
_VISIBILITY_TIMEOUT = 12_000

celery_app = Celery(
    "app",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.example",
        "app.tasks.email",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Ack after completion, not on receipt — work survives a worker crash.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": _VISIBILITY_TIMEOUT},
    result_backend_transport_options={"visibility_timeout": _VISIBILITY_TIMEOUT},
    # Route task modules to queues. Each queue maps to a worker Rollout in the
    # chart (values.yaml `workers`). Unrouted tasks land on `default`.
    task_default_queue="default",
    task_routes={
        "app.tasks.email.*": {"queue": "emails"},
        "app.tasks.example.*": {"queue": "default"},
    },
    # Periodic tasks. Beat is a singleton scheduler (one replica in the chart).
    beat_schedule={
        "heartbeat": {
            "task": "app.tasks.example.heartbeat",
            "schedule": 60.0,
        },
    },
)
