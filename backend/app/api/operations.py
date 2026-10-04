"""
SecureStego — Operations API Routes

Endpoints for querying operation history (Recent Activity).
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.postgres import get_db
from app.models.db_models import Operation, User
from app.services.storage_service import stream_file
from pydantic import BaseModel
from datetime import datetime
from fastapi.responses import StreamingResponse
from fastapi import HTTPException, status

router = APIRouter(prefix="/operations", tags=["operations"])

class RecentOperationResponse(BaseModel):
    operation_id: str
    operation_type: str
    mode: str
    image_filename: str
    status: str
    created_at: datetime
    recipient_username: str | None = None

@router.get(
    "/recent",
    response_model=list[RecentOperationResponse],
    summary="Get recent operations",
    description="Returns the current user's recent encode/decode operations.",
)
async def get_recent_operations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch the latest 10 operations for the current user."""
    stmt = (
        select(Operation, User.username.label("recipient_username"))
        .outerjoin(User, Operation.recipient_id == User.id)
        .where(
            (Operation.sender_id == current_user.id) | 
            (Operation.recipient_id == current_user.id)
        )
        .order_by(desc(Operation.created_at))
        .limit(10)
    )
    result = await db.execute(stmt)
    
    recent_ops = []
    for op, recipient_username in result.all():
        recent_ops.append(
            RecentOperationResponse(
                operation_id=op.operation_id,
                operation_type=op.operation_type,
                mode=op.mode,
                image_filename=op.image_filename,
                status=op.status,
                created_at=op.created_at,
                recipient_username=recipient_username,
            )
        )
        
    return recent_ops

@router.get(
    "/{operation_id}/download",
    summary="Download operation file",
    description="Download the stego image securely through the backend.",
)
async def download_operation_file(
    operation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Fetch the operation
    result = await db.execute(
        select(Operation).where(Operation.operation_id == operation_id)
    )
    op = result.scalar_one_or_none()
    if not op:
        raise HTTPException(status_code=404, detail="Operation not found")

    # Authorize: user must be sender or recipient
    if op.sender_id != current_user.id and op.recipient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to download this file")

    if not op.storage_path:
        raise HTTPException(status_code=404, detail="File not available")

    # Stream the file back
    try:
        file_stream = stream_file(op.storage_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return StreamingResponse(
        file_stream, 
        media_type="image/png", 
        headers={"Content-Disposition": f'attachment; filename="{op.image_filename or "stego.png"}"'}
    )
