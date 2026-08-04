"""Command-line entry point: run the server, or manage the stored API key.

Running with no subcommand starts the MCP server, so an MCP client only ever
needs the bare command. The subcommands are for a human at a terminal.
"""

import argparse
import getpass
import os
import sys
from collections.abc import Sequence

from lse_data_mcp import credentials
from lse_data_mcp.server import main as run_server

_PROMPT = "London Strategic Edge API key (input is hidden): "


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lse-data-mcp",
        description=(
            "Unofficial read-only MCP server for London Strategic Edge market data. "
            "Run without a subcommand to serve an MCP client over standard input/output."
        ),
    )
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser(
        "login",
        help="Prompt for an API key and store it in this system's credential store.",
    )
    subcommands.add_parser(
        "logout",
        help="Remove the API key held in this system's credential store.",
    )
    subcommands.add_parser(
        "status",
        help="Report where the server would read its API key from, without printing it.",
    )
    return parser


def _prompt_for_api_key() -> str:
    """Read the key from the terminal without echoing it."""
    return getpass.getpass(_PROMPT).strip()


def _login() -> int:
    # Never accept the key as an argument: argv reaches shell history and `ps`.
    api_key = _prompt_for_api_key()
    if not api_key:
        print("No key entered. Nothing was stored.", file=sys.stderr)
        return 1

    try:
        backend = credentials.store_api_key(api_key)
    except credentials.CredentialStoreError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Stored the API key in {backend}.")
    if os.getenv("LSE_API_KEY", "").strip():
        print(
            "Note: LSE_API_KEY is set in this environment and takes precedence over "
            "the stored key.",
        )
    return 0


def _logout() -> int:
    try:
        removed = credentials.delete_stored_api_key()
    except credentials.CredentialStoreError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not removed:
        print("No stored API key was found; nothing to remove.")
        return 0
    print("Removed the stored API key.")
    return 0


_STORED_KEY_REPORT = {
    credentials.CredentialStatus.STORED: "yes",
    credentials.CredentialStatus.ABSENT: "no",
    credentials.CredentialStatus.NO_STORE: "unknown - there is no credential store to ask",
    credentials.CredentialStatus.INACCESSIBLE: (
        "unknown - this process cannot reach the credential store"
    ),
}


def _status() -> int:
    from_environment = bool(os.getenv("LSE_API_KEY", "").strip())
    credential = credentials.read_credential()
    stored = credential.api_key is not None

    if from_environment:
        source = "the LSE_API_KEY environment variable"
    elif stored:
        source = "this system's credential store"
    else:
        source = "nowhere - no API key is available"

    print(f"API key source: {source}")
    print(f"Credential store: {credentials.describe_backend()}")
    print(f"Key stored there: {_STORED_KEY_REPORT[credential.status]}")
    print(f"LSE_API_KEY set: {'yes' if from_environment else 'no'}")

    unavailable = credentials.describe_unavailable(credential.status)
    if unavailable and not from_environment:
        print(f"\n{unavailable}")
        print("Set LSE_API_KEY in this process's environment to supply the key directly.")
    return 0 if from_environment or stored else 1


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch a subcommand, or run the MCP server when none is given."""
    args = _build_parser().parse_args(argv)

    if args.command == "login":
        return _login()
    if args.command == "logout":
        return _logout()
    if args.command == "status":
        return _status()

    run_server()
    return 0
