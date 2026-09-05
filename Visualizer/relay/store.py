"""In-memory, capped event store for the standalone ticket pipeline tracer.
Never a system of record - see Global Constraints in the implementation plan."""

from __future__ import annotations

import time
from collections import OrderedDict

_ONE_HOUR = 3600


class TraceStore:
    def __init__(self, max_tickets: int = 50, max_age_seconds: float = _ONE_HOUR) -> None:
        self._max_tickets = max_tickets
        self._max_age_seconds = max_age_seconds
        # OrderedDict so the least-recently-updated ticket is always first,
        # letting eviction be a cheap popitem(last=False).
        self._events: OrderedDict[str, list[dict]] = OrderedDict()

    def add(self, event: dict) -> None:
        ticket_id = event["ticket_id"]
        if ticket_id in self._events:
            self._events.move_to_end(ticket_id)
        else:
            self._events[ticket_id] = []
            if len(self._events) > self._max_tickets:
                self._events.popitem(last=False)
        self._events.setdefault(ticket_id, [])
        self._events[ticket_id].append(event)
        self._prune(ticket_id)

    def _prune(self, ticket_id: str) -> None:
        cutoff = time.time() - self._max_age_seconds
        self._events[ticket_id] = [e for e in self._events[ticket_id] if e["timestamp"] >= cutoff]

    def events_for(self, ticket_id: str) -> list[dict]:
        return list(self._events.get(ticket_id, []))

    def merge_correlation(self, correlation_id: str, ticket_id: str) -> None:
        """Fold a correlation-id-keyed ticket's events into its real ticket_id
        once that's known (from ticket-core-service's "persisted" event, which
        carries both). No-op if they're already the same key or nothing is
        filed under the correlation id."""
        if correlation_id == ticket_id or correlation_id not in self._events:
            return
        correlation_events = self._events.pop(correlation_id)
        self._events.setdefault(ticket_id, [])
        self._events[ticket_id] = correlation_events + self._events[ticket_id]
        self._events.move_to_end(ticket_id)

    def tickets(self) -> list[dict]:
        result = []
        for ticket_id, events in self._events.items():
            if not events:
                continue
            result.append({
                "ticket_id": ticket_id,
                "latest_step": events[-1]["step"],
                "latest_status": events[-1]["status"],
                "first_seen": events[0]["timestamp"],
                "last_seen": events[-1]["timestamp"],
            })
        return result
