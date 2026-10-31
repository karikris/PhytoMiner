"""Private per-invocation diagnostics; never publish failed scientific output."""

import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from .storage import atomic_json
from .models import ValidationError


class RunContext:
    def __init__(self, root, client, callback=None):
        self.id = uuid.uuid4().hex
        self.root = root
        self.client = client
        self.callback = callback
        self.started = time.monotonic()
        self.offset = len(client.metrics)
        self.counters = {
            "cache_hits": 0,
            "cache_misses": 0,
            "http_attempts": 0,
            "bytes": 0,
            "rows": 0,
        }
        self.timings = {}
        self.outcomes = []
        self.status = "running"
        self.reason: str | None = None
        self.started_at = datetime.now(timezone.utc).isoformat()

    def emit(self, event, **values):
        if self.callback:
            self.callback({"run_id": self.id, "event": event, **values})

    @contextmanager
    def stage(self, name):
        start = time.monotonic()
        self.emit("stage_started", stage=name)
        try:
            yield
        finally:
            self.timings[name] = self.timings.get(name, 0) + time.monotonic() - start
            self.emit("stage_finished", stage=name)

    def metrics(self):
        return {
            "run_id": self.id,
            **self.counters,
            "stages": dict(self.timings),
            "requests": list(self.client.metrics[self.offset :]),
        }

    def save(self):
        atomic_json(
            self.root / ".runs" / f"{self.id}.json",
            {
                "run_id": self.id,
                "status": self.status,
                "reason": self.reason,
                "started_at": self.started_at,
                "elapsed_seconds": time.monotonic() - self.started,
                "metrics": self.metrics(),
                "seed_outcomes": self.outcomes,
            },
        )


@contextmanager
def run_context(root, client, callback=None):
    if client.run is not None:
        raise ValidationError("Client already has an active run")
    run = RunContext(root, client, callback)
    client.run = run
    try:
        run.emit("run_started")
        yield run
        run.status = "complete"
    except BaseException as exc:
        run.status = "stopped"
        run.reason = type(exc).__name__
        raise
    finally:
        run.save()
        client.run = None
        run.emit("run_finished", status=run.status)
