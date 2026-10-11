"""Resume file storage, extraction, and validation service."""
import os
from werkzeug.utils import secure_filename
from pypdf import PdfReader
from flask import current_app
from app.utils.security import generate_safe_storage_filename
from app.utils.validators import validate_pdf_file

class ResumeService:

    @staticmethod
    def get_storage_dir():
        """Get or create private instance folder for resumes outside public static."""
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "instance/private_resumes")
        if not os.path.isabs(upload_folder):
            upload_folder = os.path.join(current_app.root_path, "..", upload_folder)
        upload_folder = os.path.abspath(upload_folder)
        os.makedirs(upload_folder, exist_ok=True)
        return upload_folder

    @classmethod
    def save_and_extract_text(cls, file_storage):
        """
        Validates, saves PDF into private storage with randomized name,
        and extracts readable text.
        Returns (success: bool, data_or_error: dict|str).
        """
        max_mb = current_app.config.get("MAX_RESUME_MB", 5)
        is_valid, msg = validate_pdf_file(file_storage, max_size_mb=max_mb)
        if not is_valid:
            return False, msg

        storage_dir = cls.get_storage_dir()
        safe_filename = generate_safe_storage_filename(file_storage.filename)
        file_path = os.path.join(storage_dir, safe_filename)

        file_storage.seek(0)
        file_storage.save(file_path)

        # Extract text using pypdf
        extracted_text = ""
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    extracted_text += page_text + "\n"
        except Exception as e:
            # Clean up on failure
            if os.path.exists(file_path):
                os.remove(file_path)
            current_app.logger.warning("PDF extraction failed: %s", type(e).__name__)
            return False, "Could not extract text from this PDF. Please upload a readable, unencrypted PDF."

        extracted_text = extracted_text.strip()
        if len(extracted_text) < 50:
            try:
                os.remove(file_path)
            except OSError:
                current_app.logger.warning("Could not remove unprocessable uploaded resume")
            return False, "This PDF contains too little extractable text. Scanned PDFs may require OCR; please upload a text-readable PDF."

        # Cap text to 50,000 characters to prevent prompt overflow or memory exhaustion
        if len(extracted_text) > 50000:
            extracted_text = extracted_text[:50000]

        return True, {
            "storage_name": safe_filename,
            "original_name": secure_filename(file_storage.filename or "resume.pdf")[:180] or "resume.pdf",
            "text": extracted_text,
            "file_path": file_path
        }

    @classmethod
    def delete_file(cls, storage_name):
        """Safely delete private resume file."""
        if not storage_name:
            return
        storage_dir = cls.get_storage_dir()
        file_path = os.path.join(storage_dir, os.path.basename(storage_name))
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                current_app.logger.error(f"Error deleting file {file_path}: {e}")
