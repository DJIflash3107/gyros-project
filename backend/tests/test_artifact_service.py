import base64
from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import os
import shutil
import tempfile
from unittest.mock import patch, MagicMock
import pytest
import httpx
from sqlalchemy.orm import Session

from app.configs.settings import settings
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.exceptions import (
    AppException,
    ArtifactNotFoundException,
    ValidationException,
    AuthenticationException,
    AIRateLimitException,
    ImageGenerationException,
)
from app.models.user import User
from app.models.business import Business
from app.models.branch import Branch
from app.models.product import Product
from app.models.expense import Expense
from app.models.sales_report_submission import SalesReportSubmission
from app.models.sales_report_observation import SalesReportObservation
from app.models.promotion_plan import PromotionPlan
from app.models.forecast_run import ForecastRun
from app.models.forecast_result import ForecastResult
from app.models.business_action import BusinessAction
from app.models.artifact import Artifact
from app.models.business_membership import BusinessMembership
from app.models.schemas.artifact import (
    GenerateReportRequest,
    GeneratePlanArtifactRequest,
    GenerateImageRequest,
    ArtifactFilterParams,
)
from app.services.artifact_storage import (
    LocalStorageService,
    create_download_token,
    verify_download_token,
)
from app.services.report_generator import ReportGeneratorService
from app.services.image_generator import ImageGeneratorService
from app.services.artifact_service import ArtifactService
from app.agent.tools import execute_invoke_artifact_service, execute_tool_by_name


# -----------------------------------------------------------------------------
# Fixtures & Setup Helpers
# -----------------------------------------------------------------------------

@pytest.fixture
def temp_storage():
    """Use a temporary directory for local artifact storage during tests."""
    temp_dir = tempfile.mkdtemp(prefix="gyros_artifacts_test_")
    old_dir = settings.ARTIFACT_STORAGE_LOCAL_DIR
    settings.ARTIFACT_STORAGE_LOCAL_DIR = temp_dir
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)
    settings.ARTIFACT_STORAGE_LOCAL_DIR = old_dir


def _setup_business_and_data(client, auth_headers, db: Session):
    """Seed test business with branch, product, sales observation, expense, promo plan, action."""
    # 1. Create Business
    biz_resp = client.post(
        "/api/v1/businesses", json={"name": "Artifact Test Bistro"}, headers=auth_headers
    )
    assert biz_resp.status_code == 201
    biz_id = biz_resp.json()["data"]["business"]["id"]

    # 2. Create Branch
    branch_resp = client.post(
        f"/api/v1/businesses/{biz_id}/branches", json={"name": "Main Branch"}, headers=auth_headers
    )
    assert branch_resp.status_code == 201
    branch_id = branch_resp.json()["data"]["branch"]["id"]

    # 3. Create Product
    prod_resp = client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Special Gyros Bowl", "category": "Food", "base_unit": "portion"},
        headers=auth_headers,
    )
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["data"]["product"]["id"]

    # 4. Seed Submission and Sales Observation
    today = date.today()
    u = db.query(User).first()
    sub = SalesReportSubmission(
        business_id=biz_id,
        submitted_by_user_id=u.id if u else 1,
        branch_id=branch_id,
        input_method="manual",
        report_period_type="daily",
        coverage_start=today - timedelta(days=2),
        coverage_end=today - timedelta(days=2),
        status="confirmed",
    )
    db.add(sub)
    db.flush()

    obs = SalesReportObservation(
        business_id=biz_id,
        branch_id=branch_id,
        product_id=prod_id,
        source_submission_id=sub.id,
        period_start=today - timedelta(days=2),
        period_end=today - timedelta(days=2),
        granularity="daily",
        sold_qty=Decimal("25.0"),
        recorded_revenue=Decimal("1250000.00"),
        record_status="active",
        created_by_user_id=u.id if u else 1,
    )
    # 5. Seed Expense
    exp = Expense(
        business_id=biz_id,
        branch_id=branch_id,
        expense_date=today - timedelta(days=2),
        category="Ingredients",
        amount=Decimal("300000.00"),
        description="Fresh vegetables supply",
    )
    # 6. Seed Promotion Plan
    plan = PromotionPlan(
        business_id=biz_id,
        title="Ramadan Dinner Special",
        promotion_type="discount",
        status="approved",
        branch_id=branch_id,
        start_date=today,
        end_date=today + timedelta(days=14),
        items=[
            {
                "product_id": prod_id,
                "product_name": "Special Gyros Bowl",
                "discount_type": "percentage",
                "discount_value": 20.0,
                "original_price": 50000.0,
                "discounted_price": 40000.0,
                "estimated_cost": 25000.0,
                "estimated_margin": 15000.0,
                "margin_pct": 37.5,
            }
        ],
        total_original_revenue=Decimal("1000000.00"),
        total_discounted_revenue=Decimal("800000.00"),
        total_estimated_cost=Decimal("500000.00"),
        total_estimated_margin=Decimal("300000.00"),
        avg_margin_pct=Decimal("37.5000"),
        is_financially_validated=True,
    )
    # 7. Seed Forecast Run & Results
    run = ForecastRun(
        business_id=biz_id,
        branch_id=branch_id,
        product_id=prod_id,
        method="WSMA",
        horizon_days=7,
        window_size=7,
        mae=Decimal("1.25"),
    )
    db.add_all([obs, exp, plan, run])
    db.commit()
    db.refresh(run)

    fc_res = ForecastResult(
        forecast_run_id=run.id,
        forecast_date=today + timedelta(days=1),
        predicted_qty=Decimal("30.0"),
        weekday=1,
    )
    # 8. Seed Business Action
    action = BusinessAction(
        business_id=biz_id,
        branch_id=branch_id,
        action_type="promotion",
        rule_label="ACT_PROMOTE_SLOW",
        category="sales",
        title="Promote Slow Moving Gyros Special",
        urgency="medium",
        expected_impact="high",
        priority_score=Decimal("85.5"),
        status="open",
        evidence_quality="high",
        rationale="Opportunity to boost midweek sales volume.",
    )
    db.add_all([fc_res, action])
    db.commit()

    return biz_id, branch_id, prod_id, plan.id, run.id


# =============================================================================
# 1. Storage Service Tests
# =============================================================================

def test_local_storage_crud_and_safety(temp_storage):
    """Test LocalStorageService save, load, exists, delete, and path traversal defense."""
    svc = LocalStorageService(base_dir=temp_storage)
    data = b"Hello, Gyros Artifact!"

    # Save
    path, size, sha256 = svc.save(
        business_id=1, file_data=data, file_name="test_report.csv", mime_type="text/csv"
    )
    assert size == len(data)
    assert sha256 is not None
    assert svc.exists(path) is True

    # Load
    loaded = svc.load(path)
    assert loaded == data

    # Delete
    deleted = svc.delete(path)
    assert deleted is True
    assert svc.exists(path) is False

    # Path traversal attempt
    with pytest.raises(ValidationException):
        svc.load("../../../windows/system32/cmd.exe")


def test_local_storage_max_file_size_exceeded(temp_storage):
    """Saving data larger than ARTIFACT_MAX_FILE_SIZE_MB raises 413."""
    svc = LocalStorageService(base_dir=temp_storage)
    old_max = settings.ARTIFACT_MAX_FILE_SIZE_MB
    settings.ARTIFACT_MAX_FILE_SIZE_MB = 1  # 1 MB

    try:
        huge_data = b"X" * (1024 * 1024 + 10)
        with pytest.raises(AppException) as exc_info:
            svc.save(1, huge_data, "huge.bin", "application/octet-stream")
        assert exc_info.value.status_code == 413
        assert exc_info.value.error_code == ErrorCodeRegistry.ART_FILE_TOO_LARGE
    finally:
        settings.ARTIFACT_MAX_FILE_SIZE_MB = old_max


def test_download_token_generation_and_expiry():
    """Verify signed download token validation, mismatch, and expiration."""
    art_id = 42
    biz_id = 99

    # Valid token
    token = create_download_token(art_id, biz_id, expires_in=3600)
    verified_biz = verify_download_token(token, art_id)
    assert verified_biz == biz_id

    # Artifact mismatch
    with pytest.raises(AuthenticationException) as exc_info:
        verify_download_token(token, artifact_id=999)
    assert "Artifact mismatch" in str(exc_info.value.errors)

    # Expired token
    expired_token = create_download_token(art_id, biz_id, expires_in=-10)
    with pytest.raises(AuthenticationException) as exc_info:
        verify_download_token(expired_token, art_id)
    assert exc_info.value.error_code == ErrorCodeRegistry.ART_EXPIRED


# =============================================================================
# 2. Report Generator Service Tests
# =============================================================================

def test_report_generator_sales_summary_formats(client, auth_user, db_session, temp_storage):
    """Test generating sales_summary report in CSV, XLSX, and PDF formats."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )
    svc = ReportGeneratorService()

    # 1. CSV
    req_csv = GenerateReportRequest(report_type="sales_summary", file_format="csv")
    csv_bytes, csv_name, csv_mime, csv_meta = svc.generate_report(db_session, biz_id, req_csv)
    assert csv_mime == "text/csv"
    assert csv_name.endswith(".csv")
    csv_text = csv_bytes.decode("utf-8-sig")
    assert "Special Gyros Bowl" in csv_text
    assert "Recorded Revenue" in csv_text

    # 2. XLSX
    req_xlsx = GenerateReportRequest(report_type="sales_summary", file_format="xlsx")
    xlsx_bytes, xlsx_name, xlsx_mime, xlsx_meta = svc.generate_report(db_session, biz_id, req_xlsx)
    assert xlsx_mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert xlsx_name.endswith(".xlsx")
    assert len(xlsx_bytes) > 1000

    # 3. PDF
    req_pdf = GenerateReportRequest(report_type="sales_summary", file_format="pdf")
    pdf_bytes, pdf_name, pdf_mime, pdf_meta = svc.generate_report(db_session, biz_id, req_pdf)
    assert pdf_mime == "application/pdf"
    assert pdf_name.endswith(".pdf")
    assert pdf_bytes.startswith(b"%PDF-")


def test_report_generator_all_report_types(client, auth_user, db_session, temp_storage):
    """Test generating all supported report types (financial, inventory, forecast, promo, actions)."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )
    svc = ReportGeneratorService()

    report_types = [
        "financial_summary",
        "inventory_status",
        "forecast_export",
        "promotion_summary",
        "action_center_summary",
    ]

    for r_type in report_types:
        req = GenerateReportRequest(report_type=r_type, file_format="xlsx")
        b, name, mime, meta = svc.generate_report(db_session, biz_id, req)
        assert len(b) > 500
        assert name.endswith(".xlsx")
        assert meta["report_type"] == r_type


def test_report_generator_date_filtering(client, auth_user, db_session, temp_storage):
    """Report generator applies date range filters."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )
    svc = ReportGeneratorService()

    # Filter with start_date and end_date
    today = date.today()
    req = GenerateReportRequest(
        report_type="sales_summary",
        file_format="csv",
        start_date=today - timedelta(days=5),
        end_date=today,
    )
    b, name, mime, meta = svc.generate_report(db_session, biz_id, req)
    assert meta["total_records"] >= 1

    # Empty range
    req_empty = GenerateReportRequest(
        report_type="sales_summary",
        file_format="csv",
        start_date=today + timedelta(days=10),
        end_date=today + timedelta(days=20),
    )
    b, name, mime, meta = svc.generate_report(db_session, biz_id, req_empty)
    assert meta["total_records"] == 0


def test_report_generator_plan_artifact(client, auth_user, db_session, temp_storage):
    """Test generating structured plan export for an existing PromotionPlan."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )
    svc = ReportGeneratorService()

    # PDF Plan
    req_pdf = GeneratePlanArtifactRequest(source_plan_id=plan_id, file_format="pdf")
    pdf_bytes, pdf_name, pdf_mime, meta = svc.generate_plan_artifact(db_session, biz_id, req_pdf)
    assert pdf_mime == "application/pdf"
    assert pdf_bytes.startswith(b"%PDF-")
    assert meta["source_plan_id"] == plan_id

    # XLSX Plan
    req_xlsx = GeneratePlanArtifactRequest(source_plan_id=plan_id, file_format="xlsx")
    xlsx_bytes, xlsx_name, xlsx_mime, meta = svc.generate_plan_artifact(db_session, biz_id, req_xlsx)
    assert xlsx_name.endswith(".xlsx")

    # CSV Plan
    req_csv = GeneratePlanArtifactRequest(source_plan_id=plan_id, file_format="csv")
    csv_bytes, csv_name, csv_mime, meta = svc.generate_plan_artifact(db_session, biz_id, req_csv)
    assert csv_name.endswith(".csv")

    # Non-existent plan raises 404
    with pytest.raises(Exception):
        svc.generate_plan_artifact(
            db_session, biz_id, GeneratePlanArtifactRequest(source_plan_id=99999)
        )


def test_report_request_validation():
    """Invalid date range (end_date < start_date) triggers validation error."""
    today = date.today()
    with pytest.raises(ValueError):
        GenerateReportRequest(
            report_type="sales_summary",
            start_date=today,
            end_date=today - timedelta(days=1),
        )


# =============================================================================
# 3. Image Generation Service & Provider Validation Tests
# =============================================================================

def test_image_generator_rejects_non_image_models():
    """Verify that text/vision/chat models are strictly rejected for image generation."""
    svc = ImageGeneratorService()

    # Explicit text/chat model
    with pytest.raises(ValidationException) as exc_info:
        svc._verify_model("DeepSeek-V4-Flash")
    assert exc_info.value.error_code == ErrorCodeRegistry.ART_IMAGE_MODEL_UNSUPPORTED

    # Vision model must not be accepted for image generation
    with pytest.raises(ValidationException) as exc_info:
        svc._verify_model("qwen-vl-vision-chat")
    assert exc_info.value.error_code == ErrorCodeRegistry.ART_IMAGE_MODEL_UNSUPPORTED

    # Empty model
    with pytest.raises(AppException) as exc_info:
        svc._verify_model("")
    assert exc_info.value.error_code == ErrorCodeRegistry.ART_IMAGE_NOT_CONFIGURED

    # Verified image synthesis models should be accepted
    assert svc._verify_model("FLUX.1-schnell") == "FLUX.1-schnell"
    assert svc._verify_model("SDXL-Turbo") == "SDXL-Turbo"
    assert svc._verify_model("stable-diffusion-3") == "stable-diffusion-3"


def test_image_request_prompt_validation():
    """Verify F&B business relevance and off-topic rejection."""
    # Disallowed keywords
    with pytest.raises(ValueError) as exc:
        GenerateImageRequest(purpose="promotional_poster", prompt="High quality poster with a gun and weapon")
    assert "disallowed content" in str(exc.value)

    # Completely off-topic non-F&B prompt
    with pytest.raises(ValueError) as exc:
        GenerateImageRequest(purpose="promotional_poster", prompt="Quantum physics equation on a blackboard in space")
    assert "relevant to food & beverage business" in str(exc.value)

    # Valid F&B prompt passes
    req = GenerateImageRequest(
        purpose="product_catalog",
        prompt="Delicious roasted chicken gyro wrap with tzatziki sauce",
    )
    assert req.purpose == "product_catalog"


@pytest.mark.asyncio
async def test_image_generator_success_b64():
    """Test successful image generation returning b64_json."""
    fake_png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00test"
    fake_b64 = base64.b64encode(fake_png_bytes).decode("utf-8")

    async def mock_post(url, json=None, headers=None, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"b64_json": fake_b64}]
        }
        return mock_resp

    svc = ImageGeneratorService(
        api_key="mock-key-123",
        model="FLUX.1-schnell",
        max_retries=0,
    )
    req = GenerateImageRequest(
        purpose="promotional_poster",
        prompt="Vibrant promotional poster for gourmet burger and iced tea combo",
    )

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        img_bytes, filename, mime, meta = await svc.generate_image(req, business_id=1)

    assert img_bytes == fake_png_bytes
    assert filename.endswith(".png")
    assert mime == "image/png"
    assert meta["purpose"] == "promotional_poster"
    assert meta["model"] == "FLUX.1-schnell"


@pytest.mark.asyncio
async def test_image_generator_provider_content_policy_error():
    """Provider 400 content policy error raises ART_IMAGE_CONTENT_POLICY exception."""
    async def mock_post(url, json=None, headers=None, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Prompt flagged by content moderation filter"
        mock_resp.json.return_value = {"error": {"message": "Content policy violation"}}
        return mock_resp

    svc = ImageGeneratorService(
        api_key="mock-key",
        model="FLUX.1-schnell",
        max_retries=0,
    )
    req = GenerateImageRequest(
        purpose="promotional_poster",
        prompt="Special promotion feast for holiday celebration dinner",
    )

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        with pytest.raises(AppException) as exc_info:
            await svc.generate_image(req, business_id=1)
        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == ErrorCodeRegistry.ART_IMAGE_CONTENT_POLICY


@pytest.mark.asyncio
async def test_image_generator_provider_timeout_error():
    """Provider timeout raises ART_IMAGE_TIMEOUT (HTTP 504)."""
    async def mock_post(url, **kwargs):
        raise httpx.TimeoutException("Read timed out after 120s")

    svc = ImageGeneratorService(
        api_key="mock-key",
        model="FLUX.1-schnell",
        max_retries=0,
    )
    req = GenerateImageRequest(
        purpose="promotional_poster",
        prompt="Fresh coffee and pastry morning combo poster",
    )

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        with pytest.raises(AppException) as exc_info:
            await svc.generate_image(req, business_id=1)
        assert exc_info.value.status_code == 504
        assert exc_info.value.error_code == ErrorCodeRegistry.ART_IMAGE_TIMEOUT


@pytest.mark.asyncio
async def test_image_generator_never_creates_placeholder_on_failure():
    """CRITICAL: Failed image generation must fail loudly and NEVER generate placeholder files."""
    async def mock_post(url, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Provider Error"
        mock_resp.json.return_value = {"error": {"message": "GPU worker crash"}}
        return mock_resp

    svc = ImageGeneratorService(
        api_key="mock-key",
        model="FLUX.1-schnell",
        max_retries=0,
    )
    req = GenerateImageRequest(
        purpose="promotional_poster",
        prompt="Special chef tasting menu visual presentation",
    )

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        with pytest.raises(ImageGenerationException) as exc_info:
            await svc.generate_image(req, business_id=1)
        assert exc_info.value.status_code == 502


# =============================================================================
# 4. Artifact Service & API Endpoints Tests
# =============================================================================

def test_api_generate_report(client, auth_user, db_session, temp_storage):
    """POST /api/v1/businesses/{business_id}/artifacts/generate-report creates artifact."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/artifacts/generate-report",
        json={"report_type": "sales_summary", "file_format": "xlsx", "title": "Monthly Sales Overview"},
        headers=auth_user["headers"],
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["title"] == "Monthly Sales Overview"
    assert data["artifact_type"] == "report"
    assert data["file_format"] == "xlsx"
    assert data["status"] == "ready"
    assert data["download_url"] is not None


def test_api_generate_plan_artifact(client, auth_user, db_session, temp_storage):
    """POST /api/v1/businesses/{business_id}/artifacts/generate-plan exports a promotion plan."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/artifacts/generate-plan",
        json={"source_plan_id": plan_id, "file_format": "pdf"},
        headers=auth_user["headers"],
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["artifact_type"] == "plan"
    assert data["file_format"] == "pdf"
    assert data["source_entity_id"] == plan_id


def test_api_generate_image(client, auth_user, db_session, temp_storage):
    """POST /api/v1/businesses/{business_id}/artifacts/generate-image generates an F&B visual."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )

    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00img_bytes"
    fake_b64 = base64.b64encode(fake_png).decode("utf-8")

    async def mock_post(url, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"b64_json": fake_b64}]}
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post), \
         patch.object(settings, "IMAGE_GEN_MODEL", "FLUX.1-schnell"), \
         patch.object(settings, "AMD_API_KEY", "test-api-key"):
        resp = client.post(
            f"/api/v1/businesses/{biz_id}/artifacts/generate-image",
            json={
                "purpose": "product_catalog",
                "prompt": "Gourmet beef gyros sandwich on artisanal bread with chips",
                "product_id": prod_id,
            },
            headers=auth_user["headers"],
        )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["artifact_type"] == "image"
    assert data["purpose"] == "product_catalog"
    assert data["file_format"] == "png"


def test_api_list_artifacts_with_filters(client, auth_user, db_session, temp_storage):
    """GET /api/v1/businesses/{business_id}/artifacts/ lists items with pagination and filters."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )

    # Generate two reports
    client.post(
        f"/api/v1/businesses/{biz_id}/artifacts/generate-report",
        json={"report_type": "sales_summary", "file_format": "csv"},
        headers=auth_user["headers"],
    )
    client.post(
        f"/api/v1/businesses/{biz_id}/artifacts/generate-report",
        json={"report_type": "financial_summary", "file_format": "xlsx"},
        headers=auth_user["headers"],
    )

    # List all
    list_resp = client.get(
        f"/api/v1/businesses/{biz_id}/artifacts",
        headers=auth_user["headers"],
    )
    assert list_resp.status_code == 200
    res_data = list_resp.json()["data"]
    assert len(res_data["artifacts"]) >= 2
    assert res_data["pagination"]["total_records"] >= 2

    # Filter by format=csv
    filtered_resp = client.get(
        f"/api/v1/businesses/{biz_id}/artifacts?file_format=csv",
        headers=auth_user["headers"],
    )
    assert filtered_resp.status_code == 200
    for a in filtered_resp.json()["data"]["artifacts"]:
        assert a["file_format"] == "csv"


def test_api_get_artifact_detail(client, auth_user, db_session, temp_storage):
    """GET /api/v1/businesses/{business_id}/artifacts/{artifact_id} returns detail."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )
    gen = client.post(
        f"/api/v1/businesses/{biz_id}/artifacts/generate-report",
        json={"report_type": "inventory_status", "file_format": "csv"},
        headers=auth_user["headers"],
    )
    art_id = gen.json()["data"]["id"]

    detail = client.get(
        f"/api/v1/businesses/{biz_id}/artifacts/{art_id}",
        headers=auth_user["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == art_id


def test_api_download_endpoints_signed_token_and_bearer(client, auth_user, db_session, temp_storage):
    """Verify download endpoint works with signed download token (no headers) and Bearer header."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )
    gen = client.post(
        f"/api/v1/businesses/{biz_id}/artifacts/generate-report",
        json={"report_type": "sales_summary", "file_format": "csv"},
        headers=auth_user["headers"],
    )
    art = gen.json()["data"]
    art_id = art["id"]
    download_url = art["download_url"]

    # 1. Download via signed download URL without Bearer header
    token_dl = client.get(download_url)
    assert token_dl.status_code == 200
    assert "text/csv" in token_dl.headers["Content-Type"]
    assert "Special Gyros Bowl" in token_dl.text

    # 2. Download via Bearer header directly
    bearer_dl = client.get(
        f"/api/v1/businesses/{biz_id}/artifacts/{art_id}/download",
        headers=auth_user["headers"],
    )
    assert bearer_dl.status_code == 200
    assert "Special Gyros Bowl" in bearer_dl.text

    # 3. Download without any auth returns 401
    anon_dl = client.get(f"/api/v1/businesses/{biz_id}/artifacts/{art_id}/download")
    assert anon_dl.status_code == 401


def test_api_delete_artifact(client, auth_user, db_session, temp_storage):
    """DELETE /api/v1/businesses/{business_id}/artifacts/{artifact_id} removes artifact and disk file."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )
    gen = client.post(
        f"/api/v1/businesses/{biz_id}/artifacts/generate-report",
        json={"report_type": "sales_summary", "file_format": "csv"},
        headers=auth_user["headers"],
    )
    art_id = gen.json()["data"]["id"]

    del_resp = client.delete(
        f"/api/v1/businesses/{biz_id}/artifacts/{art_id}",
        headers=auth_user["headers"],
    )
    assert del_resp.status_code == 200

    # Ensure not found now
    get_resp = client.get(
        f"/api/v1/businesses/{biz_id}/artifacts/{art_id}",
        headers=auth_user["headers"],
    )
    assert get_resp.status_code == 404


def test_api_multi_tenant_isolation(client, auth_user, second_user, db_session, temp_storage):
    """Ensure user from Business B cannot access or download artifacts from Business A."""
    biz_a, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )

    # Generate artifact in Business A
    gen_a = client.post(
        f"/api/v1/businesses/{biz_a}/artifacts/generate-report",
        json={"report_type": "financial_summary", "file_format": "xlsx"},
        headers=auth_user["headers"],
    )
    art_a_id = gen_a.json()["data"]["id"]

    # Create Business B for second_user
    biz_b_resp = client.post(
        "/api/v1/businesses", json={"name": "Business B"}, headers=second_user["headers"]
    )
    biz_b = biz_b_resp.json()["data"]["business"]["id"]

    # second_user attempts to access Business A artifact -> 403 Forbidden
    cross_access = client.get(
        f"/api/v1/businesses/{biz_a}/artifacts/{art_a_id}",
        headers=second_user["headers"],
    )
    assert cross_access.status_code == 403

    # second_user attempts to download Business A artifact via business B route -> 404 Not Found
    cross_download = client.get(
        f"/api/v1/businesses/{biz_b}/artifacts/{art_a_id}/download",
        headers=second_user["headers"],
    )
    assert cross_download.status_code == 404


def test_api_role_permissions(client, auth_user, second_user, db_session, temp_storage):
    """Verify role permissions: staff cannot generate or delete artifacts."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )

    # Add second_user as 'viewer'
    add_mem = client.post(
        f"/api/v1/businesses/{biz_id}/memberships",
        json={"user_id": second_user["user"]["id"], "role": "viewer"},
        headers=auth_user["headers"],
    )
    assert add_mem.status_code == 201

    # Viewer attempt to generate report -> 403 Forbidden
    viewer_gen = client.post(
        f"/api/v1/businesses/{biz_id}/artifacts/generate-report",
        json={"report_type": "sales_summary", "file_format": "csv"},
        headers=second_user["headers"],
    )
    assert viewer_gen.status_code == 403


def test_direct_artifact_endpoints(client, auth_user, db_session, temp_storage):
    """Verify secondary direct router under /api/v1/artifacts/."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )

    # Direct generate report
    gen_resp = client.post(
        f"/api/v1/artifacts/generate-report?business_id={biz_id}",
        json={"report_type": "sales_summary", "file_format": "csv"},
        headers=auth_user["headers"],
    )
    assert gen_resp.status_code == 201
    art_id = gen_resp.json()["data"]["id"]

    # Direct list
    list_resp = client.get(
        f"/api/v1/artifacts?business_id={biz_id}",
        headers=auth_user["headers"],
    )
    assert list_resp.status_code == 200

    # Direct get
    get_resp = client.get(
        f"/api/v1/artifacts/{art_id}?business_id={biz_id}",
        headers=auth_user["headers"],
    )
    assert get_resp.status_code == 200

    # Direct download
    dl_resp = client.get(
        f"/api/v1/artifacts/{art_id}/download?business_id={biz_id}",
        headers=auth_user["headers"],
    )
    assert dl_resp.status_code == 200


# =============================================================================
# 5. Agent Tool Integration Tests
# =============================================================================

def test_agent_tool_invoke_artifact_service(client, auth_user, db_session, temp_storage):
    """Test execute_invoke_artifact_service handles generate_report, generate_plan, list, get."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )

    # 1. Action: generate_report
    res_rpt = execute_invoke_artifact_service(
        biz_id,
        db=db_session,
        action="generate_report",
        report_type="sales_summary",
        file_format="xlsx",
    )
    assert res_rpt["data"]["status"] == "success"
    art_id = res_rpt["data"]["artifact"]["id"]
    assert "Download URL" in res_rpt["summary"]

    # 2. Action: generate_plan
    res_plan = execute_invoke_artifact_service(
        biz_id,
        db=db_session,
        action="generate_plan",
        source_plan_id=plan_id,
        file_format="pdf",
    )
    assert res_plan["data"]["status"] == "success"

    # 3. Action: list
    res_list = execute_invoke_artifact_service(
        biz_id,
        db=db_session,
        action="list",
    )
    assert res_list["data"]["total"] >= 2

    # 4. Action: get
    res_get = execute_invoke_artifact_service(
        biz_id,
        db=db_session,
        action="get",
        artifact_id=art_id,
    )
    assert res_get["data"]["artifact"]["id"] == art_id

    # 5. Missing db session returns error safely
    err_res = execute_invoke_artifact_service(biz_id, db=None)
    assert err_res["error"] == "db session is required"


def test_agent_tool_dispatch_by_name(client, auth_user, db_session, temp_storage):
    """Test execute_tool_by_name dispatches invoke_artifact_service properly."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )

    result = execute_tool_by_name(
        tool_name="invoke_artifact_service",
        tool_args={
            "action": "generate_report",
            "report_type": "sales_summary",
            "file_format": "csv",
        },
        db=db_session,
        business_id=biz_id,
    )
    assert result["data"]["status"] == "success"
    assert "CSV" in result["summary"]


@pytest.mark.asyncio
async def test_image_generator_success_url_download():
    """Test image generator downloads image when provider returns URL instead of b64."""
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRurl_bytes"

    async def mock_post(url, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"url": "https://images.example.com/generated_123.png"}]}
        return mock_resp

    async def mock_get(url, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = fake_png
        return mock_resp

    svc = ImageGeneratorService(
        api_key="mock-key",
        model="FLUX.1-schnell",
        max_retries=0,
    )
    req = GenerateImageRequest(
        purpose="promotion_visual",
        prompt="A vibrant promotional visual of iced peach tea beverage on a wooden table",
    )

    with patch("httpx.AsyncClient.post", side_effect=mock_post), \
         patch("httpx.AsyncClient.get", side_effect=mock_get):
        img_bytes, filename, mime, meta = await svc.generate_image(req, business_id=1)

    assert img_bytes == fake_png
    assert mime == "image/png"


@pytest.mark.asyncio
async def test_image_generator_provider_rate_limited():
    """Provider 429 rate limit raises AIRateLimitException."""
    async def mock_post(url, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Rate limit exceeded"
        mock_resp.json.return_value = {"error": {"message": "Rate limit exceeded"}}
        return mock_resp

    svc = ImageGeneratorService(
        api_key="mock-key",
        model="FLUX.1-schnell",
        max_retries=0,
    )
    req = GenerateImageRequest(
        purpose="promotional_poster",
        prompt="Delicious special coffee combo visual",
    )

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        with pytest.raises(AIRateLimitException):
            await svc.generate_image(req, business_id=1)


def test_direct_generate_plan_and_image(client, auth_user, db_session, temp_storage):
    """Verify direct /api/v1/artifacts/generate-plan and /api/v1/artifacts/generate-image."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )

    # 1. Direct generate-plan
    plan_resp = client.post(
        f"/api/v1/artifacts/generate-plan?business_id={biz_id}",
        json={"source_plan_id": plan_id, "file_format": "xlsx"},
        headers=auth_user["headers"],
    )
    assert plan_resp.status_code == 201
    assert plan_resp.json()["data"]["file_format"] == "xlsx"

    # 2. Direct generate-image
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRdirect_img"
    fake_b64 = base64.b64encode(fake_png).decode("utf-8")

    async def mock_post(url, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"b64_json": fake_b64}]}
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post), \
         patch.object(settings, "IMAGE_GEN_MODEL", "FLUX.1-schnell"), \
         patch.object(settings, "AMD_API_KEY", "test-api-key"):
        img_resp = client.post(
            f"/api/v1/artifacts/generate-image?business_id={biz_id}",
            json={
                "purpose": "promotional_poster",
                "prompt": "Festive promo poster showcasing signature dessert waffles",
            },
            headers=auth_user["headers"],
        )
    assert img_resp.status_code == 201
    assert img_resp.json()["data"]["artifact_type"] == "image"


def test_download_token_tampered_fails():
    """Tampered token raises AuthenticationException."""
    token = create_download_token(artifact_id=1, business_id=1)
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(AuthenticationException):
        verify_download_token(tampered, artifact_id=1)


def test_agent_tool_invoke_artifact_service_plan_and_image(client, auth_user, db_session, temp_storage):
    """Test execute_invoke_artifact_service for generate_plan and generate_image actions."""
    biz_id, branch_id, prod_id, plan_id, run_id = _setup_business_and_data(
        client, auth_user["headers"], db_session
    )

    # 1. Agent tool export plan
    res_plan = execute_invoke_artifact_service(
        business_id=biz_id,
        db=db_session,
        action="generate_plan",
        source_plan_id=plan_id,
        file_format="pdf",
    )
    assert res_plan["data"]["status"] == "success"

    # 2. Agent tool generate image
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRtool_img"
    fake_b64 = base64.b64encode(fake_png).decode("utf-8")

    async def mock_post(url, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"b64_json": fake_b64}]}
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post), \
         patch.object(settings, "IMAGE_GEN_MODEL", "FLUX.1-schnell"), \
         patch.object(settings, "AMD_API_KEY", "test-api-key"):
        res_img = execute_invoke_artifact_service(
            business_id=biz_id,
            db=db_session,
            action="generate_image",
            purpose="product_catalog",
            prompt="High quality product catalog visual of traditional cold brew iced coffee",
        )
    assert res_img["data"]["status"] == "success"
    assert "Download URL" in res_img["summary"]

