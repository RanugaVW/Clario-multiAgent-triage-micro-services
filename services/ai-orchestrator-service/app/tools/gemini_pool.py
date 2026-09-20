"""Round-robins every configured Gemini API key so one key's per-minute or
per-day quota doesn't stall classification, drafting, or judging.

Every call site that used to do ``client = genai.Client()`` (reading only
GEMINI_API_KEY) now does ``client = gemini_client()`` instead: with a single
key configured, behaviour is unchanged (a one-client "pool" is exactly a
fresh Client() each time); with GEMINI_API_KEY2, GEMINI_API_KEY3, ... also
set, each call gets the next key in round-robin order, so an existing retry
loop that just calls the same function again already gets a different key
on its next attempt, without needing its own retry logic changed.
"""

from __future__ import annotations

import itertools
import os
import threading

from google import genai

_KEY_ENV_NAMES = [
    "GEMINI_API_KEY", "GEMINI_API_KEY2", "GEMINI_API_KEY3", "GEMINI_API_KEY4",
    "GEMINI_API_KEY5", "GEMINI_API_KEY6", "GEMINI_API_KEY7", "GEMINI_API_KEY8", "GEMINI_API_KEY9",
]

_lock = threading.Lock()
_clients: list[genai.Client] | None = None
_cycle: "itertools.cycle[int] | None" = None
_dead: set[int] = set()


def _init() -> None:
    global _clients, _cycle
    if _clients is not None:
        return
    keys = [os.environ[name] for name in _KEY_ENV_NAMES if os.environ.get(name)]
    # No key at all still works exactly as genai.Client() always did: it
    # reads GEMINI_API_KEY (or GOOGLE_API_KEY) from the environment itself.
    _clients = [genai.Client(api_key=key) for key in keys] if keys else [genai.Client()]
    _cycle = itertools.cycle(range(len(_clients)))


def gemini_client() -> genai.Client:
    """The next client in the round-robin pool, skipping any key already
    marked dead this run (see mark_dead)."""
    with _lock:
        _init()
        assert _clients is not None and _cycle is not None
        for _ in range(len(_clients)):
            idx = next(_cycle)
            if idx not in _dead:
                return _clients[idx]
        # Every key marked dead (shouldn't normally happen) - keep serving
        # something rather than raising, since a suspended key can still
        # sometimes succeed and callers already have their own retry logic.
        return _clients[idx]


def mark_dead(client: genai.Client) -> None:
    """Permanently remove a key from rotation for the rest of this process -
    for an error like CONSUMER_SUSPENDED that will never succeed, so
    retries stop burning attempts (and the ainvoke timeout budget) on a key
    that cannot recover mid-run."""
    with _lock:
        _init()
        assert _clients is not None
        for i, c in enumerate(_clients):
            if c is client:
                _dead.add(i)
                return


def pool_size() -> int:
    with _lock:
        _init()
        assert _clients is not None
        return len(_clients)


def is_rate_limited(exc: BaseException) -> bool:
    """True for a 429 / RESOURCE_EXHAUSTED error, whether it's a per-minute
    limit (worth trying a different key immediately) or a per-day quota."""
    text = str(exc)
    return "RESOURCE_EXHAUSTED" in text or "429" in text


def is_permanently_dead(exc: BaseException) -> bool:
    """True for an error that will never succeed on retry (key suspended,
    revoked, or otherwise rejected outright) - as opposed to a rate limit,
    which is temporary and the key should stay in rotation for."""
    text = str(exc)
    return "CONSUMER_SUSPENDED" in text or "PERMISSION_DENIED" in text or "API_KEY_INVALID" in text
