import threading
import time
from typing import Dict, Optional


class ProgressTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: Dict[str, dict] = {}

    def _cleanup_stale_locked(self, now: float) -> None:
        stale_ids = [
            job_id
            for job_id, data in self._jobs.items()
            if now - data.get("updated_at", now) > 900
        ]
        for job_id in stale_ids:
            del self._jobs[job_id]

    def start(self, job_id: str) -> None:
        now = time.time()
        with self._lock:
            self._cleanup_stale_locked(now)
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "running",
                "progress": 5,
                "stage": "Preparing conversion",
                "error": None,
                "updated_at": now,
            }

    def update(self, job_id: str, progress: int, stage: str) -> None:
        now = time.time()
        with self._lock:
            if job_id not in self._jobs:
                self.start(job_id)
            self._jobs[job_id].update(
                {
                    "progress": max(0, min(progress, 100)),
                    "stage": stage,
                    "updated_at": now,
                }
            )

    def complete(self, job_id: str, stage: str = "Completed") -> None:
        now = time.time()
        with self._lock:
            if job_id not in self._jobs:
                self.start(job_id)
            self._jobs[job_id].update(
                {
                    "status": "completed",
                    "progress": 100,
                    "stage": stage,
                    "updated_at": now,
                }
            )

    def fail(self, job_id: str, error: str) -> None:
        now = time.time()
        with self._lock:
            if job_id not in self._jobs:
                self.start(job_id)
            self._jobs[job_id].update(
                {
                    "status": "failed",
                    "stage": "Failed",
                    "error": error,
                    "updated_at": now,
                }
            )

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            return dict(job)


progress_tracker = ProgressTracker()
