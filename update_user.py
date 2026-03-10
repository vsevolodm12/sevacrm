#!/usr/bin/env python3
"""
Update or create a user in the database.

Usage:
    python update_user.py --old-username admin --new-username seva@hren.com --password newpass
    python update_user.py --new-username seva@hren.com --password newpass  # create if not exists
"""

import argparse
import sys

from app.auth import get_password_hash
from app.database import Base, SessionLocal, engine
from app.models.models import User  # noqa: F401


def update_user(old_username: str | None, new_username: str, password: str) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if old_username:
            user = db.query(User).filter(User.username == old_username).first()
            if not user:
                print(f"User '{old_username}' not found.", file=sys.stderr)
                sys.exit(1)
            user.username = new_username
            user.hashed_password = get_password_hash(password)
            db.commit()
            print(f"User updated: '{old_username}' -> '{new_username}'")
        else:
            user = db.query(User).filter(User.username == new_username).first()
            if user:
                user.hashed_password = get_password_hash(password)
                db.commit()
                print(f"Password updated for '{new_username}'")
            else:
                user = User(username=new_username, hashed_password=get_password_hash(password))
                db.add(user)
                db.commit()
                print(f"User '{new_username}' created")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-username", type=str, default=None)
    parser.add_argument("--new-username", type=str, required=True)
    parser.add_argument("--password", type=str, required=True)
    args = parser.parse_args()
    update_user(args.old_username, args.new_username, args.password)


if __name__ == "__main__":
    main()
