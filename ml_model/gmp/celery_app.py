"""Celery integration for moving long LLM calls out of the request path.

Tasks run inside a Flask app context (so they can use the DB / data collector).
If no broker is configured (CELERY_BROKER_URL unset), tasks run eagerly —
inline, no worker required — so local dev works without Redis. In production,
set CELERY_BROKER_URL (e.g. redis://redis:6379/0) and run a `celery worker`.
"""

import os

from celery import Celery, Task


def make_celery(app):
    broker = os.environ.get("CELERY_BROKER_URL")
    eager = not broker  # no broker → run inline (dev/test)

    # Results must be retrievable across requests (enqueue then poll). Default to
    # the broker, or a local SQLite store so eager mode still works without Redis.
    default_result = f"db+sqlite:///{os.path.abspath('celery_results.db')}"
    result_backend = os.environ.get("CELERY_RESULT_BACKEND") or broker or default_result

    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery = Celery(
        app.import_name,
        task_cls=FlaskTask,
        broker=broker or "memory://",
        backend=result_backend,
    )
    celery.conf.update(
        task_always_eager=eager,
        task_store_eager_result=True,   # persist eager results so polling works
        task_track_started=True,
        result_expires=int(os.environ.get("CELERY_RESULT_EXPIRES", 3600)),
        worker_hijack_root_logger=False,
        broker_connection_retry_on_startup=True,
    )
    celery.set_default()
    app.extensions["celery"] = celery

    # Whether the frontend should use the async (enqueue + poll) endpoints.
    # Defaults to "a real broker is configured"; can be forced via env.
    forced = os.environ.get("ASYNC_TASKS_ENABLED")
    app.config["ASYNC_TASKS_ENABLED"] = (
        forced.lower() in ("1", "true", "yes") if forced is not None else (not eager)
    )
    return celery
