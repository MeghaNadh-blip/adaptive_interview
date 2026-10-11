"""Validation utilities for URLs, inputs, and PDF files."""
import re
import os

GITHUB_URL_REGEX = re.compile(
    r"^https?://(www\.)?github\.com/[A-Za-z0-9_-]+/?$"
)

LINKEDIN_URL_REGEX = re.compile(
    r"^https?://([a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9_-]+/?$"
)

def validate_github_url(url):
    """Validate that the URL belongs to a valid GitHub user profile and prevent SSRF."""
    if not url:
        return False, "GitHub profile URL is mandatory."
    url = url.strip()
    if not GITHUB_URL_REGEX.match(url):
        return False, "Invalid GitHub profile URL format. Example: https://github.com/username"
    return True, url

def validate_linkedin_url(url):
    """Validate optional LinkedIn URL."""
    if not url or not url.strip():
        return True, ""  # Optional
    url = url.strip()
    if not LINKEDIN_URL_REGEX.match(url):
        return False, "Invalid LinkedIn profile URL format. Example: https://linkedin.com/in/username"
    return True, url

def validate_pdf_file(file_storage, max_size_mb=5):
    """
    Validate that the uploaded file is a genuine PDF within size limits.
    Checks file extension, file size, and the standard %PDF- header magic bytes.
    """
    if not file_storage or file_storage.filename == "":
        return False, "No resume file selected."

    filename = file_storage.filename
    if not filename.lower().endswith(".pdf"):
        return False, "Only PDF (.pdf) documents are accepted."

    # Check magic bytes for PDF signature
    header = file_storage.read(5)
    file_storage.seek(0)  # Reset pointer
    if header != b"%PDF-":
        return False, "Invalid file content: Not a valid PDF document."

    # Check size
    file_storage.seek(0, os.SEEK_END)
    size_bytes = file_storage.tell()
    file_storage.seek(0)  # Reset pointer

    max_bytes = max_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        return False, f"File exceeds maximum allowed size of {max_size_mb} MB."

    if size_bytes < 100:
        return False, "Uploaded PDF file appears to be empty or corrupted."

    return True, "Valid PDF"
