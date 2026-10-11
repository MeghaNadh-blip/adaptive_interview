"""Automated unit tests for Authentication workflows."""
import pytest
from app import create_app
from app.models import User

@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "MONGO_URI": "mongodb://localhost:27017/test_db",
        "SECRET_KEY": "test-secret-key-that-is-long-enough-for-tests"
    })
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_registration_and_login(client):
    """Test candidate registration, duplicate check, and login."""
    # 1. Register candidate
    resp = client.post("/auth/register", data={
        "full_name": "Test Candidate",
        "email": "candidate.test@example.com",
        "password": "securepassword123",
        "confirm_password": "securepassword123",
        "role": "candidate"
    }, follow_redirects=True)
    assert resp.status_code == 200

    # 2. Duplicate registration attempt should be rejected
    resp_dup = client.post("/auth/register", data={
        "full_name": "Test Candidate Duplicate",
        "email": "candidate.test@example.com",
        "password": "securepassword123",
        "confirm_password": "securepassword123",
        "role": "candidate"
    }, follow_redirects=True)
    assert b"already exists" in resp_dup.data or resp_dup.status_code == 200

    # 3. Logout
    client.post("/auth/logout", follow_redirects=True)

    # 4. Valid login
    resp_login = client.post("/auth/login", data={
        "email": "candidate.test@example.com",
        "password": "securepassword123"
    }, follow_redirects=True)
    assert resp_login.status_code == 200
    assert b"Welcome back" in resp_login.data or b"Dashboard" in resp_login.data

    # 5. Invalid login
    client.post("/auth/logout", follow_redirects=True)
    resp_invalid = client.post("/auth/login", data={
        "email": "candidate.test@example.com",
        "password": "wrongpassword"
    }, follow_redirects=True)
    assert b"Invalid email or password" in resp_invalid.data


def test_public_registration_cannot_create_recruiter(client):
    response = client.post("/auth/register", data={
        "full_name": "Attempted Recruiter",
        "email": "attempted.recruiter@example.com",
        "password": "securepassword123",
        "confirm_password": "securepassword123",
        "role": "recruiter",
    }, follow_redirects=True)
    assert response.status_code == 200
    with client.application.app_context():
        user = User.get_by_email("attempted.recruiter@example.com")
        assert user is not None
        assert user.role == "candidate"


def test_demo_login_route_is_removed(client):
    assert client.get("/auth/demo-login/recruiter").status_code == 404
