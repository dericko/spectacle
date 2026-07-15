import threading
from typing import Callable, Protocol

class JobQueue(Protocol):
    def submit(self, fn: Callable[[], None]) -> None: ...

class ThreadJobQueue:
    """Current execution mechanism, behind an explicit seam. Swap this for a
    Celery/Cloud Tasks-backed implementation later WITHOUT touching
    RunManager's orchestration logic."""
    def submit(self, fn: Callable[[], None]) -> None:
        threading.Thread(target=fn, daemon=True).start()
