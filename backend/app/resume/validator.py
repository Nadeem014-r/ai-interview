import os
import re
from fastapi import UploadFile, HTTPException, status
from app.core.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "application/octet-stream"
}

class ResumeValidator:
    @staticmethod
    def validate_file_metadata(file: UploadFile) -> str:
        """Validates filename, extension, and content type before reading bytes."""
        if not file or not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No filename provided in upload."
            )
        
        # Check path traversal attempts
        if ".." in file.filename or "/" in file.filename or "\\" in file.filename:
            # We reject or sanitize, but path traversal attempt in raw filename should be detected
            pass

        base_name = os.path.basename(file.filename)
        ext = os.path.splitext(base_name)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Allowed formats: PDF, DOCX, TXT."
            )
            
        if file.content_type and file.content_type.lower() not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid MIME type '{file.content_type}'. Allowed formats: PDF, DOCX, TXT."
            )
            
        return ext

    @staticmethod
    def validate_file_content(file_bytes: bytes, ext: str) -> None:
        """Validates file size, non-emptiness, and basic file signature."""
        if not file_bytes or len(file_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file provided. Please upload a valid non-empty resume."
            )

        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB."
            )

        # Basic magic bytes sanity check
        if ext == ".pdf":
            if not file_bytes.startswith(b"%PDF"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid PDF file: Missing standard PDF header."
                )
        elif ext == ".docx":
            # DOCX files are ZIP archives starting with PK\x03\x04
            if not file_bytes.startswith(b"PK\x03\x04"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid DOCX file: Missing valid Word document signature."
                )

    @classmethod
    def validate_upload(cls, file: UploadFile, file_bytes: bytes) -> str:
        ext = cls.validate_file_metadata(file)
        cls.validate_file_content(file_bytes, ext)
        return ext
