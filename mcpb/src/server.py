"""Entry point for the Claude Desktop bundle.

This file carries no server logic. It exists only because the bundle declares an
`entry_point`, and it calls into `lse-data-mcp` as resolved from PyPI by the pin
in `../pyproject.toml`. Keeping the implementation out of the bundle is what
guarantees a bundle user runs exactly the code published under that version.
"""

from lse_data_mcp.cli import main

if __name__ == "__main__":
    # An explicit empty argument list, rather than letting the parser read
    # sys.argv: the bundle has exactly one job, which is to run the server. A
    # bundle user supplies the key through the host's own configuration screen
    # and should never reach the `login` or `logout` subcommands.
    raise SystemExit(main([]))
