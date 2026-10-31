"""Create an account from the command line: the first platform admin, or demo accounts.

Usage (from backend/):
    uv run python -m scripts.create_user --role admin --email admin@example.com --name "Platform Admin"
    uv run python -m scripts.create_user --role recruiter --email rh@demo.test --name "Rania" --company "Demo company"
    uv run python -m scripts.create_user --role candidate --email samira@example.com --name "Samira"

Without --password a random one is generated and printed once. A recruiter's company is created (active) if missing.
"""

from __future__ import annotations

import argparse

from sqlalchemy import select

from app.db import OrganizationRecord, OrganizationStatus, Role, new_session
from app.services.accounts import AccountError, create_user, temporary_password


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--role", choices=[r.value for r in Role], required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--company", help="Recruiters only: the company name.")
    parser.add_argument("--password", help="Default: a generated password, printed once.")
    args = parser.parse_args()

    password = args.password or temporary_password()
    with new_session() as db:
        organization = None
        if args.role == Role.RECRUITER:
            if not args.company:
                parser.error("--company is required for a recruiter")
            organization = db.scalar(select(OrganizationRecord).where(OrganizationRecord.name == args.company))
            if organization is None:
                organization = OrganizationRecord(name=args.company, status=OrganizationStatus.ACTIVE)
                db.add(organization)
                db.flush()
        try:
            create_user(
                db,
                email=args.email,
                password=password,
                full_name=args.name,
                role=Role(args.role),
                organization=organization,
            )
        except AccountError as exc:
            parser.exit(1, f"error: {exc}\n")
        db.commit()
    print(f"created {args.role} {args.email}")
    if not args.password:
        print(f"password (shown once): {password}")


if __name__ == "__main__":
    main()
