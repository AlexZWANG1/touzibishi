"""
IRIS Tracing — Langfuse v4 safe wrapper.

If langfuse is not installed or not configured, everything degrades to no-op.
No other module needs to check availability — just import from here.
"""

from __future__ import annotations

import os
import logging
from contextlib import contextmanager
from functools import wraps

log = logging.getLogger(__name__)

# ── Detect availability ────────────────────────────────────

_ENABLED = False

try:
    if (
        os.getenv("LANGFUSE_ENABLED", "true").lower() != "false"
        and os.getenv("LANGFUSE_SECRET_KEY")
    ):
        from langfuse import (
            get_client as _get_client,
            observe as _observe,
            propagate_attributes as _propagate_attributes,
        )
        _ENABLED = True
        log.info("Langfuse tracing enabled")
    else:
        log.info("Langfuse tracing disabled (env not configured)")
except ImportError:
    log.info("Langfuse tracing disabled (package not installed)")


def is_enabled() -> bool:
    return _ENABLED


# ── Safe wrappers ──────────────────────────────────────────

def observe(*, name: str | None = None, as_type: str | None = None):
    """Drop-in for @observe(). No-op decorator when langfuse unavailable."""
    if _ENABLED:
        kwargs = {}
        if name is not None:
            kwargs["name"] = name
        if as_type is not None:
            kwargs["as_type"] = as_type
        return _observe(**kwargs)

    # No-op: return the function unchanged
    def passthrough(fn):
        return fn
    return passthrough


@contextmanager
def propagate_attributes(**kwargs):
    """Drop-in for propagate_attributes(). No-op context manager when unavailable."""
    if _ENABLED:
        with _propagate_attributes(**kwargs):
            yield
    else:
        yield


@contextmanager
def start_span(name: str, input: dict | None = None):
    """Create a manual observation span. No-op when unavailable.

    Usage:
        with start_span("tool:financials", input={"ticker": "NVDA"}) as span:
            result = do_work()
            span.set_output({"status": "ok"})
    """
    if _ENABLED:
        client = _get_client()
        with client.start_as_current_observation(
            name=name, as_type="span", input=input
        ) as obs:
            yield _SpanHandle(obs)
    else:
        yield _NoOpSpan()


def flush():
    """Flush pending traces to Langfuse. No-op when unavailable."""
    if _ENABLED:
        try:
            _get_client().flush()
        except Exception as e:
            log.debug("Langfuse flush error: %s", e)


def shutdown():
    """Flush + terminate background threads. Call on app exit."""
    if _ENABLED:
        try:
            _get_client().shutdown()
        except Exception as e:
            log.debug("Langfuse shutdown error: %s", e)


# ── Span handle (thin wrapper for uniform API) ─────────────

class _SpanHandle:
    """Wraps a langfuse observation to provide a simple set_output / set_error API."""

    def __init__(self, obs):
        self._obs = obs

    def set_output(self, output: dict):
        try:
            self._obs.update(output=output)
        except Exception:
            pass

    def set_error(self, error: str):
        try:
            self._obs.update(
                output={"error": error},
                level="ERROR",
                status_message=error,
            )
        except Exception:
            pass


class _NoOpSpan:
    """No-op span when langfuse is unavailable."""

    def set_output(self, output: dict):
        pass

    def set_error(self, error: str):
        pass
