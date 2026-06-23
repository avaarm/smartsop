"""Gunicorn configuration for the GMP backend.

The app is I/O-bound — most request time is spent waiting on the Ollama LLM,
the database, or PubMed Central. Sync workers handle one request each, so a
handful of slow LLM calls would block every other user. Threaded (gthread)
workers let each worker serve many concurrent requests while those waits
happen, which is what lets a single instance handle real concurrency. Scale
out further by running more instances behind a load balancer (the app is
stateless: JWT auth, shared DB via DATABASE_URL, shared docs via S3).

Everything is overridable via environment variables.
"""

import os
import multiprocessing

bind = f"0.0.0.0:{os.environ.get('PORT', '5001')}"

worker_class = "gthread"
workers = int(os.environ.get("GUNICORN_WORKERS", max(2, multiprocessing.cpu_count())))
threads = int(os.environ.get("GUNICORN_THREADS", 8))

# LLM section generation can take up to ~90s; give headroom before a worker is
# treated as hung and killed.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", 30))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", 5))

# Recycle workers periodically to bound any slow memory growth.
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", 100))

# Log to stdout/stderr so the container platform collects it.
accesslog = "-"
errorlog = "-"
