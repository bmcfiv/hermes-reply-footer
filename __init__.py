"""reply-footer: re-state a standing reply-format rule on every interactive turn.

Long system prompts bury format rules ("end every reply with ...") far from the end of the context, so
models drift on them over a long session. This plugin adds a short, user-chosen reminder to the context of
each user turn (``pre_llm_call`` -> ``{"context": ...}``, which Hermes appends to the user message, never
the system prompt) and can check long replies against a regular expression (``post_llm_call``), logging
OK / MISS so the miss rate is measurable.

Everything is opt-in and read from ``plugins.entries.reply-footer.settings``:

* ``reminder``      text injected each turn; empty (default) = the plugin does nothing
* ``skip_sources``  platforms that get neither reminder nor check (default cron, subagent, batch, webhook)
* ``check_pattern`` regex a reply must match; empty (default) = no check
* ``min_chars``     replies shorter than this are not checked (default 400)
* ``log``           write OK/MISS lines to ``<HERMES_HOME>/logs/reply_footer.log`` (default false)

Both hooks fail open: an error is logged and the turn proceeds unchanged.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger(__name__)

DEFAULT_SKIP_SOURCES = ("cron", "subagent", "batch", "webhook")
DEFAULT_MIN_CHARS = 400
LOG_NAME = "reply_footer.log"


def _home():
    from hermes_constants import get_hermes_home

    return get_hermes_home()


def _skip_sources(raw: Any) -> frozenset[str]:
    if raw is None:
        raw = DEFAULT_SKIP_SOURCES
    if isinstance(raw, str):
        raw = [p for p in re.split(r"[,\s]+", raw) if p]
    return frozenset(str(s).strip().lower() for s in raw if str(s).strip())


def _skipped(skip: frozenset[str], platform: Any, parent_session_id: Any = "") -> bool:
    if str(platform or "").strip().lower() in skip:
        return True
    return "subagent" in skip and bool(parent_session_id)


def _int(raw: Any, default: int) -> int:
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return default


def register(ctx) -> None:
    get: Callable[[str, Any], Any] = ctx.get_config
    bad_pattern: set[str] = set()

    def pre_llm_call(platform=None, parent_session_id="", **_kw):
        try:
            reminder = str(get("reminder", "") or "").strip()
            if not reminder:
                return None
            if _skipped(_skip_sources(get("skip_sources", None)), platform, parent_session_id):
                return None
            return {"context": reminder}
        except Exception:
            logger.warning("reply-footer pre_llm_call failed open", exc_info=True)
            return None

    def post_llm_call(session_id="", platform=None, assistant_response=None, **_kw):
        try:
            pattern = str(get("check_pattern", "") or "")
            if not pattern or not get("log", False) or not assistant_response:
                return None
            if _skipped(_skip_sources(get("skip_sources", None)), platform):
                return None
            text = str(assistant_response)
            if len(text) < _int(get("min_chars", DEFAULT_MIN_CHARS), DEFAULT_MIN_CHARS):
                return None
            try:
                found = re.search(pattern, text, re.MULTILINE) is not None
            except re.error as exc:
                if pattern not in bad_pattern:
                    bad_pattern.add(pattern)
                    logger.warning("reply-footer: check_pattern is not a valid regex (%s); check skipped", exc)
                return None
            log_dir = _home() / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            with (log_dir / LOG_NAME).open("a", encoding="utf-8") as fh:
                fh.write(
                    f"{datetime.now().isoformat(timespec='seconds')} {'OK' if found else 'MISS'} "
                    f"platform={platform or ''} session={session_id}\n"
                )
        except Exception:
            logger.warning("reply-footer post_llm_call failed open", exc_info=True)
        return None

    ctx.register_hook("pre_llm_call", pre_llm_call)
    ctx.register_hook("post_llm_call", post_llm_call)
