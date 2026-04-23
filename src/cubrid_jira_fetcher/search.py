#!/usr/bin/env python3
"""
cubrid-jira-search: Search local cache for a JIRA issue, fetch if missing.

Usage:
    cubrid-jira-search CBRD-12345
    cubrid-jira-search CBRD-12345 --dir /path/to/cache
    CUBRID_JIRA_DIR=/my/dir cubrid-jira-search CBRD-12345

Cache directory resolution (first match wins):
    1. --dir flag
    2. $CUBRID_JIRA_DIR env var
    3. ~/.local/share/cubrid-jira/issues/
"""

import sys
import os
import argparse
from pathlib import Path

from cubrid_jira_fetcher.fetcher import parse_issue_key, fetch_recursive

DEFAULT_DIR = Path.home() / ".local" / "share" / "cubrid-jira" / "issues"


def resolve_dir(cli_dir: str | None) -> Path:
    if cli_dir:
        return Path(cli_dir)
    env = os.environ.get("CUBRID_JIRA_DIR")
    if env:
        return Path(env)
    return DEFAULT_DIR


def find_cached(key: str, directory: Path) -> list[Path]:
    """Find cached markdown files matching the issue key."""
    if not directory.exists():
        return []
    return sorted(directory.glob(f"{key}*.md"))


def main():
    parser = argparse.ArgumentParser(
        description="Search local cache for a CUBRID JIRA issue; fetch from web if missing."
    )
    parser.add_argument("issue", help="Issue key (e.g. CBRD-12345) or full browse URL")
    parser.add_argument(
        "-d", "--dir", default=None, metavar="DIR",
        help=f"Cache directory (default: $CUBRID_JIRA_DIR or {DEFAULT_DIR})",
    )
    parser.add_argument(
        "--no-recurse", action="store_true",
        help="When fetching, only fetch the given issue (no related issues)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-fetch even if cached",
    )
    args = parser.parse_args()

    try:
        key = parse_issue_key(args.issue)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    out_dir = resolve_dir(args.dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Check cache first (unless --force)
    if not args.force:
        cached = find_cached(key, out_dir)
        if cached:
            print(f"# Found cached: {cached[0].name}", file=sys.stderr)
            print(cached[0].read_text(encoding="utf-8"))
            return

    # Fetch from web
    print(f"# Fetching {key} from jira.cubrid.org ...", file=sys.stderr)
    max_depth = 0 if args.no_recurse else 1
    visited: set[str] = set()
    fetch_recursive(key, max_depth, visited, out_dir)

    # Output the fetched file
    cached = find_cached(key, out_dir)
    if cached:
        print(cached[0].read_text(encoding="utf-8"))
    else:
        print(f"Error: Failed to fetch {key}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
