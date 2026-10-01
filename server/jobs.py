# server/jobs.py
"""
Background jobs for slow work (generating minutes, fact checking).

The API starts a job and returns its id straight away; the frontend polls
GET /api/jobs/{id} for progress messages and the result.
"""
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

JOB_RETENTION_SECONDS = 3600
# Few workers on purpose: Gemini's free tier allows only a handful of requests per minute
MAX_CONCURRENT_JOBS = 2


class Job:
    def __init__(self, kind, owner_id):
        self.id = uuid.uuid4().hex
        self.kind = kind
        self.owner_id = owner_id
        self.status = "running"  # running | done | error
        self.steps = []
        self.done = 0
        self.total = None
        self.result = None
        self.error = None
        self.created_at = time.time()
        self.finished_at = None

    def report(self, message, done=None, total=None):
        """Record a progress message (and optionally step counts) for the UI"""
        self.steps.append({"message": message, "at": time.time()})
        if done is not None:
            self.done = done
        if total is not None:
            self.total = total

    def to_dict(self):
        return {
            "id": self.id, "kind": self.kind, "status": self.status, "steps": list(self.steps),
            "done": self.done, "total": self.total, "result": self.result, "error": self.error,
            "created_at": self.created_at, "finished_at": self.finished_at,
        }


class JobManager:
    def __init__(self, max_workers=MAX_CONCURRENT_JOBS):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job")
        self._jobs = {}
        self._lock = threading.Lock()

    def start(self, kind, owner_id, fn, *args, **kwargs):
        """
        Run fn(job, *args, **kwargs) in the background for a user; its return value becomes job.result

        Returns:
            Job
        """
        job = Job(kind, owner_id)
        with self._lock:
            self._prune()
            self._jobs[job.id] = job
        self._executor.submit(self._run, job, fn, args, kwargs)
        return job

    def get(self, job_id, owner_id):
        """The job, or None when it doesn't exist (any more) or another user started it"""
        with self._lock:
            job = self._jobs.get(job_id)
        return job if job and job.owner_id == owner_id else None

    @staticmethod
    def _run(job, fn, args, kwargs):
        try:
            job.result = fn(job, *args, **kwargs)
            job.status = "done"
        except Exception as e:  # every failure is reported to the UI through the job
            logger.exception("Job %s (%s) failed", job.id, job.kind)
            job.error = str(e) or type(e).__name__
            job.status = "error"
        finally:
            job.finished_at = time.time()

    def _prune(self):
        cutoff = time.time() - JOB_RETENTION_SECONDS
        for job_id in [j.id for j in self._jobs.values() if j.finished_at and j.finished_at < cutoff]:
            del self._jobs[job_id]


jobs = JobManager()
