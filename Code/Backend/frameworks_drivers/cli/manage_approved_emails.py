"""Manage the email-OTP allowlist, from the command line.

Run from ``Code/Backend``::

    python -m frameworks_drivers.cli.manage_approved_emails add reader@example.com
    python -m frameworks_drivers.cli.manage_approved_emails remove reader@example.com
    python -m frameworks_drivers.cli.manage_approved_emails list

The allowlist is a database table (``approved_emails``), not a config file
(Ranjit, 2026-10-08 — see ``Documents/notes/Decisions-and-Questions.md``).
This is the only tool that writes to it until there is a reason for more —
an admin screen, a bulk-import path — and "Ranjit or Shloka run a command"
is a deliberately low bar for a POC-stage, single-client allowlist.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from frameworks_drivers.container import build_container, dispose_container
from infrastructure.config.settings import get_settings

EXIT_OK = 0
EXIT_NOT_FOUND = 1


def _out(line: str) -> None:
    sys.stdout.write(f"{line}\n")
    sys.stdout.flush()


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    container = build_container(settings)
    try:
        if args.command == "add":
            await container.approved_emails.add(args.email, at=container.clock.now())
            _out(f"Approved: {args.email}")
            return EXIT_OK

        if args.command == "remove":
            removed = await container.approved_emails.remove(args.email)
            if removed:
                _out(f"Removed: {args.email}")
                return EXIT_OK
            _out(f"Not on the list: {args.email}")
            return EXIT_NOT_FOUND

        emails = await container.approved_emails.list_all()
        if not emails:
            _out("No approved addresses yet.")
        else:
            for email in emails:
                _out(email)
        return EXIT_OK
    finally:
        await dispose_container(container)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add", help="Approve an address.")
    add.add_argument("email")

    remove = commands.add_parser("remove", help="Revoke an address.")
    remove.add_argument("email")

    commands.add_parser("list", help="List every approved address.")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_run(_parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
