from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from typing import Any

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='background-job')
_jobs: dict[int, dict[str, Any]] = {}
_counter = 1
_lock = Lock()
TERMINAL_STATUSES = {'succeeded', 'failed'}


def enqueue_job(db, business_id: int, user_id: int, job_type: str, payload: dict[str, Any]):
    global _counter
    now = datetime.now(timezone.utc)
    with _lock:
        job_id = _counter
        _counter += 1
        job = {'id': job_id, 'business_id': business_id, 'requested_by_user_id': user_id,
               'job_type': job_type, 'payload': payload, 'status': 'queued',
               'progress': {'step': 'queued', 'message': 'Job queued'}, 'progress_version': 0,
               'result': None, 'error': None, 'created_at': now, 'started_at': None,
               'completed_at': None}
        _jobs[job_id] = job
    _executor.submit(_execute, job_id)
    return job


def _execute(job_id: int):
    with _lock:
        job = _jobs[job_id]
        job['status'] = 'processing'
        job['started_at'] = datetime.now(timezone.utc)
        job['progress'] = {'step': 'starting', 'message': 'Job started'}
        job['progress_version'] += 1
        args = (job_id, job['job_type'], job['business_id'], job['requested_by_user_id'], job['payload'])
    try:
        from app.services.background_job_worker import run_job
        result = run_job(*args)
        update_job(None, job_id, result=result, status='succeeded', progress={'step': 'complete', 'message': 'Job completed'})
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception('Background job %s failed', job_id)
        update_job(None, job_id, error=getattr(exc, 'message', 'Background job failed'), status='failed', progress={'step': 'failed', 'message': 'Background job failed'})


def get_job(db, job_id: int, business_id: int):
    with _lock:
        job = _jobs.get(job_id)
        if not job or job['business_id'] != business_id:
            return None
        return {key: value for key, value in job.items() if key not in {'payload', 'requested_by_user_id'}}


def update_job(db, job_id: int, *, progress=None, result=None, error=None, status=None):
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        if progress is not None:
            job['progress'] = progress
            job['progress_version'] += 1
        if result is not None:
            job['result'] = result
        if error is not None:
            job['error'] = error
        if status is not None:
            job['status'] = status
            if status in TERMINAL_STATUSES:
                job['completed_at'] = datetime.now(timezone.utc)
