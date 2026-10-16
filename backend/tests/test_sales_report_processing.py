import csv
import io
import json
from unittest.mock import AsyncMock, patch
import openpyxl
import pytest

from app.models.schemas.ai import AIModelInfo
from app.configs.settings import settings


@pytest.fixture(autouse=True)
def disable_semantic_mapping_in_legacy_tests(monkeypatch):
    monkeypatch.setattr(settings, "SEMANTIC_MAPPING_ENABLED", False)



def _create_test_xlsx(headers: list, rows: list) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _create_test_csv(headers: list, rows: list) -> bytes:
    sio = io.StringIO()
    writer = csv.writer(sio)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return sio.getvalue().encode("utf-8")


def _setup_test_data(client, headers):
    biz_resp = client.post("/api/v1/businesses", json={"name": "Processing Test Biz"}, headers=headers)
    assert biz_resp.status_code == 201
    biz_id = biz_resp.json()["data"]["business"]["id"]

    branch_resp = client.post(f"/api/v1/businesses/{biz_id}/branches", json={"name": "Main Branch"}, headers=headers)
    assert branch_resp.status_code == 201
    branch_id = branch_resp.json()["data"]["branch"]["id"]

    prod_resp = client.post(f"/api/v1/businesses/{biz_id}/products", json={"name": "Beef Gyros", "base_unit": "portion"}, headers=headers)
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["data"]["product"]["id"]

    # Add alias "gyro sapi"
    alias_resp = client.post(
        f"/api/v1/businesses/{biz_id}/product_aliases",
        json={"product_id": prod_id, "alias_name": "gyro sapi"},
        headers=headers,
    )
    assert alias_resp.status_code == 201

    return biz_id, branch_id, prod_id


# 1. test_spreadsheet_xlsx_happy_path
def test_spreadsheet_xlsx_happy_path(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id = _setup_test_data(client, headers)

    xlsx_bytes = _create_test_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue"],
        rows=[
            ["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 25, 1250000],
            ["gyro sapi", branch_id, "2026-10-02", "2026-10-02", "daily", 30, 1500000],
        ],
    )

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-02",
            "branch_id": branch_id,
        },
        files={"file": ("sales.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["submission"]["status"] == "reviewed"
    assert body["summary"]["total_rows"] == 2
    assert body["summary"]["ready_rows"] == 2
    assert body["summary"]["needs_correction_rows"] == 0


# 2. test_spreadsheet_csv_happy_path
def test_spreadsheet_csv_happy_path(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id = _setup_test_data(client, headers)

    csv_bytes = _create_test_csv(
        headers=["nama_produk", "branch_id", "period_start", "period_end", "granularity", "sold_qty", "recorded_revenue"],
        rows=[
            ["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 15, 750000],
        ],
    )

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("sales.csv", csv_bytes, "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["summary"]["total_rows"] == 1
    assert body["summary"]["ready_rows"] == 1


# 3. test_spreadsheet_malformed_file
def test_spreadsheet_malformed_file(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, _ = _setup_test_data(client, headers)

    corrupt_bytes = b"corrupted file not an excel content \x00\x01\x02\xff"
    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("bad.xlsx", corrupt_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["error_code"] == "ERR-RPT-001"


# 4. test_spreadsheet_empty_file
def test_spreadsheet_empty_file(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, _ = _setup_test_data(client, headers)

    # Empty XLSX (headers only, no rows)
    empty_xlsx = _create_test_xlsx(
        headers=["Product", "Sold Qty"],
        rows=[],
    )
    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("empty.xlsx", empty_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["error_code"] == "ERR-RPT-002"


# 5. test_spreadsheet_file_too_large
def test_spreadsheet_file_too_large(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, _ = _setup_test_data(client, headers)

    fake_large_bytes = b"0" * (10 * 1024 * 1024 + 1)
    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("big.xlsx", fake_large_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["error_code"] == "ERR-RPT-003"


# 6. test_spreadsheet_wrong_mime_type
def test_spreadsheet_wrong_mime_type(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, _ = _setup_test_data(client, headers)

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("photo.png", b"\x89PNG\r\n\x1a\nfakeimage", "image/png")},
        headers=headers,
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["error_code"] == "ERR-RPT-004"


# 7. test_spreadsheet_duplicate_sha256
def test_spreadsheet_duplicate_sha256(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, _ = _setup_test_data(client, headers)

    xlsx_bytes = _create_test_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty"],
        rows=[["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 10]],
    )

    # First upload
    resp1 = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("first.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp1.status_code == 201

    # Second upload with identical bytes
    resp2 = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("second.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp2.status_code == 409
    body = resp2.json()
    assert body["error"]["error_code"] == "ERR-RPT-005"


# 8. test_spreadsheet_unresolvable_product
def test_spreadsheet_unresolvable_product(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, _ = _setup_test_data(client, headers)

    xlsx_bytes = _create_test_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty"],
        rows=[["Unknown Mystery Product XYZ", branch_id, "2026-10-01", "2026-10-01", "daily", 10]],
    )

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("unresolved.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["summary"]["needs_correction_rows"] == 1
    assert any(i["issue_code"] == "RPT-VAL-001" for i in body["issues"])


# 9. test_spreadsheet_partial_parse_errors
def test_spreadsheet_partial_parse_errors(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, _ = _setup_test_data(client, headers)

    xlsx_bytes = _create_test_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty"],
        rows=[
            ["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 10],
            ["Ghost Item", branch_id, "2026-10-01", "2026-10-01", "daily", 5],
        ],
    )

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("partial.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["summary"]["total_rows"] == 2
    assert body["summary"]["ready_rows"] == 1
    assert body["summary"]["needs_correction_rows"] == 1


# 10. test_batch_form_happy_path
def test_batch_form_happy_path(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id = _setup_test_data(client, headers)

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/batch_form",
        json={
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-02",
            "branch_id": branch_id,
            "rows": [
                {
                    "raw_product_name": "Beef Gyros",
                    "branch_id": branch_id,
                    "product_id": prod_id,
                    "period_start": "2026-10-01",
                    "period_end": "2026-10-01",
                    "granularity": "daily",
                    "sold_qty": "20.000",
                    "recorded_revenue": "1000000.00",
                },
                {
                    "raw_product_name": "gyro sapi",
                    "branch_id": branch_id,
                    "period_start": "2026-10-02",
                    "period_end": "2026-10-02",
                    "granularity": "daily",
                    "sold_qty": "15.000",
                    "recorded_revenue": "750000.00",
                },
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["submission"]["status"] == "reviewed"
    assert body["summary"]["total_rows"] == 2
    assert body["summary"]["ready_rows"] == 2


# 11. test_batch_form_invalid_branch
def test_batch_form_invalid_branch(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id = _setup_test_data(client, headers)

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/batch_form",
        json={
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "rows": [
                {
                    "raw_product_name": "Beef Gyros",
                    "branch_id": 999999,
                    "product_id": prod_id,
                    "period_start": "2026-10-01",
                    "period_end": "2026-10-01",
                    "granularity": "daily",
                    "sold_qty": "10",
                }
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["summary"]["needs_correction_rows"] == 1
    assert any(i["issue_code"] == "RPT-VAL-002" for i in body["issues"])


# 12. test_batch_form_invalid_dates
def test_batch_form_invalid_dates(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id = _setup_test_data(client, headers)

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/batch_form",
        json={
            "report_period_type": "daily",
            "coverage_start": "2026-10-05",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
            "rows": [
                {
                    "raw_product_name": "Beef Gyros",
                    "branch_id": branch_id,
                    "period_start": "2026-10-05",
                    "period_end": "2026-10-01",
                    "granularity": "daily",
                }
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 422


# 13. test_batch_form_negative_quantities
def test_batch_form_negative_quantities(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id = _setup_test_data(client, headers)

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/batch_form",
        json={
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
            "rows": [
                {
                    "raw_product_name": "Beef Gyros",
                    "branch_id": branch_id,
                    "period_start": "2026-10-01",
                    "period_end": "2026-10-01",
                    "granularity": "daily",
                    "sold_qty": "-5",
                }
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["summary"]["needs_correction_rows"] == 1
    assert any(i["issue_code"] == "RPT-VAL-006" for i in body["issues"])


# 14. test_batch_form_intra_submission_duplicates
def test_batch_form_intra_submission_duplicates(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id = _setup_test_data(client, headers)

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/batch_form",
        json={
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
            "rows": [
                {
                    "raw_product_name": "Beef Gyros",
                    "branch_id": branch_id,
                    "period_start": "2026-10-01",
                    "period_end": "2026-10-01",
                    "granularity": "daily",
                    "sold_qty": "10",
                },
                {
                    "raw_product_name": "Beef Gyros",
                    "branch_id": branch_id,
                    "period_start": "2026-10-01",
                    "period_end": "2026-10-01",
                    "granularity": "daily",
                    "sold_qty": "15",
                },
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert any(i["issue_code"] == "RPT-VAL-007" for i in body["issues"])


# 15. test_photo_no_vision_model
@patch("app.handlers.sales_report_submission_handler.list_models")
def test_photo_no_vision_model(mock_list_models, client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, _ = _setup_test_data(client, headers)

    # Return only non-vision models
    mock_list_models.return_value = [
        AIModelInfo(id="DeepSeek-V4-Flash", supports_streaming=True, supports_tools=True, supports_vision=False, supports_reasoning=False)
    ]

    with patch.object(settings, "VISION_MODEL_OVERRIDE", ""):
        resp = client.post(
            f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
            data={
                "input_method": "photo",
                "report_period_type": "daily",
                "coverage_start": "2026-10-01",
                "coverage_end": "2026-10-01",
                "branch_id": branch_id,
            },
            files={"file": ("receipt.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIFfakephoto", "image/jpeg")},
            headers=headers,
        )
        assert resp.status_code == 503
        body = resp.json()
        assert body["error"]["error_code"] == "ERR-RPT-010"


# 16. test_photo_extraction_unparseable
@patch("app.handlers.sales_report_submission_handler.list_models")
@patch("app.services.photo_extractor.list_models")
@patch("app.services.photo_extractor.get_amd_client")
def test_photo_extraction_unparseable(mock_amd_client, mock_extractor_list, mock_handler_list, client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, _ = _setup_test_data(client, headers)

    vision_model = AIModelInfo(id="DeepSeek-V4.1-Flash", supports_streaming=True, supports_tools=True, supports_vision=True, supports_reasoning=False)
    mock_handler_list.return_value = [vision_model]
    mock_extractor_list.return_value = [vision_model]

    # Vision model returns completely invalid response
    mock_client_instance = AsyncMock()
    mock_client_instance.chat_completion = AsyncMock(return_value={
        "choices": [{"message": {"content": "I cannot read this image because it is blurry."}}]
    })
    mock_amd_client.return_value = mock_client_instance

    # Test sync mode (stream=False)
    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "photo",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
            "stream": "false",
        },
        files={"file": ("blurry.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIFfakeblurry", "image/jpeg")},
        headers=headers,
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["error_code"] == "ERR-RPT-011"

    # Test streaming mode (default)
    stream_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "photo",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("blurry2.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIFfakeblurry2", "image/jpeg")},
        headers=headers,
    )
    assert stream_resp.status_code == 200
    assert "ERR-RPT-011" in stream_resp.text


# 17. test_photo_rows_never_auto_confirmed
@patch("app.handlers.sales_report_submission_handler.list_models")
@patch("app.services.photo_extractor.list_models")
@patch("app.services.photo_extractor.get_amd_client")
def test_photo_rows_never_auto_confirmed(mock_amd_client, mock_extractor_list, mock_handler_list, client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, _ = _setup_test_data(client, headers)

    vision_model = AIModelInfo(id="DeepSeek-V4.1-Flash", supports_streaming=True, supports_tools=True, supports_vision=True, supports_reasoning=False)
    mock_handler_list.return_value = [vision_model]
    mock_extractor_list.return_value = [vision_model]

    # Perfect vision extraction
    mock_client_instance = AsyncMock()
    mock_client_instance.chat_completion = AsyncMock(return_value={
        "choices": [{
            "message": {
                "content": json.dumps({
                    "rows": [
                        {
                            "raw_product_name": "Beef Gyros",
                            "period_start": "2026-10-01",
                            "period_end": "2026-10-01",
                            "granularity": "daily",
                            "sold_qty": 20,
                            "recorded_revenue": 1000000,
                        }
                    ]
                })
            }
        }]
    })
    mock_amd_client.return_value = mock_client_instance

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "photo",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
            "stream": "false",
        },
        files={"file": ("clean.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIFcleanphoto", "image/jpeg")},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    # CRITICAL: OCR is NEVER auto-confirmed!
    assert body["submission"]["status"] == "reviewed"
    assert body["summary"]["ready_rows"] == 0
    assert body["summary"]["pending_review_rows"] == 1

    # Fetch staging rows from DB endpoint to be 100% sure review_status == "pending_review"
    sub_id = body["submission"]["id"]
    rows_resp = client.get(f"/api/v1/sales_report_submissions/{sub_id}/staging_rows", headers=headers)
    assert rows_resp.status_code == 200
    rows = rows_resp.json()["data"]["staging_rows"]
    assert len(rows) == 1
    assert rows[0]["review_status"] == "pending_review"


# 18. test_photo_image_too_large
def test_photo_image_too_large(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, _ = _setup_test_data(client, headers)

    large_img = b"0" * (5 * 1024 * 1024 + 1)
    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "photo",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("huge.jpg", large_img, "image/jpeg")},
        headers=headers,
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["error_code"] == "ERR-RPT-012"


# 19. test_cross_submission_overlap_warning
def test_cross_submission_overlap_warning(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id = _setup_test_data(client, headers)

    # 1. Process and confirm a submission for 2026-10-01
    xlsx1 = _create_test_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue"],
        rows=[["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 10, 500000]],
    )
    resp1 = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("first_run.xlsx", xlsx1, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    sub1_id = resp1.json()["data"]["submission"]["id"]
    confirm_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/{sub1_id}/confirm",
        headers=headers,
    )
    assert confirm_resp.status_code == 200

    # 2. Process a new spreadsheet that overlaps the same day/product/branch
    xlsx2 = _create_test_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue"],
        rows=[["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 12, 600000]],
    )
    resp2 = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("second_run.xlsx", xlsx2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp2.status_code == 201
    body2 = resp2.json()["data"]
    # Row gets staged as pending_review because of warning
    assert body2["summary"]["pending_review_rows"] == 1
    assert any(i["issue_code"] == "RPT-VAL-008" and i["severity"] == "warning" for i in body2["issues"])


# 20. test_confirm_after_processing
def test_confirm_after_processing(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, _ = _setup_test_data(client, headers)

    xlsx = _create_test_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue"],
        rows=[
            ["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 10, 500000],
            ["Beef Gyros", branch_id, "2026-10-02", "2026-10-02", "daily", 15, 750000],
        ],
    )
    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-02",
            "branch_id": branch_id,
        },
        files={"file": ("two_days.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 201
    sub_id = resp.json()["data"]["submission"]["id"]

    # Confirm
    conf_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/{sub_id}/confirm",
        headers=headers,
    )
    assert conf_resp.status_code == 200
    sub = conf_resp.json()["data"]["submission"]
    assert sub["status"] == "confirmed"
    assert sub["accepted_rows"] == 2
    assert sub["rejected_rows"] == 0

    # Verify observations exist
    obs_resp = client.get(f"/api/v1/businesses/{biz_id}/sales_report_observations", headers=headers)
    assert obs_resp.status_code == 200
    observations = obs_resp.json()["data"]["observations"]
    assert len(observations) == 2


# 21. test_confirm_rejects_unresolved_rows
def test_confirm_rejects_unresolved_rows(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, _ = _setup_test_data(client, headers)

    xlsx = _create_test_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue"],
        rows=[
            ["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 10, 500000],
            ["Unresolvable Food Item", branch_id, "2026-10-02", "2026-10-02", "daily", 8, 400000],
        ],
    )
    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-02",
            "branch_id": branch_id,
        },
        files={"file": ("mix.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 201
    sub_id = resp.json()["data"]["submission"]["id"]

    # Confirm
    conf_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/{sub_id}/confirm",
        headers=headers,
    )
    assert conf_resp.status_code == 200
    sub = conf_resp.json()["data"]["submission"]
    assert sub["status"] == "confirmed"
    assert sub["accepted_rows"] == 1
    assert sub["rejected_rows"] == 1

    # Only 1 observation created
    obs_resp = client.get(f"/api/v1/businesses/{biz_id}/sales_report_observations", headers=headers)
    assert obs_resp.status_code == 200
    observations = obs_resp.json()["data"]["observations"]
    assert len(observations) == 1


# 22. test_duplicate_confirmation_409
def test_duplicate_confirmation_409(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, _ = _setup_test_data(client, headers)

    xlsx = _create_test_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty"],
        rows=[["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 10]],
    )
    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("single.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    sub_id = resp.json()["data"]["submission"]["id"]

    conf1 = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/{sub_id}/confirm",
        headers=headers,
    )
    assert conf1.status_code == 200

    # Second confirm must fail with 409
    conf2 = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/{sub_id}/confirm",
        headers=headers,
    )
    assert conf2.status_code == 409
