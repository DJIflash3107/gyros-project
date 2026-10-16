import io
import json
from unittest.mock import AsyncMock, patch
import openpyxl
import pytest

from app.configs.settings import settings
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.exceptions import ValidationException
from app.services.input_profiler import (
    profile_excel_workbook,
    WorkbookProfile,
)
from app.services.semantic_mapper import (
    SheetClassification,
    classify_sheet_roles,
    build_fallback_sheet_classifications,
)
from app.services.spreadsheet_parser import parse_excel_workbook


def _create_multi_sheet_xlsx(sheets: dict) -> bytes:
    """Create Excel workbook with multiple sheets. sheets = {title: (headers, rows)}"""
    wb = openpyxl.Workbook()
    for idx, (name, (headers, rows)) in enumerate(sheets.items()):
        ws = wb.active if idx == 0 else wb.create_sheet(title=name)
        if idx == 0:
            ws.title = name
        if headers:
            ws.append(headers)
        for row in rows:
            ws.append(row)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _setup_test_data(client, headers):
    biz_resp = client.post("/api/v1/businesses", json={"name": "MultiSheet Biz"}, headers=headers)
    assert biz_resp.status_code == 201
    biz_id = biz_resp.json()["data"]["business"]["id"]

    branch_resp = client.post(f"/api/v1/businesses/{biz_id}/branches", json={"name": "Central Branch"}, headers=headers)
    assert branch_resp.status_code == 201
    branch_id = branch_resp.json()["data"]["branch"]["id"]

    prod_resp = client.post(f"/api/v1/businesses/{biz_id}/products", json={"name": "Beef Gyros", "base_unit": "portion"}, headers=headers)
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["data"]["product"]["id"]

    prod2_resp = client.post(f"/api/v1/businesses/{biz_id}/products", json={"name": "Chicken Gyros", "base_unit": "portion"}, headers=headers)
    assert prod2_resp.status_code == 201
    prod2_id = prod2_resp.json()["data"]["product"]["id"]

    return biz_id, branch_id, prod_id, prod2_id


# 1. test_profile_excel_workbook
def test_profile_excel_workbook():
    xlsx_bytes = _create_multi_sheet_xlsx({
        "Sheet1": (["Product", "Sold", "Date"], [["Beef Gyros", 10, "2026-10-01"]]),
        "EmptySheet": ([], []),
        "Sheet2": (["Menu", "Terjual", "Omset"], [["Chicken Gyros", 5, 250000]]),
    })

    wb_profile = profile_excel_workbook(xlsx_bytes)
    assert len(wb_profile.sheet_profiles) == 2
    assert "EmptySheet" in wb_profile.skipped_sheets
    sheet_names = [p.active_sheet_name for p in wb_profile.sheet_profiles]
    assert "Sheet1" in sheet_names
    assert "Sheet2" in sheet_names


# 2. test_sheet_role_classification_fallback
def test_sheet_role_classification_fallback():
    xlsx_bytes = _create_multi_sheet_xlsx({
        "Petunjuk Pengisian": (["Langkah", "Keterangan"], [["1", "Isi kolom A"]]),
        "Daftar Menu": (["ID", "Nama Produk"], [["1", "Beef Gyros"]]),
        "Biaya Operasional": (["Tanggal", "Keterangan Biaya"], [["2026-10-01", "Listrik"]]),
        "Penjualan Cabang": (["Product", "Sold Qty", "Revenue"], [["Beef Gyros", 10, 500000]]),
        "Unclear": (["Foo", "Bar"], [["X", "Y"]]),
    })

    wb_profile = profile_excel_workbook(xlsx_bytes)
    classifications = build_fallback_sheet_classifications(wb_profile.sheet_profiles)
    cls_map = {c.sheet_name: c.role for c in classifications}

    assert cls_map["Petunjuk Pengisian"] == "instructional"
    assert cls_map["Daftar Menu"] == "reference"
    assert cls_map["Biaya Operasional"] == "expenses"
    assert cls_map["Penjualan Cabang"] == "sales"
    assert cls_map["Unclear"] == "ambiguous"


# 3. test_sheet_role_classification_llm
@pytest.mark.asyncio
async def test_sheet_role_classification_llm(monkeypatch):
    monkeypatch.setattr(settings, "SEMANTIC_MAPPING_ENABLED", True)
    monkeypatch.setattr(settings, "AMD_API_KEY", "test-key")

    mock_llm_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "classifications": [
                            {"sheet_name": "Sales_DineIn", "role": "sales", "confidence": 0.98, "reasoning": "Contains sold quantities"},
                            {"sheet_name": "Instructions", "role": "instructional", "confidence": 0.95, "reasoning": "Usage guide"},
                            {"sheet_name": "Product_List", "role": "reference", "confidence": 0.90, "reasoning": "Product master data"},
                        ]
                    })
                }
            }
        ]
    }

    xlsx_bytes = _create_multi_sheet_xlsx({
        "Sales_DineIn": (["Item", "Qty Sold", "Price"], [["Beef Gyros", 12, 50000]]),
        "Instructions": (["Note", "Desc"], [["Rule 1", "Fill dates"]]),
        "Product_List": (["Code", "Name"], [["P1", "Beef Gyros"]]),
    })

    wb_profile = profile_excel_workbook(xlsx_bytes)

    with patch("app.configs.amd_client.AMDTokenFactoryClient.chat_completion", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_llm_response
        classifications = await classify_sheet_roles(wb_profile.sheet_profiles)

    cls_map = {c.sheet_name: c.role for c in classifications}
    assert cls_map["Sales_DineIn"] == "sales"
    assert cls_map["Instructions"] == "instructional"
    assert cls_map["Product_List"] == "reference"


# 4. test_parse_excel_workbook_multiple_sheets
def test_parse_excel_workbook_multiple_sheets():
    xlsx_bytes = _create_multi_sheet_xlsx({
        "DineIn": (["Product", "Sold Qty", "Revenue"], [["Beef Gyros", 10, 500000]]),
        "Takeaway": (["Product", "Sold Qty", "Revenue"], [["Chicken Gyros", 8, 320000]]),
        "Ignored": (["X", "Y"], [["1", "2"]]),
    })

    rows, errors = parse_excel_workbook(xlsx_bytes, {"DineIn": None, "Takeaway": None})
    assert len(rows) == 2
    sheets_found = {r["source_sheet_name"] for r in rows}
    assert sheets_found == {"DineIn", "Takeaway"}


# 5. test_end_to_end_multi_sheet_sales
def test_end_to_end_multi_sheet_sales(client, auth_user, monkeypatch):
    monkeypatch.setattr(settings, "SEMANTIC_MAPPING_ENABLED", False)
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id, prod2_id = _setup_test_data(client, headers)

    xlsx_bytes = _create_multi_sheet_xlsx({
        "DineIn": (
            ["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue"],
            [["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 15, 750000]],
        ),
        "Takeaway": (
            ["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue"],
            [["Chicken Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 20, 800000]],
        ),
    })

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("multi_sales.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )

    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["submission"]["status"] == "reviewed"
    assert body["summary"]["total_rows"] == 2
    assert body["summary"]["ready_rows"] == 2
    assert "DineIn" in body["summary"]["sheets_processed"]
    assert "Takeaway" in body["summary"]["sheets_processed"]


# 6. test_end_to_end_multi_sheet_mixed_types
def test_end_to_end_multi_sheet_mixed_types(client, auth_user, monkeypatch):
    monkeypatch.setattr(settings, "SEMANTIC_MAPPING_ENABLED", False)
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id, prod2_id = _setup_test_data(client, headers)

    xlsx_bytes = _create_multi_sheet_xlsx({
        "Petunjuk": (["Info"], [["Gunakan format standard"]]),
        "Daftar Menu": (["Product", "Base Unit"], [["Beef Gyros", "portion"]]),
        "Penjualan": (
            ["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue"],
            [["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 30, 1500000]],
        ),
    })

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("mixed.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )

    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["summary"]["total_rows"] == 1
    assert "Penjualan" in body["summary"]["sheets_processed"]
    assert "Petunjuk" in body["summary"]["sheets_skipped"]
    assert "Daftar Menu" in body["summary"]["sheets_skipped"]


# 7. test_end_to_end_cross_sheet_duplicates
def test_end_to_end_cross_sheet_duplicates(client, auth_user, monkeypatch):
    monkeypatch.setattr(settings, "SEMANTIC_MAPPING_ENABLED", False)
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id, prod2_id = _setup_test_data(client, headers)

    # Both sheets provide the exact same product, branch, and date!
    xlsx_bytes = _create_multi_sheet_xlsx({
        "SheetA": (
            ["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue"],
            [["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 10, 500000]],
        ),
        "SheetB": (
            ["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue"],
            [["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 10, 500000]],
        ),
    })

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("duplicates.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )

    assert resp.status_code == 201
    body = resp.json()["data"]
    # One row is accepted, second is dropped to prevent double counting
    assert body["summary"]["total_rows"] == 1
    # Check that a cross-sheet duplicate issue was raised
    dup_issues = [i for i in body["issues"] if i["issue_code"] == ErrorCodeRegistry.RPT_CROSS_SHEET_DUPLICATE]
    assert len(dup_issues) == 1
    assert "Duplicate record detected across worksheets" in dup_issues[0]["message"]


# 8. test_end_to_end_ambiguous_sheet_warning
def test_end_to_end_ambiguous_sheet_warning(client, auth_user, monkeypatch):
    monkeypatch.setattr(settings, "SEMANTIC_MAPPING_ENABLED", False)
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id, prod2_id = _setup_test_data(client, headers)

    xlsx_bytes = _create_multi_sheet_xlsx({
        "SalesData": (
            ["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue"],
            [["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 10, 500000]],
        ),
        "WeirdNotes": (
            ["Random Header 1", "Random Header 2", "Another Column", "Extra Column"],
            [["Alpha", "Beta", "Gamma", "Delta"]],
        ),
    })

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("ambiguous.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )

    assert resp.status_code == 201
    body = resp.json()["data"]
    assert "SalesData" in body["summary"]["sheets_processed"]
    assert "WeirdNotes" in body["summary"]["sheets_ambiguous"]

    ambig_issues = [i for i in body["issues"] if i["issue_code"] == ErrorCodeRegistry.RPT_AMBIGUOUS_SHEET]
    assert len(ambig_issues) == 1
    assert "WeirdNotes" in ambig_issues[0]["message"]


# 9. test_end_to_end_no_sales_sheets_error
def test_end_to_end_no_sales_sheets_error(client, auth_user, monkeypatch):
    monkeypatch.setattr(settings, "SEMANTIC_MAPPING_ENABLED", False)
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id, prod2_id = _setup_test_data(client, headers)

    xlsx_bytes = _create_multi_sheet_xlsx({
        "Panduan": (["Cara Pakai"], [["1. Baca ini"]]),
    })

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("only_guide.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )

    assert resp.status_code == 422
    err_body = resp.json()
    assert err_body["error"]["error_code"] == ErrorCodeRegistry.RPT_EMPTY_FILE


# 10. test_staging_rows_endpoint_returns_source_sheet_name
def test_staging_rows_endpoint_returns_source_sheet_name(client, auth_user, monkeypatch):
    monkeypatch.setattr(settings, "SEMANTIC_MAPPING_ENABLED", False)
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id, prod2_id = _setup_test_data(client, headers)

    xlsx_bytes = _create_multi_sheet_xlsx({
        "OutletNorth": (
            ["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue"],
            [["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 12, 600000]],
        ),
        "OutletSouth": (
            ["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue"],
            [["Chicken Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 18, 720000]],
        ),
    })

    proc_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("branches.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert proc_resp.status_code == 201
    sub_id = proc_resp.json()["data"]["submission"]["id"]

    rows_resp = client.get(
        f"/api/v1/sales_report_submissions/{sub_id}/staging_rows",
        headers=headers,
    )
    assert rows_resp.status_code == 200
    staging_rows = rows_resp.json()["data"]["staging_rows"]
    assert len(staging_rows) == 2
    sheet_names = {r["source_sheet_name"] for r in staging_rows}
    assert sheet_names == {"OutletNorth", "OutletSouth"}


# 11. test_multi_sheet_repeated_headers_and_blank_rows
def test_multi_sheet_repeated_headers_and_blank_rows():
    headers = ["Product", "Sold Qty", "Revenue"]
    xlsx_bytes = _create_multi_sheet_xlsx({
        "Sheet1": (
            headers,
            [
                ["Beef Gyros", 10, 500000],
                [None, None, None],  # blank row
                headers,              # repeated header row
                ["Chicken Gyros", 8, 320000],
            ],
        ),
    })

    rows, _ = parse_excel_workbook(xlsx_bytes, {"Sheet1": None})
    assert len(rows) == 2
    assert rows[0]["raw_product_name"] == "Beef Gyros"
    assert rows[1]["raw_product_name"] == "Chicken Gyros"
