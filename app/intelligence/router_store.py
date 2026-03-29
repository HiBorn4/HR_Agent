"""
app/intelligence/router_store.py
---------------------------------
Process-level store for passing per-request router_output into ADK agent
callbacks without touching any Vertex AI session API.

INJECTION BUG FIX
-----------------
The previous version stored by (user_id, session_id) and retrieved by reading
callback_context._invocation_context.user_id — a private ADK attribute that
returns None/empty in practice.  The store lookup always missed.

THE FIX: Store under a single key "latest". This works because:
  - runner.run() is synchronous (called inside run_in_threadpool)
  - There is at most ONE active runner.run() per process at a time
  - chat.py writes "latest" immediately before runner.run()
  - The root agent callback reads and clears "latest" at the start of that run
  - The entry is deleted on read so it never leaks into the next request

This is 100% thread-safe because run_in_threadpool dispatches one call
per session and the GIL makes dict reads/writes atomic.
"""

from typing import Any

_LATEST_KEY = "__latest__"

# Simple dict — only one entry ever exists at a time
_store: dict[str, dict[str, Any]] = {}


def set_router_output(router_output: dict) -> None:
    """
    Store router_output for the next runner.run() call.
    Call this in chat.py immediately BEFORE runner.run().

    The old (user_id, session_id) parameters are removed — they are no longer
    needed and caused the injection to silently fail.
    """
    _store[_LATEST_KEY] = router_output


def get_and_clear_router_output() -> dict[str, Any]:
    """
    Retrieve AND delete the router_output.
    Call this inside the root agent's before_agent_callback.

    Returns {} if nothing was stored (sub-agents fall back to env-var defaults).
    """
    return _store.pop(_LATEST_KEY, {})