import os
import uuid
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, UploadFile, status


s3_client = boto3.client("s3")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

MAX_INCIDENT_MEDIA_SIZE_MB = int(
    os.getenv("MAX_INCIDENT_MEDIA_SIZE_MB", "100")
)
MAX_INCIDENT_MEDIA_SIZE_BYTES = MAX_INCIDENT_MEDIA_SIZE_MB * 1024 * 1024

ALLOWED_INCIDENT_MEDIA_TYPES = {
    "image/jpeg",
    "image/png",
    "video/mp4",
    "video/quicktime",
}

ALLOWED_RESPONSE_EVIDENCE_TYPES = {
    "image/jpeg",
    "image/png",
}


def upload_file_to_s3(file: UploadFile, agency_id: int) -> str:
    """Upload an agency document to the configured S3 bucket."""

    if not S3_BUCKET_NAME:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="S3 bucket is not configured.",
        )

    original_filename = Path(file.filename or "uploaded_file").name
    object_key = f"agencies/{agency_id}/{uuid.uuid4()}-{original_filename}"

    try:
        s3_client.upload_fileobj(
            file.file,
            S3_BUCKET_NAME,
            object_key,
            ExtraArgs={
                "ContentType": file.content_type or "application/octet-stream"
            },
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file.",
        ) from exc

    return f"s3://{S3_BUCKET_NAME}/{object_key}"


def upload_incident_media_to_s3(
    file: UploadFile,
    incident_id: int,
) -> str:
    """Validate and upload incident image/video to S3."""

    if not S3_BUCKET_NAME:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="S3 bucket is not configured.",
        )

    if file.content_type not in ALLOWED_INCIDENT_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported media type. Allowed types are JPEG, PNG, MP4, "
                "and MOV."
            ),
        )

    original_filename = Path(file.filename or "uploaded_media").name

    # Check the uploaded file size before sending it to S3.
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > MAX_INCIDENT_MEDIA_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File is too large. Maximum allowed size is "
                f"{MAX_INCIDENT_MEDIA_SIZE_MB} MB."
            ),
        )

    object_key = (
        f"incidents/{incident_id}/{uuid.uuid4()}-{original_filename}"
    )

    try:
        s3_client.upload_fileobj(
            file.file,
            S3_BUCKET_NAME,
            object_key,
            ExtraArgs={
                "ContentType": file.content_type,
            },
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload incident media.",
        ) from exc

    return f"s3://{S3_BUCKET_NAME}/{object_key}"


def generate_presigned_url(s3_url: str, expiration: int = 3600) -> str:
    """Generate a temporary HTTPS URL for a private S3 object."""

    if not S3_BUCKET_NAME:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="S3 bucket is not configured.",
        )

    if not s3_url.startswith("s3://"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid S3 object reference.",
        )

    s3_path = s3_url[5:]
    bucket_name, object_key = s3_path.split("/", 1)

    if bucket_name != S3_BUCKET_NAME:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid S3 bucket reference.",
        )

    try:
        return s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket_name,
                "Key": object_key,
            },
            ExpiresIn=expiration,
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate media URL.",
        ) from exc


def upload_response_evidence_to_s3(
    file: UploadFile,
    assignment_id: int,
) -> str:
    """Validate and upload responder completion evidence to S3."""

    if not S3_BUCKET_NAME:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="S3 bucket is not configured.",
        )

    if file.content_type not in ALLOWED_RESPONSE_EVIDENCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported evidence type. Only JPEG and PNG images are allowed.",
        )

    original_filename = Path(
        file.filename or "response_evidence"
    ).name

    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > MAX_INCIDENT_MEDIA_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File is too large. Maximum allowed size is "
                f"{MAX_INCIDENT_MEDIA_SIZE_MB} MB."
            ),
        )

    object_key = (
        f"responder-evidence/"
        f"{assignment_id}/"
        f"{uuid.uuid4()}-{original_filename}"
    )

    try:
        s3_client.upload_fileobj(
            file.file,
            S3_BUCKET_NAME,
            object_key,
            ExtraArgs={
                "ContentType": file.content_type,
            },
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload response evidence.",
        ) from exc

    return f"s3://{S3_BUCKET_NAME}/{object_key}"
