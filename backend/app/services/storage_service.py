import os
import uuid
import logging
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException, status
from app.core.config import settings

logger = logging.getLogger("srmp.storage")

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
DEFAULT_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

# Local static base directory
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "static")


class StorageService:
    def __init__(self):
        self.backend = (settings.STORAGE_BACKEND or "local").lower()
        self.s3_client = None
        if self.backend == "s3":
            if not settings.S3_BUCKET_NAME or not settings.S3_ACCESS_KEY_ID or not settings.S3_SECRET_ACCESS_KEY:
                logger.warning("STORAGE_BACKEND is 's3' but required S3 credentials are missing. Falling back to local storage.")
                self.backend = "local"
            else:
                try:
                    import boto3
                    client_kwargs = {
                        "aws_access_key_id": settings.S3_ACCESS_KEY_ID,
                        "aws_secret_access_key": settings.S3_SECRET_ACCESS_KEY,
                    }
                    if settings.S3_ENDPOINT_URL:
                        client_kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
                    if settings.S3_REGION:
                        client_kwargs["region_name"] = settings.S3_REGION

                    self.s3_client = boto3.client("s3", **client_kwargs)
                    logger.info("S3 / Cloudflare R2 client initialized successfully.")
                except Exception as e:
                    logger.error(f"Failed to initialize S3 client: {e}. Falling back to local storage.")
                    self.backend = "local"

    def validate_image_file(self, filename: str, content_type: str, content: bytes, max_size_bytes: int = DEFAULT_MAX_FILE_SIZE) -> str:
        """
        Validates extension, MIME type, size limit, and header magic bytes.
        Returns the sanitized file extension.
        """
        ext = os.path.splitext(filename or "")[1].lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file extension '{ext}'. Only JPEG, PNG, and WebP images are allowed."
            )

        if content_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid MIME type '{content_type}'. Must be image/jpeg, image/png, or image/webp."
            )

        if len(content) > max_size_bytes:
            max_mb = int(max_size_bytes / (1024 * 1024))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds maximum allowed limit of {max_mb}MB."
            )

        # Magic Bytes Validation
        is_valid_magic = False
        if ext in [".jpg", ".jpeg"] and content.startswith(b"\xff\xd8\xff"):
            is_valid_magic = True
        elif ext == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n"):
            is_valid_magic = True
        elif ext == ".webp" and content.startswith(b"RIFF") and b"WEBP" in content[8:12]:
            is_valid_magic = True

        if not is_valid_magic:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Corrupted or invalid image header. File signature does not match image format."
            )

        return ext

    async def save_image(
        self,
        file: UploadFile,
        folder: str = "feedback",
        prefix: str = "img",
        max_size_bytes: int = DEFAULT_MAX_FILE_SIZE
    ) -> dict:
        """
        Reads, validates, and stores an uploaded image to S3/R2 or local persistent storage.
        Returns dictionary with file metadata and public URL.
        """
        content = await file.read()
        ext = self.validate_image_file(
            filename=file.filename or "",
            content_type=file.content_type or "",
            content=content,
            max_size_bytes=max_size_bytes
        )

        unique_filename = f"{prefix}_{uuid.uuid4().hex}{ext}"

        if self.backend == "s3" and self.s3_client:
            key = f"uploads/{folder}/{unique_filename}"
            try:
                put_kwargs = {
                    "Bucket": settings.S3_BUCKET_NAME,
                    "Key": key,
                    "Body": content,
                    "ContentType": file.content_type,
                }
                if not settings.S3_ENDPOINT_URL:
                    put_kwargs["ACL"] = "public-read"
                self.s3_client.put_object(**put_kwargs)
                if settings.S3_PUBLIC_BASE_URL:
                    base_url = settings.S3_PUBLIC_BASE_URL.rstrip("/")
                    public_url = f"{base_url}/{key}"
                elif settings.S3_ENDPOINT_URL:
                    public_url = f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{settings.S3_BUCKET_NAME}/{key}"
                else:
                    public_url = f"https://{settings.S3_BUCKET_NAME}.s3.{settings.S3_REGION}.amazonaws.com/{key}"

                return {
                    "photo_url": public_url,
                    "storage_backend": "s3",
                    "file_size_bytes": len(content),
                    "mime_type": file.content_type,
                    "key": key
                }
            except Exception as e:
                logger.error(f"S3 upload failed: {e}. Falling back to local storage.")
                # Fallback to local storage if S3 upload raises unexpected runtime error

        # Local storage fallback / default
        local_dir = os.path.join(STATIC_DIR, "uploads", folder)
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, unique_filename)

        with open(local_path, "wb") as f:
            f.write(content)

        public_url = f"/static/uploads/{folder}/{unique_filename}"
        return {
            "photo_url": public_url,
            "storage_backend": "local",
            "file_size_bytes": len(content),
            "mime_type": file.content_type,
            "key": unique_filename,
            "folder": folder
        }

    def get_file(self, key: str, folder: str = "feedback") -> Optional[bytes]:
        """
        Retrieves raw file bytes from S3/R2 or local persistent storage.
        """
        if self.backend == "s3" and self.s3_client:
            try:
                response = self.s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
                return response["Body"].read()
            except Exception as e:
                logger.error(f"S3 get_object error for key '{key}': {e}")
                return None

        # Local storage
        local_path = os.path.join(STATIC_DIR, "uploads", folder, os.path.basename(key))
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                return f.read()
        return None

    def delete_file(self, key: str, folder: str = "feedback") -> bool:
        """
        Deletes a file from S3/R2 or local persistent storage.
        """
        if self.backend == "s3" and self.s3_client:
            try:
                self.s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
                return True
            except Exception as e:
                logger.error(f"S3 delete_object error for key '{key}': {e}")
                return False

        # Local storage
        local_path = os.path.join(STATIC_DIR, "uploads", folder, os.path.basename(key))
        if os.path.exists(local_path):
            os.remove(local_path)
            return True
        return False


storage_service = StorageService()
