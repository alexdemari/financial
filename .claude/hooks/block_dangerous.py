#!/usr/bin/env python3
"""
PreToolUse hook — blocks dangerous bash commands before Claude executes them.

Exit codes:
  0 = allowed
  2 = blocked (message sent back to Claude as feedback)
"""

import json
import sys

BLOCKLIST = [
    "rm -rf",
    "git push --force",
    "git push -f",
    "DROP TABLE",
    "DROP DATABASE",
    "truncate",
    "> /dev/",
    "chmod 777",
    "curl | bash",
    "wget | bash",
    "curl | sh",
]


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")

    for pattern in BLOCKLIST:
        if pattern.lower() in command.lower():
            print(
                f"[block_dangerous] Blocked: command contains '{pattern}'. "
                f"Review and run manually if intentional.",
                file=sys.stderr,
            )
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
