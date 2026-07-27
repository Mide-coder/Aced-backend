import uuid
import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Request
from sqlmodel import Session, select

from app.database import get_session
from app.models import TutorProfile
from app.auth import get_current_user
from app.config import settings
from app.rate_limit import limiter

router = APIRouter(prefix="/media", tags=["Media"])

# Allowed video MIME types
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm"}

# Max file size: 100MB (2-min demo video)
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024


def get_r2_client():
    """Get a boto3 S3 client configured for Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


# ── Upload Demo Video [E002-S03] ──────────────────────────────────────────────

@router.post("/upload/demo-video", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def upload_demo_video(
    request: Request,
    file: UploadFile = File(..., description="Demo video (MP4, MOV, WEBM). Max 2 minutes."),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Upload a tutor demo video to Cloudflare R2.
    - Only tutors can upload
    - UUID filename to prevent PII leakage
    - Stateless: no local file storage
    - Supported formats: MP4, MOV, WEBM
    - Max size: 100MB
    """
    # Only tutors can upload demo videos
    if current_user.get("role") != "tutor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tutors can upload demo videos",
        )

    # Validate MIME type
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{file.content_type}'. Allowed: MP4, MOV, WEBM",
        )

    # Read file and check size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 100MB",
        )

    # Get tutor profile
    user_id = int(current_user["sub"])
    profile = session.exec(
        select(TutorProfile).where(TutorProfile.user_id == user_id)
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tutor profile not found. Create a profile first.",
        )

    # Generate UUID filename — no PII in the path
    extension = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "mp4"
    unique_filename = f"demo-videos/{uuid.uuid4()}.{extension}"

    # Upload to Cloudflare R2
    try:
        r2 = get_r2_client()
        r2.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=unique_filename,
            Body=file_bytes,
            ContentType=file.content_type,
        )
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload to storage: {str(e)}",
        )

    # Build public URL and save to tutor profile
    video_url = f"https://{settings.R2_BUCKET_NAME}.{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com/{unique_filename}"

    profile.demo_video_url = video_url
    session.add(profile)
    session.commit()

    return {
        "message": "Demo video uploaded successfully",
        "video_url": video_url,
        "filename": unique_filename,
    }


# ── Upload Matric ID [E001-S04] ───────────────────────────────────────────────

@router.post("/upload/matric-id", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def upload_matric_id(
    request: Request,
    file: UploadFile = File(..., description="Matric ID image (JPG, PNG, PDF)"),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a matric ID to Cloudflare R2 for manual verification.
    Storage path: matric-ids/{user_id}/{uuid}.{ext}
    - UUID filename prevents PII leakage in the URL
    - Manual review required by Mide after upload
    """
    allowed_types = {"image/jpeg", "image/png", "application/pdf"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed: JPG, PNG, PDF",
        )

    max_size = 10 * 1024 * 1024  # 10MB
    file_bytes = await file.read()
    if len(file_bytes) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 10MB",
        )

    user_id = int(current_user["sub"])
    extension = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"

    # Storage path schema: matric-ids/{user_id}/{uuid}.{ext}
    unique_filename = f"matric-ids/{user_id}/{uuid.uuid4()}.{extension}"

    try:
        r2 = get_r2_client()
        r2.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=unique_filename,
            Body=file_bytes,
            ContentType=file.content_type,
        )
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload to storage: {str(e)}",
        )

    return {
        "message": "Matric ID uploaded successfully. Manual review pending.",
        "path": unique_filename,
        "status": "pending_verification",
    }
