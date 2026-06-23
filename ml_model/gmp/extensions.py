"""Shared Flask extensions.

The rate limiter lives here (not in gmp_server) so blueprint route modules can
import it without a circular import. It protects the scarce/expensive resources
— auth (brute force) and the LLM endpoints (worker threads) — so one client
can't starve everyone else under load.

Storage defaults to in-memory (per-instance limiting). For exact limits across
multiple instances, set RATELIMIT_STORAGE_URI to a shared store, e.g.
redis://host:6379.
"""

import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Per-endpoint limits (env-tunable). Empty/"none" disables the limit.
AUTH_RATELIMIT = os.environ.get("AUTH_RATELIMIT", "10 per minute")
LLM_RATELIMIT = os.environ.get("LLM_RATELIMIT", "30 per minute")

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
    # No blanket default — only the explicitly decorated sensitive endpoints
    # are limited, so normal browsing and template/list calls are unaffected.
    default_limits=[],
    headers_enabled=True,
)
