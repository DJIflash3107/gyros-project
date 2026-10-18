import threading
import time

from app.services import background_job_service


def test_job_runs_in_background_and_exposes_status(monkeypatch):
    started = threading.Event()
    finish = threading.Event()

    def run_job(job_id, job_type, business_id, user_id, payload):
        started.set()
        assert finish.wait(timeout=2)
        return {'processed': True}

    monkeypatch.setattr('app.services.background_job_worker.run_job', run_job, raising=False)
    job = background_job_service.enqueue_job(None, 987654, 123, 'test', {})
    assert job['status'] in {'queued', 'processing'}
    assert started.wait(timeout=1)

    snapshot = background_job_service.get_job(None, job['id'], 987654)
    assert snapshot['status'] == 'processing'
    assert background_job_service.get_job(None, job['id'], 987655) is None

    finish.set()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        snapshot = background_job_service.get_job(None, job['id'], 987654)
        if snapshot['status'] == 'succeeded':
            break
        time.sleep(0.01)

    assert snapshot['status'] == 'succeeded'
    assert snapshot['result'] == {'processed': True}
    assert snapshot['completed_at'] is not None
