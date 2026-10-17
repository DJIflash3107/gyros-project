from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.configs.database import get_db
from app.configs.security import decode_access_token
from app.models.user import User
from app.models.artifact import Artifact
from app.models.business_membership import BusinessMembership
from app.models.schemas.artifact import (
    GenerateReportRequest,
    GeneratePlanArtifactRequest,
    GenerateImageRequest,
    ArtifactFilterParams,
    ArtifactTypeLiteral,
    ArtifactStatusLiteral,
)
from app.middlewares.auth import get_current_user, require_business_membership
from app.handlers import artifact_handler
from app.services.artifact_storage import verify_download_token
from app.helpers.exceptions import (
    ValidationException,
    AuthorizationException,
    AuthenticationException,
    ArtifactNotFoundException,
)


# Primary router scoped by business
router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/artifacts",
    tags=["Artifacts"],
)

# Secondary router mounted under /api/v1/artifacts
direct_router = APIRouter(
    prefix="/api/v1/artifacts",
    tags=["Artifacts"],
)


def _verify_user_business_role(
    db: Session,
    user: User,
    business_id: int,
    allowed_roles: Optional[List[str]] = None,
) -> BusinessMembership:
    membership = (
        db.query(BusinessMembership)
        .filter(
            BusinessMembership.business_id == business_id,
            BusinessMembership.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise AuthorizationException(
            message="Access denied",
            errors={"authorization": "You are not a member of this business"},
        )
    if allowed_roles and membership.role not in allowed_roles:
        raise AuthorizationException(
            message="Access denied",
            errors={"authorization": f"Role '{membership.role}' does not have sufficient permissions"},
        )
    return membership


# ---------------------------------------------------------
# Primary Business-Scoped Endpoints: /api/v1/businesses/{business_id}/artifacts
# ---------------------------------------------------------

@router.post(
    "/generate-report",
    status_code=201,
    dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))],
)
def generate_report(
    business_id: int,
    data: GenerateReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate business report (CSV, XLSX, PDF) from validated business data."""
    return artifact_handler.generate_report_handler(business_id, data, current_user, db)


@router.post(
    "/generate-plan",
    status_code=201,
    dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))],
)
def generate_plan_artifact(
    business_id: int,
    data: GeneratePlanArtifactRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export promotion plan or business plan to file (CSV, XLSX, PDF)."""
    return artifact_handler.generate_plan_artifact_handler(business_id, data, current_user, db)


@router.post(
    "/generate-image",
    status_code=201,
    dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))],
)
async def generate_image(
    business_id: int,
    data: GenerateImageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate image for verified F&B business purpose (product catalog, poster, promotion visual)."""
    return await artifact_handler.generate_image_handler(business_id, data, current_user, db)


@router.get(
    "",
    dependencies=[Depends(require_business_membership(["owner", "admin", "manager", "viewer"]))],
)
@router.get(
    "/",
    include_in_schema=False,
    dependencies=[Depends(require_business_membership(["owner", "admin", "manager", "viewer"]))],
)
def list_artifacts(
    business_id: int,
    artifact_type: Optional[ArtifactTypeLiteral] = Query(None, description="Filter by type (report, plan, file, image)"),
    file_format: Optional[str] = Query(None, description="Filter by file format (csv, xlsx, pdf, png)"),
    purpose: Optional[str] = Query(None, description="Filter by business purpose"),
    status: Optional[ArtifactStatusLiteral] = Query(None, description="Filter by status (pending, generating, ready, failed)"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List business artifacts with optional filtering."""
    filters = ArtifactFilterParams(
        artifact_type=artifact_type,
        file_format=file_format,
        purpose=purpose,
        status=status,
        page=page,
        per_page=per_page,
    )
    return artifact_handler.list_artifacts_handler(business_id, filters, db)


@router.get(
    "/{artifact_id}",
    dependencies=[Depends(require_business_membership(["owner", "admin", "manager", "viewer"]))],
)
def get_artifact(
    business_id: int,
    artifact_id: int,
    db: Session = Depends(get_db),
):
    """Get metadata for a specific artifact."""
    return artifact_handler.get_artifact_handler(business_id, artifact_id, db)


@router.get(
    "/{artifact_id}/download-url",
    dependencies=[Depends(require_business_membership(["owner", "admin", "manager", "viewer"]))],
)
def get_download_url(
    business_id: int,
    artifact_id: int,
    expires_in: int = Query(3600, ge=60, le=86400, description="Expiry time in seconds"),
    db: Session = Depends(get_db),
):
    """Generate authorized expiring download URL for artifact."""
    return artifact_handler.get_download_url_handler(business_id, artifact_id, expires_in, db)


@router.get(
    "/{artifact_id}/download",
)
def download_artifact(
    business_id: int,
    artifact_id: int,
    token: Optional[str] = Query(None, description="Signed download token"),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Download artifact file content. Authenticates via either signed download token or Bearer header."""
    if token:
        # Validate token and verify it matches this business & artifact
        biz_id = verify_download_token(token, artifact_id)
        if biz_id != business_id:
            raise AuthorizationException(
                message="Download token does not match specified business",
                errors={"authorization": "Business mismatch"},
            )
        return artifact_handler.download_artifact_handler(business_id, artifact_id, db)

    # Fallback to Authorization header Bearer token
    auth_header = request.headers.get("Authorization") if request else None
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AuthenticationException(
            message="Authentication required: provide Bearer token or signed download token",
            errors={"authentication": "Missing credentials"},
        )
    bearer_token = auth_header[7:].strip()
    payload = decode_access_token(bearer_token)
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise AuthenticationException(message="User not found")

    _verify_user_business_role(db, user, business_id)
    return artifact_handler.download_artifact_handler(business_id, artifact_id, db)


@router.delete(
    "/{artifact_id}",
    status_code=200,
    dependencies=[Depends(require_business_membership(["owner", "admin"]))],
)
def delete_artifact(
    business_id: int,
    artifact_id: int,
    db: Session = Depends(get_db),
):
    """Delete an artifact and its underlying stored file."""
    return artifact_handler.delete_artifact_handler(business_id, artifact_id, db)


# ---------------------------------------------------------
# Direct Endpoints: /api/v1/artifacts
# ---------------------------------------------------------

@direct_router.post("/generate-report", status_code=201)
def direct_generate_report(
    data: GenerateReportRequest,
    business_id: int = Query(..., description="Business ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate report via direct /api/v1/artifacts/ endpoint."""
    _verify_user_business_role(db, current_user, business_id, ["owner", "admin", "manager"])
    return artifact_handler.generate_report_handler(business_id, data, current_user, db)


@direct_router.post("/generate-plan", status_code=201)
def direct_generate_plan(
    data: GeneratePlanArtifactRequest,
    business_id: int = Query(..., description="Business ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export plan via direct /api/v1/artifacts/ endpoint."""
    _verify_user_business_role(db, current_user, business_id, ["owner", "admin", "manager"])
    return artifact_handler.generate_plan_artifact_handler(business_id, data, current_user, db)


@direct_router.post("/generate-image", status_code=201)
async def direct_generate_image(
    data: GenerateImageRequest,
    business_id: int = Query(..., description="Business ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate image via direct /api/v1/artifacts/ endpoint."""
    _verify_user_business_role(db, current_user, business_id, ["owner", "admin", "manager"])
    return await artifact_handler.generate_image_handler(business_id, data, current_user, db)


@direct_router.get("")
@direct_router.get("/", include_in_schema=False)
def direct_list_artifacts(
    business_id: int = Query(..., description="Business ID"),
    artifact_type: Optional[ArtifactTypeLiteral] = Query(None, description="Filter by type"),
    file_format: Optional[str] = Query(None, description="Filter by format"),
    purpose: Optional[str] = Query(None, description="Filter by purpose"),
    status: Optional[ArtifactStatusLiteral] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List artifacts via direct /api/v1/artifacts/ endpoint."""
    _verify_user_business_role(db, current_user, business_id)
    filters = ArtifactFilterParams(
        artifact_type=artifact_type,
        file_format=file_format,
        purpose=purpose,
        status=status,
        page=page,
        per_page=per_page,
    )
    return artifact_handler.list_artifacts_handler(business_id, filters, db)


@direct_router.get("/{artifact_id}")
def direct_get_artifact(
    artifact_id: int,
    business_id: Optional[int] = Query(None, description="Business ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get artifact detail via direct /api/v1/artifacts/ endpoint."""
    if not business_id:
        # Resolve business_id from artifact
        art = db.execute(select(Artifact).where(Artifact.id == artifact_id)).scalar_one_or_none()
        if not art:
            raise ArtifactNotFoundException(message=f"Artifact #{artifact_id} not found")
        business_id = art.business_id

    _verify_user_business_role(db, current_user, business_id)
    return artifact_handler.get_artifact_handler(business_id, artifact_id, db)


@direct_router.get("/{artifact_id}/download-url")
def direct_get_download_url(
    artifact_id: int,
    business_id: Optional[int] = Query(None, description="Business ID"),
    expires_in: int = Query(3600, ge=60, le=86400, description="Expiry time in seconds"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get download URL via direct /api/v1/artifacts/ endpoint."""
    if not business_id:
        art = db.execute(select(Artifact).where(Artifact.id == artifact_id)).scalar_one_or_none()
        if not art:
            raise ArtifactNotFoundException(message=f"Artifact #{artifact_id} not found")
        business_id = art.business_id

    _verify_user_business_role(db, current_user, business_id)
    return artifact_handler.get_download_url_handler(business_id, artifact_id, expires_in, db)


@direct_router.get("/{artifact_id}/download")
def direct_download_artifact(
    artifact_id: int,
    token: Optional[str] = Query(None, description="Signed download token"),
    business_id: Optional[int] = Query(None, description="Business ID"),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Download artifact via direct /api/v1/artifacts/{artifact_id}/download endpoint."""
    if token:
        biz_id = verify_download_token(token, artifact_id)
        return artifact_handler.download_artifact_handler(biz_id, artifact_id, db)

    # Fallback to Bearer token
    auth_header = request.headers.get("Authorization") if request else None
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AuthenticationException(
            message="Authentication required: provide Bearer token or signed download token",
            errors={"authentication": "Missing credentials"},
        )
    bearer_token = auth_header[7:].strip()
    payload = decode_access_token(bearer_token)
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise AuthenticationException(message="User not found")

    if not business_id:
        art = db.execute(select(Artifact).where(Artifact.id == artifact_id)).scalar_one_or_none()
        if not art:
            raise ArtifactNotFoundException(message=f"Artifact #{artifact_id} not found")
        business_id = art.business_id

    _verify_user_business_role(db, user, business_id)
    return artifact_handler.download_artifact_handler(business_id, artifact_id, db)


@direct_router.delete("/{artifact_id}", status_code=200)
def direct_delete_artifact(
    artifact_id: int,
    business_id: Optional[int] = Query(None, description="Business ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete artifact via direct /api/v1/artifacts/ endpoint."""
    if not business_id:
        art = db.execute(select(Artifact).where(Artifact.id == artifact_id)).scalar_one_or_none()
        if not art:
            raise ArtifactNotFoundException(message=f"Artifact #{artifact_id} not found")
        business_id = art.business_id

    _verify_user_business_role(db, current_user, business_id, ["owner", "admin"])
    return artifact_handler.delete_artifact_handler(business_id, artifact_id, db)
