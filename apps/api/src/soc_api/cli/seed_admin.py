"""Seed or rotate the bootstrap admin user.

Usage:
    python -m soc_api.cli.seed_admin
    python -m soc_api.cli.seed_admin --rotate

The password is read interactively via getpass, never accepted as a CLI
argument or environment variable, to keep it out of shell history,
process listings, and CI logs.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from typing import NoReturn

from sqlalchemy import select

from soc_api.db import SessionLocal
from soc_api.models.orm import User
from soc_api.security import MIN_PASSWORD_LENGTH, hash_password


def _prompt_email() -> str:
    email = input("Admin email: ").strip().lower()
    if not email or "@" not in email:
        _exit("Invalid email.")
    return email


def _prompt_password() -> str:
    while True:
        first = getpass.getpass("Password (min 12 chars): ")
        if len(first) < MIN_PASSWORD_LENGTH:
            print(f"Too short ({len(first)} < {MIN_PASSWORD_LENGTH}).")
            continue
        second = getpass.getpass("Confirm password: ")
        if first != second:
            print("Passwords do not match. Try again.")
            continue
        return first


def _exit(msg: str) -> NoReturn:
    print(msg, file=sys.stderr)
    sys.exit(1)


async def seed_admin(rotate: bool) -> None:
    email = _prompt_email()
    password = _prompt_password()
    password_hash = hash_password(password)

    async with SessionLocal() as session:
        existing = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

        if existing and not rotate:
            _exit(
                f"User already exists: {email}. Re-run with --rotate to update password."
            )

        if existing:
            existing.password_hash = password_hash
            existing.role = "admin"
            await session.commit()
            print(f"Rotated password for admin user {email} (id={existing.id}).")
        else:
            user = User(email=email, password_hash=password_hash, role="admin")
            session.add(user)
            await session.commit()
            await session.refresh(user)
            print(f"Created admin user {email} (id={user.id}).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="Update the password if the user already exists.",
    )
    args = parser.parse_args()
    asyncio.run(seed_admin(rotate=args.rotate))


if __name__ == "__main__":
    main()
