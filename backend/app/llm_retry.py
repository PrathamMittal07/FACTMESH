"""Shared retry + pacing helper for Gemini API calls.

Free-tier API keys are aggressively rate-limited (HTTP 429). Every LLM call
in the pipeline goes through `generate_with_retry`, which:
  1. Sleeps `LLM_BATCH_DELAY_SEC` before each call (stays under req/min limits).
  2. Retries retryable errors (429 / 503 / overloaded) with exponential
     backoff, honouring the server's "retry in Ns" hint when present.
"""

import logging
import re
import time

from app.config import settings

logger = logging.getLogger(__name__)

_RETRY_HINT_RE = re.compile(r"retry in ([\d.]+)s", re.IGNORECASE)


def _is_retryable(exc: Exception) -> bool:
    """True if the exception looks like a transient rate-limit/server error."""
    try:
        from google.api_core import exceptions as gexc

        if isinstance(
            exc,
            (
                gexc.ResourceExhausted,  # 429
                gexc.ServiceUnavailable,  # 503
                gexc.DeadlineExceeded,
                gexc.InternalServerError,
            ),
        ):
            return True
    except ImportError:
        pass
    msg = str(exc).lower()
    return any(
        token in msg
        for token in ("429", "quota", "rate", "overloaded", "503", "timeout", "temporarily")
    )


def pace() -> None:
    """Sleep between LLM calls to respect per-minute rate limits."""
    delay = settings.llm_batch_delay_sec
    if delay > 0:
        time.sleep(delay)


def generate_with_retry(model, prompt: str):
    """Call `model.generate_content(prompt)` with pacing + backoff retries.

    Raises the last exception if all attempts fail.
    """
    max_attempts = max(1, settings.llm_max_retries)
    base = max(1.0, settings.llm_retry_base_sec)

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        pace()
        try:
            return model.generate_content(prompt)
        except Exception as exc:  # noqa: BLE001 - must catch SDK errors
            last_exc = exc
            if not _is_retryable(exc) or attempt == max_attempts:
                raise
            hint = _RETRY_HINT_RE.search(str(exc))
            if hint and float(hint.group(1)) > 30 and attempt >= 2:
                # Server asks to wait >30s twice in a row: the quota window
                # itself is exhausted (not a per-minute blip). Fail fast
                # instead of burning minutes on futile retries.
                logger.error(
                    f"LLM quota window exhausted (server asked to wait "
                    f"{hint.group(1)}s repeatedly). Aborting retries."
                )
                raise
            wait = float(hint.group(1)) + 2.0 if hint else base * (2 ** (attempt - 1))
            wait = min(wait, 300.0)
            logger.warning(
                f"LLM rate-limited (attempt {attempt}/{max_attempts}), "
                f"waiting {wait:.1f}s: {str(exc)[:150]}"
            )
            time.sleep(wait)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("generate_with_retry: no attempts made")
