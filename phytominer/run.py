"""Private per-invocation diagnostics; never publish failed scientific output."""

import time
import uuid
import threading
from contextvars import ContextVar
from .limits import RunLimits
from .models import BudgetExceededError, DeadlineExceededError
from contextlib import contextmanager
from datetime import datetime, timezone
from .storage import atomic_json
from .models import ValidationError


CURRENT_RUN: ContextVar = ContextVar("phytominer_run", default=None)


class RunContext:
    def __init__(self, root, client, callback=None, limits=None):
        self.limits = limits or RunLimits()
        self.genes = set()
        self.guard = threading.Lock()
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

    def check(self):
        if (
            self.limits.max_seconds is not None
            and time.monotonic() - self.started >= self.limits.max_seconds
        ):
            raise DeadlineExceededError("Invocation deadline expired")

    def track_genes(self, identities):
        self.check()
        self.genes.update(identities)
        if (
            self.limits.max_genes is not None
            and len(self.genes) > self.limits.max_genes
        ):
            raise BudgetExceededError("max_genes", len(self.genes))

    def before_http(self):
        with self.guard:
            self.check()
            count = self.counters["http_attempts"] + 1
            if (
                self.limits.max_requests is not None
                and count > self.limits.max_requests
            ):
                raise BudgetExceededError("max_requests", count)
            self.counters["http_attempts"] = count

    def check_output(self, directory):
        self.check()
        size = sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())
        if (
            self.limits.max_output_bytes is not None
            and size > self.limits.max_output_bytes
        ):
            raise BudgetExceededError("max_output_bytes", size)

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
def run_context(root, client, callback=None, limits=None):
    if client.run is not None:
        raise ValidationError("Client already has an active run")
    run = RunContext(root, client, callback, limits)
    token = CURRENT_RUN.set(run)
    client.run = run
    try:
        run.emit("run_started")
        yield run
        run.status = "complete"
    except BaseException as exc:
        run.status = "stopped"
        run.reason = type(exc).__name__
        for seed in run.outcomes:
            if seed["status"] == "not_processed":
                seed["status"] = "failed"
        raise
    finally:
        run.save()
        client.run = None
        CURRENT_RUN.reset(token)
        run.emit("run_finished", status=run.status)
