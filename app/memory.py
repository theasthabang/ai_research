"""
memory.py — Chat history storage with Redis primary / in-memory fallback.

Fixes vs original:
  - _redis_ok was mutated via globals() hack; now uses a module-level list [None] as
    a mutable cell — avoids the brittle globals() call while keeping the same logic.
  - get_memory() returned a bare session_id with no purpose; replaced with
    get_history() that returns the structured message list for callers that need it.
  - Trimming to last 10 messages is now a shared helper (_trim).
  - Type hints added throughout.
"""

import json
import logging
from typing import Optional

import redis

logger = logging.getLogger("ai-research-helper.memory")

EXPIRY_SECONDS = 7 * 24 * 60 * 60   # 7 days
MAX_MESSAGES   = 10


# ---------------------------------------------------------------------------
# Redis client setup
# ---------------------------------------------------------------------------

def _build_redis_client() -> redis.Redis:
    kwargs = dict(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=True,
        socket_connect_timeout=1.5,
    )
    try:
        return redis.Redis(protocol=2, **kwargs)   # RESP3 disabled → works on Redis < 6
    except TypeError:
        return redis.Redis(**kwargs)               # older redis-py without `protocol`


_redis_client = _build_redis_client()
_redis_ok: list[Optional[bool]] = [None]          # mutable cell; [True/False/None]


def _redis_available() -> bool:
    if _redis_ok[0] is not None:
        return _redis_ok[0]
    try:
        _redis_client.ping()
        _redis_ok[0] = True
        logger.info("Redis available — using Redis-backed memory.")
    except Exception as exc:
        _redis_ok[0] = False
        logger.warning("Redis unavailable (%s). Falling back to in-memory store.", exc)
    return _redis_ok[0]


# ---------------------------------------------------------------------------
# In-memory fallback
# ---------------------------------------------------------------------------

_in_memory: dict[str, list[dict]] = {}


def _trim(messages: list[dict]) -> list[dict]:
    return messages[-MAX_MESSAGES:] if len(messages) > MAX_MESSAGES else messages


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_message(session_id: str, role: str, content: str) -> None:
    """Append one message to the session history."""
    key = f"chat:{session_id}"

    if _redis_available():
        try:
            existing = _redis_client.get(key)
            messages = json.loads(existing) if existing else []
            messages.append({"role": role, "content": content})
            messages = _trim(messages)
            _redis_client.setex(key, EXPIRY_SECONDS, json.dumps(messages))
            return
        except Exception as exc:
            logger.warning("Redis save failed (%s); switching to in-memory.", exc)
            _redis_ok[0] = False

    messages = _in_memory.get(key, [])
    messages.append({"role": role, "content": content})
    _in_memory[key] = _trim(messages)


def load_messages(session_id: str) -> str:
    """Return chat history as a plain-text string for use in the agent prompt."""
    key = f"chat:{session_id}"
    messages: list[dict] = []

    if _redis_available():
        try:
            existing = _redis_client.get(key)
            if existing:
                messages = json.loads(existing)
        except Exception as exc:
            logger.warning("Redis load failed (%s); using in-memory.", exc)
            _redis_ok[0] = False
            messages = _in_memory.get(key, [])
    else:
        messages = _in_memory.get(key, [])

    lines: list[str] = []
    for msg in messages:
        role = "User" if msg["role"] == "human" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


def get_history(session_id: str) -> list[dict]:
    """Return raw message list (used by the /history endpoint)."""
    key = f"chat:{session_id}"
    if _redis_available():
        try:
            existing = _redis_client.get(key)
            return json.loads(existing) if existing else []
        except Exception:
            pass
    return _in_memory.get(key, [])


def clear_memory(session_id: str) -> None:
    """Delete all history for a session."""
    key = f"chat:{session_id}"
    if _redis_available():
        try:
            _redis_client.delete(key)
        except Exception as exc:
            logger.warning("Redis delete failed (%s).", exc)
    _in_memory.pop(key, None)