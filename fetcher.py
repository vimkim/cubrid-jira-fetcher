#!/usr/bin/env python3
"""
cubrid-jira-fetcher: Fetch JIRA issue details and related issues from jira.cubrid.org
Usage:
    python fetcher.py CBRD-26463
    python fetcher.py http://jira.cubrid.org/browse/CBRD-26463
    python fetcher.py CBRD-26463 --depth 2
    python fetcher.py CBRD-26463 --no-recurse
    python fetcher.py CBRD-26463 -d my_issues/
"""

import sys
import re
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

JIRA_BASE = "http://jira.cubrid.org"
REST_API = f"{JIRA_BASE}/rest/api/2/issue"


def parse_issue_key(arg: str) -> str:
    """Extract issue key from a URL or a bare key like CBRD-12345."""
    # e.g. http://jira.cubrid.org/browse/CBRD-26463
    m = re.search(r"([A-Z]+-\d+)", arg)
    if m:
        return m.group(1)
    raise ValueError(f"Cannot parse issue key from: {arg!r}")


def fetch_issue(key: str) -> dict:
    """Fetch raw issue JSON from the REST API."""
    url = f"{REST_API}/{key}?expand=renderedFields"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  [HTTP {e.code}] Failed to fetch {key}: {e.reason}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"  [Error] Failed to fetch {key}: {e}", file=sys.stderr)
        return {}


def extract_related_keys(data: dict) -> list[tuple[str, str]]:
    """Return list of (relationship, key) for all related issues."""
    related = []
    fields = data.get("fields", {})

    # Parent
    parent = fields.get("parent")
    if parent:
        related.append(("parent", parent["key"]))

    # Subtasks
    for sub in fields.get("subtasks", []):
        related.append(("subtask", sub["key"]))

    # Issue links
    for link in fields.get("issuelinks", []):
        link_type = link["type"]["name"]
        if "inwardIssue" in link:
            related.append((f"{link_type} (inward)", link["inwardIssue"]["key"]))
        if "outwardIssue" in link:
            related.append((f"{link_type} (outward)", link["outwardIssue"]["key"]))

    return related


def format_issue(data: dict, indent: int = 0) -> str:
    """Format an issue dict into a readable string."""
    if not data:
        return "(no data)"

    key = data.get("key", "?")
    fields = data.get("fields", {})
    pad = "  " * indent

    lines = []
    lines.append(f"{pad}{'='*60}")
    lines.append(f"{pad}Issue : {key}  —  {JIRA_BASE}/browse/{key}")
    lines.append(f"{pad}{'='*60}")

    summary = fields.get("summary", "(no summary)")
    lines.append(f"{pad}Summary    : {summary}")

    status = fields.get("status", {}).get("name", "?")
    lines.append(f"{pad}Status     : {status}")

    priority = fields.get("priority", {}).get("name", "?")
    lines.append(f"{pad}Priority   : {priority}")

    issue_type = fields.get("issuetype", {}).get("name", "?")
    lines.append(f"{pad}Type       : {issue_type}")

    assignee = fields.get("assignee") or {}
    lines.append(f"{pad}Assignee   : {assignee.get('displayName', 'Unassigned')}")

    reporter = fields.get("reporter") or {}
    lines.append(f"{pad}Reporter   : {reporter.get('displayName', '?')}")

    resolution = fields.get("resolution") or {}
    lines.append(f"{pad}Resolution : {resolution.get('name', 'Unresolved')}")

    components = [c["name"] for c in fields.get("components", [])]
    if components:
        lines.append(f"{pad}Components : {', '.join(components)}")

    fix_versions = [v["name"] for v in fields.get("fixVersions", [])]
    if fix_versions:
        lines.append(f"{pad}Fix Version: {', '.join(fix_versions)}")

    target_versions = [v["name"] for v in fields.get("customfield_210441", []) or []]
    if target_versions:
        lines.append(f"{pad}Target Ver : {', '.join(target_versions)}")

    created = (fields.get("created") or "")[:10]
    updated = (fields.get("updated") or "")[:10]
    lines.append(f"{pad}Created    : {created}  |  Updated: {updated}")

    # Description
    desc = fields.get("description") or ""
    if desc:
        lines.append(f"{pad}Description:")
        for line in desc.splitlines():
            lines.append(f"{pad}  {line}")

    # Comments
    comments = fields.get("comment", {}).get("comments", [])
    if comments:
        lines.append(f"{pad}Comments   : ({len(comments)} total)")
        for c in comments[:5]:  # show up to 5
            author = (c.get("author") or {}).get("displayName", "?")
            date = (c.get("created") or "")[:10]
            body = (c.get("body") or "").replace("\r\n", " ").replace("\n", " ")[:200]
            lines.append(f"{pad}  [{date}] {author}: {body}")
        if len(comments) > 5:
            lines.append(f"{pad}  ... and {len(comments)-5} more comment(s)")

    # Related issues
    related = extract_related_keys(data)
    if related:
        lines.append(f"{pad}Related Issues:")
        for rel, rkey in related:
            rlink = f"{JIRA_BASE}/browse/{rkey}"
            lines.append(f"{pad}  [{rel}] {rkey}  {rlink}")

    return "\n".join(lines)


def save_issue(data: dict, out_dir: Path, raw_json: bool = False) -> Path:
    """Write a single issue to out_dir/{KEY}.txt (or .json). Returns the path."""
    key = data.get("key", "UNKNOWN")
    ext = ".json" if raw_json else ".txt"
    path = out_dir / f"{key}{ext}"
    content = (
        json.dumps(data, indent=2, ensure_ascii=False)
        if raw_json
        else format_issue(data)
    )
    path.write_text(content, encoding="utf-8")
    return path


def fetch_recursive(
    key: str,
    max_depth: int,
    visited: set[str],
    out_dir: Path,
    raw_json: bool = False,
    current_depth: int = 0,
) -> None:
    if key in visited or current_depth > max_depth:
        return
    visited.add(key)

    print(f"Fetching {key} (depth {current_depth})...", file=sys.stderr)
    data = fetch_issue(key)
    if not data:
        return

    path = save_issue(data, out_dir, raw_json=raw_json)
    print(f"  Saved -> {path}", file=sys.stderr)

    if current_depth < max_depth:
        related = extract_related_keys(data)
        for _rel, rkey in related:
            fetch_recursive(rkey, max_depth, visited, out_dir, raw_json, current_depth + 1)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch CUBRID JIRA issue details and related issues."
    )
    parser.add_argument(
        "issue",
        help="Issue key (e.g. CBRD-26463) or full browse URL",
    )
    parser.add_argument(
        "-d", "--output-dir",
        default="related_issues",
        metavar="DIR",
        help="Directory to save issue files (default: related_issues/)",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=1,
        metavar="N",
        help="How many levels of related issues to follow (default: 1, 0 = no recursion)",
    )
    parser.add_argument(
        "--no-recurse",
        action="store_true",
        help="Only fetch the given issue, no related issues (same as --depth 0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="raw_json",
        help="Save raw JSON instead of formatted text",
    )
    args = parser.parse_args()

    try:
        key = parse_issue_key(args.issue)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    max_depth = 0 if args.no_recurse else args.depth

    visited: set[str] = set()
    fetch_recursive(key, max_depth, visited, out_dir, raw_json=args.raw_json)
    print(f"\nDone. {len(visited)} issue(s) saved to {out_dir}/: {', '.join(sorted(visited))}")


if __name__ == "__main__":
    main()
