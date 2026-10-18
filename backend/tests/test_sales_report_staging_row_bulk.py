import pytest


def _setup_submission(client, headers):
    business = client.post("/api/v1/businesses", json={"name": "Bulk Staging Biz"}, headers=headers).json()["data"]["business"]
    business_id = business["id"]
    branch_id = client.post(f"/api/v1/businesses/{business_id}/branches", json={"name": "Main Branch"}, headers=headers).json()["data"]["branch"]["id"]
    submission_id = client.post(
        f"/api/v1/businesses/{business_id}/sales_report_submissions",
        json={"branch_id": branch_id, "input_method": "spreadsheet", "report_period_type": "daily", "coverage_start": "2026-10-01", "coverage_end": "2026-10-03"},
        headers=headers,
    ).json()["data"]["submission"]["id"]
    return business_id, submission_id


@pytest.mark.parametrize("method", ["patch", "post"])
def test_bulk_update_is_queued(client, auth_user, method, monkeypatch):
    from app.services import background_job_service

    class DeferredExecutor:
        def submit(self, *args, **kwargs):
            return None

    monkeypatch.setattr(background_job_service, '_executor', DeferredExecutor())
    headers = auth_user["headers"]
    business_id, submission_id = _setup_submission(client, headers)
    response = getattr(client, method)(
        f"/api/v1/sales_report_submissions/{submission_id}/staging_rows/bulk",
        json={"apply_to_all": True, "review_status": "ready"},
        headers=headers,
    )
    assert response.status_code == 202
    job = response.json()["data"]
    assert job["status"] == "queued"
    assert job["status_url"] == f"/api/v1/businesses/{business_id}/jobs/{job['job_id']}"
    status = client.get(job["status_url"], headers=headers)
    assert status.status_code == 200
    assert status.json()["data"]["job"]["status"] == "queued"


def test_bulk_update_validation_errors(client, auth_user):
    headers = auth_user["headers"]
    _, submission_id = _setup_submission(client, headers)
    missing_selection = client.patch(
        f"/api/v1/sales_report_submissions/{submission_id}/staging_rows/bulk",
        json={"review_status": "ready"},
        headers=headers,
    )
    assert missing_selection.status_code == 422
    missing_update = client.patch(
        f"/api/v1/sales_report_submissions/{submission_id}/staging_rows/bulk",
        json={"apply_to_all": True},
        headers=headers,
    )
    assert missing_update.status_code == 422
    missing_submission = client.patch(
        "/api/v1/sales_report_submissions/999999/staging_rows/bulk",
        json={"apply_to_all": True, "review_status": "ready"},
        headers=headers,
    )
    assert missing_submission.status_code == 404
