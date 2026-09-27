"""
Shared Gemini client plus a retry/backoff wrapper for transient errors.

Gemini's free tier has tight per-minute rate limits (429), and the shared
models also return 503 when they're overloaded independent of your own
quota - both are worth retrying, unlike a genuine 400/404. Every call in
this codebase (embeddings, and every agent's chat call) should go through
`call_with_backoff` rather than calling the client directly.
"""
import logging
import random
import time
from typing import Callable, Optional, TypeVar

from google import genai
from google.genai import errors as genai_errors

from app.config import settings

logger = logging.getLogger("quorum")

client = genai.Client(api_key=settings.GEMINI_API_KEY)

_MAX_RETRIES = 4
_BASE_DELAY_SECONDS = 1.0
_RETRYABLE_CODES = {429, 503}

T = TypeVar("T")


def call_with_backoff(fn: Callable[[], T], on_retry: Optional[Callable[[], None]] = None) -> T:
    """
    Calls `fn`, retrying with exponential backoff + jitter on 429 (rate
    limited) or 503 (model overloaded) - both observed in production, both
    transient. Re-raises immediately on any other error, and re-raises once
    retries are exhausted.

    `on_retry`, if given, runs right before each retry sleep. Streaming
    callers use it to tell listeners to discard any partial output already
    emitted from the attempt that just failed, since a retry re-runs `fn`
    (and therefore re-emits everything) from scratch.
    """
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return fn()
        except genai_errors.APIError as exc:
            is_retryable = exc.code in _RETRYABLE_CODES
            if not is_retryable or attempt == _MAX_RETRIES:
                raise
            delay = _BASE_DELAY_SECONDS * (2**attempt) + random.uniform(0, 0.5)
            logger.warning(
                "Gemini returned %d (attempt %d/%d), retrying in %.1fs",
                exc.code,
                attempt + 1,
                _MAX_RETRIES,
                delay,
            )
            if on_retry:
                on_retry()
            time.sleep(delay)
    raise AssertionError("unreachable")  # loop always returns or raises
