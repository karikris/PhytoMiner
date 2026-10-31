"""Writer lifecycle shared by every workflow."""

from .maintenance import maintenance_lock
from contextlib import contextmanager
import os
from .models import ValidationError


@contextmanager
def _run_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".writer.lock"
    try:
        with maintenance_lock(root):
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValidationError(
            "Dataset has an active writer; after a crash remove .writer.lock only after confirming the writer stopped"
        ) from exc
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)
