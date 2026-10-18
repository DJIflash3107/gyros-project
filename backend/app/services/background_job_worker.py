import asyncio
import json
import logging
import uuid
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from starlette.datastructures import Headers

from app.configs.database import SessionLocal
from app.configs.settings import settings
from app.helpers.exceptions import AppException
from app.models.schemas.expense import ExpenseCreate, ExpenseResponse
from app.models.schemas.sales_report_processing import ManualFormBatchCreate
from app.models.schemas.sales_report_staging_row import SalesReportStagingRowBulkUpdate, SalesReportStagingRowResponse
from app.models.schemas.sales_report_submission import SalesReportSubmissionResponse
from app.models.user import User
from app.services import expense_service, sales_report_processing_service, sales_report_staging_row_service
from app.services.background_job_service import update_job

logger = logging.getLogger(__name__)


def store_upload(business_id: int, filename: str, content: bytes) -> str:
    root = Path(settings.BACKGROUND_JOB_STORAGE_DIR).resolve()
    directory = (root / str(business_id)).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = (directory / f'{uuid.uuid4().hex}.upload').resolve()
    path.relative_to(root)
    path.write_bytes(content)
    return str(path.relative_to(root))


def load_upload(storage_key: str) -> bytes:
    root = Path(settings.BACKGROUND_JOB_STORAGE_DIR).resolve()
    path = (root / storage_key).resolve()
    path.relative_to(root)
    return path.read_bytes()


def delete_upload(storage_key: str) -> None:
    try:
        root = Path(settings.BACKGROUND_JOB_STORAGE_DIR).resolve()
        path = (root / storage_key).resolve()
        path.relative_to(root)
        path.unlink(missing_ok=True)
    except (OSError, ValueError):
        logger.warning('Could not remove background job upload %s', storage_key)


def _job_progress(job_id: int, message: str, step: str) -> None:
    update_job(None, job_id, progress={'step': step, 'message': message})


def _run_job(job_id: int, job_type: str, business_id: int, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise RuntimeError('Job requester no longer exists')
        if job_type == 'sales_report_confirm':
            from app.services import sales_report_submission_service
            result = sales_report_submission_service.confirm_submission(db, business_id, payload['submission_id'], user)
            return SalesReportSubmissionResponse.model_validate(result).model_dump(mode='json')
        if job_type == 'sales_report_process':
            _job_progress(job_id, 'Loading uploaded files', 'loading')
            files = [(load_upload(item['storage_key']), item['filename'], item['mime_type']) for item in payload['files']]
            common = {'db': db, 'business_id': business_id, 'current_user': user,
                      'report_period_type': payload['report_period_type'],
                      'coverage_start': date.fromisoformat(payload['coverage_start']),
                      'coverage_end': date.fromisoformat(payload['coverage_end']), 'branch_id': payload.get('branch_id')}
            _job_progress(job_id, 'Validating and processing report', 'processing')
            if payload['input_method'] == 'photo':
                async def consume_photo_events():
                    final_result = None
                    async for event in sales_report_processing_service.process_multi_photo_submission_stream(**common, images=files):
                        lines = event.strip().splitlines()
                        event_name = lines[0].removeprefix('event: ') if lines else 'progress'
                        event_data = json.loads(lines[1].removeprefix('data: ')) if len(lines) > 1 else {}
                        if event_name == 'report_error':
                            raise RuntimeError(event_data.get('message', 'Photo processing failed'))
                        if event_name == 'report_complete':
                            final_result = event_data
                        _job_progress(job_id, event_data.get('message', event_name), event_data.get('step', event_name))
                    return final_result or {'message': 'Photo processing finished'}
                return asyncio.run(consume_photo_events())
            content, filename, mime_type = files[0]
            result = sales_report_processing_service.process_file_submission(
                **common, file_bytes=content, file_name=filename, mime_type=mime_type, input_method='spreadsheet')
            return result.model_dump(mode='json')
        if job_type == 'sales_report_batch_form':
            _job_progress(job_id, 'Validating batch rows', 'validating')
            data = ManualFormBatchCreate.model_validate(payload['data'])
            result = sales_report_processing_service.process_manual_form_batch(db, business_id, user, data)
            return result.model_dump(mode='json')
        if job_type == 'sales_report_staging_bulk_update':
            _job_progress(job_id, 'Updating staging rows', 'updating')
            data = SalesReportStagingRowBulkUpdate.model_validate(payload['data'])
            rows = sales_report_staging_row_service.bulk_update_staging_rows(db, payload['submission_id'], data)
            return {'updated_count': len(rows), 'staging_rows': [SalesReportStagingRowResponse.model_validate(row).model_dump(mode='json') for row in rows]}
        if job_type == 'expense_batch_create':
            _job_progress(job_id, 'Saving expense batch', 'saving')
            items = [ExpenseCreate.model_validate(item) for item in payload['items']]
            expenses, summary = expense_service.create_expenses_batch(db, business_id, items, user)
            return {'summary': summary, 'expenses': [ExpenseResponse.model_validate(item).model_dump(mode='json') for item in expenses]}
        if job_type == 'expense_import':
            _job_progress(job_id, 'Extracting expense data', 'extracting')
            import_files = [UploadFile(filename=item['filename'], file=BytesIO(load_upload(item['storage_key'])), headers=Headers({'content-type': item['mime_type']})) for item in payload['files']]
            from app.services.expense_import_service import import_expenses
            result = asyncio.run(import_expenses(db=db, business_id=business_id, files=import_files,
                input_method=payload['input_method'], branch_id=payload.get('branch_id'),
                default_date=date.fromisoformat(payload['default_date']) if payload.get('default_date') else None,
                current_user=user, source_submission_id=payload.get('source_submission_id')))
            return result.model_dump(mode='json')
        raise ValueError(f'Unsupported background job type: {job_type}')


def run_job(job_id: int, job_type: str, business_id: int, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    storage_keys = [item['storage_key'] for item in payload.get('files', [])]
    try:
        return _run_job(job_id, job_type, business_id, user_id, payload)
    finally:
        for storage_key in storage_keys:
            delete_upload(storage_key)
