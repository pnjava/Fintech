"""Routes for file upload pipelines."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.routes.auth import AuthenticatedUser, require_role
from app.services.uploads import ShareholderUploadResult, ShareholderUploadService

router = APIRouter(prefix="/uploads")


@router.post("/shareholders", status_code=status.HTTP_202_ACCEPTED)
async def upload_shareholders(
    request: Request,
    user: AuthenticatedUser = Depends(require_role("ADMIN", "OPS", "COMPLIANCE")),
) -> dict[str, str]:
    request.state.actor_email = user.email
    request.state.tenant_id = user.tenant_id

    body = await request.body()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    content_type = request.headers.get("content-type", "application/octet-stream").split(";")[0]
    filename = request.headers.get("x-upload-filename")

    service = ShareholderUploadService()
    result: ShareholderUploadResult = service.handle_upload(
        tenant_id=user.tenant_id,
        file_bytes=body,
        filename=filename,
        content_type=content_type,
    )

    return {
        "upload_id": result.upload_id,
        "location": result.location,
        "status": "QUEUED",
    }


__all__ = ["router", "upload_shareholders"]
