from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.middlewares.auth import require_business_membership
from app.models.schemas.background_job import BackgroundJobResponse
from app.services.background_job_service import get_job
from app.helpers.exceptions import NotFoundException
from app.helpers.response import success_response

router = APIRouter(prefix='/api/v1/businesses/{business_id}/jobs', tags=['Background Jobs'])


@router.get('/{job_id}', dependencies=[Depends(require_business_membership())])
def get_background_job(business_id: int, job_id: int, db: Session = Depends(get_db)):
    job = get_job(db, job_id, business_id)
    if job is None:
        raise NotFoundException(message='Job not found', errors={'job_id': 'Job not found in this business'})
    return success_response('Background job retrieved successfully', {'job': BackgroundJobResponse.model_validate(job).model_dump(mode='json')})
