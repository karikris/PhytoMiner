"""Process-local endpoint coordination; sessions remain client-owned."""

import threading
import weakref
from urllib.parse import urlsplit, urlunsplit


class EndpointScheduler:
    def __init__(self):
        self.condition = threading.Condition()
        self.clients = weakref.WeakSet()
        self.active = 0
        self.next_start = 0.0
        self.cooldown = 0.0
        self.serial = False

    @property
    def workers(self):
        return (
            1
            if self.serial
            else min((c.config.max_workers for c in self.clients), default=1)
        )

    @property
    def rate(self):
        return min((c.config.requests_per_second for c in self.clients), default=1.0)


_registry = weakref.WeakValueDictionary()
_guard = threading.Lock()


def register(client):
    url = urlsplit(client.config.endpoint)
    key = urlunsplit(
        (url.scheme.lower(), url.netloc.lower(), url.path.rstrip("/"), url.query, "")
    )
    with _guard:
        scheduler = _registry.get(key)
        if scheduler is None:
            scheduler = EndpointScheduler()
            _registry[key] = scheduler
        with scheduler.condition:
            scheduler.clients.add(client)
        return scheduler
