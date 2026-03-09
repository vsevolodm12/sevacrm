#!/usr/bin/env python3
"""
Initialize the database and create an admin user.

Usage:
    python init_db.py --username admin --password yourpassword
"""

import argparse
import sys

from app.auth import get_password_hash
from app.database import Base, SessionLocal, engine
from app.models.models import User  # noqa: F401 - ensure all models are imported


def init_db():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")


def create_user(username: str, password: str) -> None:
    """Create an admin user."""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"User '{username}' already exists.")
            return

        hashed = get_password_hash(password)
        user = User(username=username, hashed_password=hashed)
        db.add(user)
        db.commit()
        print(f"User '{username}' created successfully.")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Initialize SevaCRM database and create admin user.")
    parser.add_argument("--username", type=str, default="admin", help="Admin username (default: admin)")
    parser.add_argument("--password", type=str, required=True, help="Admin password")
    args = parser.parse_args()

    if len(args.password) < 4:
        print("Error: password must be at least 4 characters long.", file=sys.stderr)
        sys.exit(1)

    init_db()
    create_user(args.username, args.password)


if __name__ == "__main__":
    main()
