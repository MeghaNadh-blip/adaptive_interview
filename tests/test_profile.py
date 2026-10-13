"""Automated unit tests for Candidate Profile & validation logic."""
import pytest
from app.utils.validators import validate_github_url, validate_linkedin_url
from app.models import CandidateProfileModel

def test_github_url_validation():
    """Verify GitHub URL validator blocks invalid formats and malicious URLs."""
    valid, _ = validate_github_url("https://github.com/torvalds")
    assert valid is True

    valid_slash, _ = validate_github_url("https://github.com/octocat/")
    assert valid_slash is True

    # Invalid URLs
    invalid1, msg1 = validate_github_url("https://evil-site.com/octocat")
    assert invalid1 is False

    invalid2, msg2 = validate_github_url("not_a_url")
    assert invalid2 is False

    invalid_empty, msg3 = validate_github_url("")
    assert invalid_empty is False

def test_linkedin_url_validation():
    """Verify LinkedIn validator allows valid or empty optional values."""
    # Optional empty should pass
    valid_empty, _ = validate_linkedin_url("")
    assert valid_empty is True

    valid_li, _ = validate_linkedin_url("https://linkedin.com/in/john-doe")
    assert valid_li is True

    invalid_li, _ = validate_linkedin_url("https://twitter.com/fake")
    assert invalid_li is False

def test_profile_completion_calculation():
    """Test completion percentage logic."""
    empty_completion = CandidateProfileModel.calculate_completion({})
    assert empty_completion["percentage"] == 0
    assert empty_completion["is_ready_for_interview"] is False

    partial_completion = CandidateProfileModel.calculate_completion({
        "resume_text": "Sample resume text...",
        "github_url": "https://github.com/testuser"
    })
    assert partial_completion["percentage"] == 80
    assert partial_completion["is_ready_for_interview"] is False

    full_completion = CandidateProfileModel.calculate_completion({
        "resume_text": "Sample resume text...",
        "github_url": "https://github.com/testuser",
        "target_role": "Python Developer"
    })
    assert full_completion["percentage"] == 100
    assert full_completion["is_ready_for_interview"] is True
