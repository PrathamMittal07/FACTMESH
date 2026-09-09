"""Shared retry + pacing helper for Gemini API calls.

Free-tier API keys are aggressively rate-limited (HTTP 429). Every LLM call
in the pipeline goes through generate_with_retry, which:
  1. Sleeps LLM_BATCH_DELAY_SEC before each call (stays under req/min limits).
  2. Retries retryable errors (429 / 503 / overloaded) with exponential
     backoff, honouring the server's "retry in Ns" hint when present.
  3. Falls back to GEMINI_API_KEY_2 if primary quota is exhausted.
"""

import logging
import re
import time
import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)

_RETRY_HINT_RE = re.compile(r"retry in ([\d.]+)s", re.IGNORECASE)

# Track which key we are currently using globally
_active_key_index = 1

def switch_to_fallback_key():
    global _active_key_index
    if _active_key_index == 1 and settings.gemini_api_key_2:
        logger.warning("Primary API key exhausted. Switching to fallback GEMINI_API_KEY_2 and gemini-3.5-flash-lite...")
        genai.configure(api_key=settings.gemini_api_key_2)
        settings.gemini_model = "gemini-3.5-flash-lite"
        _active_key_index = 2
        return True
    return False


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
    """Call model.generate_content(prompt) with pacing + backoff retries.

    Raises the last exception if all attempts fail.
    """
    max_attempts = max(1, settings.llm_max_retries)
    base = max(1.0, settings.llm_retry_base_sec)

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        # Hot-swap model if settings changed (e.g., fallback triggered)
        current_name = getattr(model, "model_name", "")
        if current_name != settings.gemini_model and current_name != f"models/{settings.gemini_model}":
            logger.info(f"Rebuilding model instance to use {settings.gemini_model} (was {current_name})")
            model = genai.GenerativeModel(
                model_name=settings.gemini_model,
                system_instruction=getattr(model, "_system_instruction", None),
                generation_config=getattr(model, "_generation_config", None),
                safety_settings=getattr(model, "_safety_settings", None)
            )
        pace()
        try:
            return model.generate_content(prompt)
        except Exception as exc:  # noqa: BLE001 - must catch SDK errors
            last_exc = exc
            if not _is_retryable(exc) or attempt == max_attempts:
                raise
            if "quota" in str(exc).lower():
                # For daily quota exhaustion, fail immediately after checking keys
                if not switch_to_fallback_key():
                    logger.error("All API keys exhausted their quotas. Failing immediately.")
                    raise exc

            hint = _RETRY_HINT_RE.search(str(exc))
            if hint and float(hint.group(1)) > 30 and attempt >= 2:
                # Server asks to wait >30s twice in a row: the quota window
                # itself is exhausted (not a per-minute blip). 
                # Try fallback key before giving up.
                if switch_to_fallback_key():
                    continue # Retry immediately with new key
                
                logger.error(
                    f"LLM quota window exhausted (server asked to wait "
                    f"{hint.group(1)}s repeatedly). Aborting retries."
                )
                raise
            
            # If it's a huge wait (>30s) on attempt 1, might also be hard quota exhausted.
            # We can also attempt a key swap here if the wait is very large.
            if hint and float(hint.group(1)) > 30:
                if switch_to_fallback_key():
                    continue # Try new key

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