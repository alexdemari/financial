#!/usr/bin/env python3
"""
Stop hook — prints a brief session summary when Claude finishes.
Helps track what changed before committing.
"""

import subprocess
from datetime import datetime


def get_modified_files():
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True
        )
        staged = subprocess.run(
            ["git", "diff", "--name-only", "--cached"], capture_output=True, text=True
        )
        files = set(
            result.stdout.strip().splitlines() + staged.stdout.strip().splitlines()
        )
        return sorted(files)
    except Exception:
        return []


def get_test_status():
    try:
        result = subprocess.run(
            ["uv", "run", "pytest", "--tb=no", "-q", "--no-header"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        last_line = (
            result.stdout.strip().splitlines()[-1]
            if result.stdout.strip()
            else "unknown"
        )
        return last_line
    except Exception:
        return "could not run tests"


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    modified = get_modified_files()

    print("\n" + "=" * 50)
    print(f"SESSION SUMMARY — {now}")
    print("=" * 50)

    if modified:
        print(f"\nModified files ({len(modified)}):")
        for f in modified:
            print(f"  {f}")
    else:
        print("\nNo modified files detected.")

    print(f"\nTests: {get_test_status()}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
