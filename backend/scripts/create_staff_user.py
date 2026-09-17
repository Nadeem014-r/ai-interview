"""Provision an admin or placement_staff account from the command line.

Public registration always creates candidates, so staff accounts -- needed for
staff-only endpoints such as POST /api/v1/research/company -- are created here
by an operator with direct database access. Nothing is exposed over HTTP.

The password is never taken as an argument (it would land in shell history and
process listings). It is read from the STAFF_USER_PASSWORD environment variable
when set, otherwise prompted for twice without echo.

Usage (from backend/):
    python -m scripts.create_staff_user --email staff@college.edu --full-name "Placement Officer" --role placement_staff
    python -m scripts.create_staff_user --email existing@college.edu --role admin --promote

After provisioning, log in through POST /api/v1/auth/login as usual; the role is
written into the JWT at login.
"""

import argparse
import asyncio
import getpass
import os
import sys
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.db.models import User

STAFF_ROLES = ("admin", "placement_staff")
MIN_PASSWORD_LENGTH = 12
PASSWORD_ENV_VAR = "STAFF_USER_PASSWORD"


class ProvisioningError(Exception):
    """Raised when a staff account cannot be provisioned as requested."""


async def provision_staff_user(
    db: AsyncSession,
    email: str,
    role: str,
    full_name: Optional[str] = None,
    password: Optional[str] = None,
    promote: bool = False,
) -> User:
    """Create a new staff user, or promote an existing active user when promote=True.

    Refuses to touch an existing account unless promotion was asked for, so a
    typo cannot silently grant staff access to someone else's account.
    """
    if role not in STAFF_ROLES:
        raise ProvisioningError(f"role must be one of {', '.join(STAFF_ROLES)}.")

    normalized_email = (email or "").strip().lower()
    if not normalized_email or "@" not in normalized_email:
        raise ProvisioningError("A valid email address is required.")

    res = await db.execute(select(User).where(func.lower(User.email) == normalized_email))
    existing = res.scalars().first()

    if existing:
        if not promote:
            raise ProvisioningError(
                "An account with this email already exists. Re-run with --promote to change its role."
            )
        if not existing.is_active:
            raise ProvisioningError("That account is inactive; refusing to promote it.")
        existing.role = role
        await db.commit()
        await db.refresh(existing)
        return existing

    if promote:
        raise ProvisioningError("No account with this email exists to promote.")
    if not full_name or not full_name.strip():
        raise ProvisioningError("--full-name is required when creating a new account.")
    if not password or len(password.strip()) < MIN_PASSWORD_LENGTH:
        raise ProvisioningError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")

    user = User(
        email=normalized_email,
        hashed_password=get_password_hash(password),
        full_name=full_name.strip(),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _read_password() -> str:
    from_env = os.environ.get(PASSWORD_ENV_VAR)
    if from_env:
        return from_env
    if not sys.stdin.isatty():
        # getpass would block waiting on a console that is not there.
        raise ProvisioningError(f"No terminal to prompt on; set {PASSWORD_ENV_VAR} instead.")
    first = getpass.getpass("Password: ")
    if first != getpass.getpass("Confirm password: "):
        raise ProvisioningError("Passwords do not match.")
    return first


async def _main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Create or promote an admin/placement_staff account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True, choices=STAFF_ROLES)
    parser.add_argument("--full-name")
    parser.add_argument("--promote", action="store_true", help="Change the role of an existing active account.")
    args = parser.parse_args(argv)

    from app.core.database import AsyncSessionLocal

    try:
        password = None if args.promote else _read_password()
        async with AsyncSessionLocal() as db:
            user = await provision_staff_user(
                db,
                email=args.email,
                role=args.role,
                full_name=args.full_name,
                password=password,
                promote=args.promote,
            )
    except ProvisioningError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    action = "Promoted" if args.promote else "Created"
    print(f"{action} user #{user.id} ({user.email}) with role '{user.role}'. Log in via POST /api/v1/auth/login.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
