from unittest.mock import patch, AsyncMock
import pytest

from app.models.product import Product
from app.models.sales_report_staging_row import SalesReportStagingRow


def _setup_test_data(client, headers):
    biz_resp = client.post("/api/v1/businesses", json={"name": "Multi Photo Biz"}, headers=headers)
    biz_id = biz_resp.json()["data"]["business"]["id"]

    branch_resp = client.post(
        f"/api/v1/businesses/{biz_id}/branches",
        json={"name": "Photo Branch", "branch_code": "PB-01"},
        headers=headers,
    )
    branch_id = branch_resp.json()["data"]["branch"]["id"]

    client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Beef Gyros", "base_unit": "portion", "sku": "BG-01"},
        headers=headers,
    )
    client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Chicken Gyros", "base_unit": "portion", "sku": "CG-01"},
        headers=headers,
    )
    return biz_id, branch_id


def test_multi_photo_sync_processing(client, auth_user, db_session):
    headers = auth_user["headers"]
    biz_id, branch_id = _setup_test_data(client, headers)

    img1_bytes = b"fake_jpeg_content_image_1"
    img2_bytes = b"fake_jpeg_content_image_2"

    async def mock_extract(image_bytes, mime_type, business_context):
        if image_bytes == img1_bytes:
            return (
                [
                    {
                        "source_row_number": 1,
                        "raw_product_name": "Beef Gyros",
                        "sold_qty": 12,
                        "period_start": "2026-10-01",
                        "period_end": "2026-10-01",
                        "granularity": "daily",
                    }
                ],
                {"confidence": 0.95},
            )
        else:
            return (
                [
                    {
                        "source_row_number": 1,
                        "raw_product_name": "Chicken Gyros",
                        "sold_qty": 20,
                        "period_start": "2026-10-01",
                        "period_end": "2026-10-01",
                        "granularity": "daily",
                    }
                ],
                {"confidence": 0.90},
            )

    with patch("app.services.sales_report_processing_service.extract_from_photo", side_effect=mock_extract):
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
            files=[
                ("files", ("receipt_page1.jpg", img1_bytes, "image/jpeg")),
                ("files", ("receipt_page2.jpg", img2_bytes, "image/jpeg")),
            ],
            headers=headers,
        )

        assert resp.status_code == 201
        body = resp.json()["data"]
        sub = body["submission"]
        summary = body["summary"]

        assert summary["total_rows"] == 2
        assert "receipt_page1.jpg; receipt_page2.jpg" in sub["source_file_name"]

        # Check DB staging rows for image metadata tagging
        staging_rows = (
            db_session.query(SalesReportStagingRow)
            .filter(SalesReportStagingRow.submission_id == sub["id"])
            .order_by(SalesReportStagingRow.id.asc())
            .all()
        )
        assert len(staging_rows) == 2
        assert staging_rows[0].source_image_index == 1
        assert staging_rows[0].source_image_name == "receipt_page1.jpg"
        assert staging_rows[1].source_image_index == 2
        assert staging_rows[1].source_image_name == "receipt_page2.jpg"
        # Row number offset check
        assert staging_rows[0].source_row_number == 1
        assert staging_rows[1].source_row_number == 1001


def test_single_photo_backward_compatibility(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id = _setup_test_data(client, headers)
    single_img_bytes = b"single_image_test_content"

    async def mock_extract(image_bytes, mime_type, business_context):
        return (
            [
                {
                    "source_row_number": 1,
                    "raw_product_name": "Beef Gyros",
                    "sold_qty": 5,
                    "period_start": "2026-10-01",
                    "period_end": "2026-10-01",
                    "granularity": "daily",
                }
            ],
            {"confidence": 0.99},
        )

    with patch("app.services.sales_report_processing_service.extract_from_photo", side_effect=mock_extract):
        # Uses single 'file' parameter (backward compatibility)
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
            files={"file": ("single_receipt.jpg", single_img_bytes, "image/jpeg")},
            headers=headers,
        )

        assert resp.status_code == 201
        body = resp.json()["data"]
        assert body["summary"]["total_rows"] == 1
        assert body["submission"]["source_file_name"] == "single_receipt.jpg"


def test_multi_photo_exceeds_max_limit(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id = _setup_test_data(client, headers)

    # 11 files (max allowed is 10)
    files_payload = [
        ("files", (f"img_{i}.jpg", b"bytes", "image/jpeg")) for i in range(11)
    ]

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "photo",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files=files_payload,
        headers=headers,
    )

    assert resp.status_code == 422
    assert "Maximum 10 images" in resp.json()["error"]["files"]
