"""
Shared Gemini client plus a retry/backoff wrapper for 429s.

Gemini's free tier has tight per-minute rate limits, so every call in this
codebase (embeddings, and every agent's chat call) should go through
`call_with_backoff` rather than calling the client directly.
"""
import logging
import random
import time
from typing import Callable, Optional, TypeVar

from google import genai
from google.genai import errors as genai_errors

from app.config import settings

logger = logging.getLogger("pdf-rag")

client = genai.Client(api_key=settings.GEMINI_API_KEY)

_MAX_RETRIES = 4
_BASE_DELAY_SECONDS = 1.0

T = TypeVar("T")


def call_with_backoff(fn: Callable[[], T], on_retry: Optional[Callable[[], None]] = None) -> T:
    """
    Calls `fn`, retrying with exponential backoff + jitter if Gemini responds
    with 429 (rate limited). Re-raises immediately on any other error, and
    re-raises the 429 once retries are exhausted.

    `on_retry`, if given, runs right before each retry sleep. Streaming
    callers use it to tell listeners to discard any partial output already
    emitted from the attempt that just failed, since a retry re-runs `fn`
    (and therefore re-emits everything) from scratch.
    """
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return fn()
        except genai_errors.ClientError as exc:
            is_rate_limited = exc.code == 429
            if not is_rate_limited or attempt == _MAX_RETRIES:
                raise
            delay = _BASE_DELAY_SECONDS * (2**attempt) + random.uniform(0, 0.5)
            logger.warning(
                "Gemini rate limited (attempt %d/%d), retrying in %.1fs",
                attempt + 1,
                _MAX_RETRIES,
                delay,
            )
            if on_retry:
                on_retry()
            time.sleep(delay)
    raise AssertionError("unreachable")  # loop always returns or raises
