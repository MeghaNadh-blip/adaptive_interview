"""Provision a recruiter account from a trusted local/admin terminal."""
from getpass import getpass

from pymongo.errors import DuplicateKeyError
from app import create_app
from app.models import User


def main():
    app = create_app()
    with app.app_context():
        full_name = input("Recruiter full name: ").strip()
        email = input("Recruiter email: ").strip().lower()
        password = getpass("Recruiter password (12+ characters): ")
        confirm = getpass("Confirm password: ")
        if not full_name or len(full_name) > 100:
            raise SystemExit("Name must be between 1 and 100 characters.")
        if len(password) < 12 or len(password.encode("utf-8")) > 72:
            raise SystemExit("Password must be at least 12 characters and at most 72 UTF-8 bytes.")
        if password != confirm:
            raise SystemExit("Passwords do not match.")
        if User.get_by_email(email):
            raise SystemExit("An account with this email already exists.")
        try:
            User.create(full_name=full_name, email=email, password=password, role="recruiter")
        except DuplicateKeyError:
            raise SystemExit("An account with this email already exists.")
        print("Recruiter account created. Keep this account restricted to authorized reviewers.")


if __name__ == "__main__":
    main()
