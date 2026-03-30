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
import subprocess
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


def jira_to_markdown(text: str) -> str:
    """Convert Jira wiki markup to markdown via pandoc. Falls back to plain text."""
    try:
        result = subprocess.run(
            ["pandoc", "-f", "jira", "-t", "markdown", "--wrap=none"],
            input=text,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return text


def format_issue_markdown(data: dict) -> str:
    """Format an issue dict as markdown."""
    if not data:
        return "(no data)"

    key = data.get("key", "?")
    fields = data.get("fields", {})

    lines = []
    summary = fields.get("summary", "(no summary)")
    lines.append(f"# [{key}] {summary}")
    lines.append(f"\n<{JIRA_BASE}/browse/{key}>")

    lines.append("\n## Metadata\n")
    lines.append(f"| Field | Value |")
    lines.append(f"|---|---|")

    status = fields.get("status", {}).get("name", "?")
    lines.append(f"| Status | {status} |")

    priority = fields.get("priority", {}).get("name", "?")
    lines.append(f"| Priority | {priority} |")

    issue_type = fields.get("issuetype", {}).get("name", "?")
    lines.append(f"| Type | {issue_type} |")

    assignee = (fields.get("assignee") or {}).get("displayName", "Unassigned")
    lines.append(f"| Assignee | {assignee} |")

    reporter = (fields.get("reporter") or {}).get("displayName", "?")
    lines.append(f"| Reporter | {reporter} |")

    resolution = (fields.get("resolution") or {}).get("name", "Unresolved")
    lines.append(f"| Resolution | {resolution} |")

    components = [c["name"] for c in fields.get("components", [])]
    if components:
        lines.append(f"| Components | {', '.join(components)} |")

    fix_versions = [v["name"] for v in fields.get("fixVersions", [])]
    if fix_versions:
        lines.append(f"| Fix Version | {', '.join(fix_versions)} |")

    target_versions = [v["name"] for v in fields.get("customfield_210441", []) or []]
    if target_versions:
        lines.append(f"| Target Version | {', '.join(target_versions)} |")

    created = (fields.get("created") or "")[:10]
    updated = (fields.get("updated") or "")[:10]
    lines.append(f"| Created | {created} |")
    lines.append(f"| Updated | {updated} |")

    # Description
    desc = fields.get("description") or ""
    if desc:
        lines.append("\n## Description\n")
        lines.append(jira_to_markdown(desc))

    # Comments
    comments = fields.get("comment", {}).get("comments", [])
    if comments:
        lines.append(f"\n## Comments ({len(comments)} total)\n")
        for c in comments:
            author = (c.get("author") or {}).get("displayName", "?")
            date = (c.get("created") or "")[:10]
            body = jira_to_markdown(c.get("body") or "")
            lines.append(f"### {author} — {date}\n")
            lines.append(body)
            lines.append("")

    # Related issues
    related = extract_related_keys(data)
    if related:
        lines.append("\n## Related Issues\n")
        for rel, rkey in related:
            rlink = f"{JIRA_BASE}/browse/{rkey}"
            lines.append(f"- **{rel}**: [{rkey}]({rlink})")

    return "\n".join(lines)


def issue_path(key: str, out_dir: Path, raw_json: bool) -> Path:
    ext = ".json" if raw_json else ".md"
    return out_dir / f"{key}{ext}"


def save_issue(data: dict, out_dir: Path, raw_json: bool = False) -> Path:
    """Write a single issue to out_dir/{KEY}.md (or .json). Returns the path."""
    key = data.get("key", "UNKNOWN")
    path = issue_path(key, out_dir, raw_json)
    content = (
        json.dumps(data, indent=2, ensure_ascii=False)
        if raw_json
        else format_issue_markdown(data)
    )
    path.write_text(content, encoding="utf-8")
    return path


def fetch_recursive(
    key: str,
    max_depth: int,
    visited: set[str],
    out_dir: Path,
    raw_json: bool = False,
    force: bool = False,
    current_depth: int = 0,
) -> None:
    if key in visited or current_depth > max_depth:
        return
    visited.add(key)

    path = issue_path(key, out_dir, raw_json)
    already_exists = path.exists()

    if not force and already_exists:
        print(f"Skipping {key} (already exists: {path})", file=sys.stderr)
        # Still need related keys to recurse — fetch without writing
        if current_depth < max_depth:
            data = fetch_issue(key)
            if data:
                related = extract_related_keys(data)
                for _rel, rkey in related:
                    fetch_recursive(rkey, max_depth, visited, out_dir, raw_json, force, current_depth + 1)
        return

    print(f"Fetching {key} (depth {current_depth})...", file=sys.stderr)
    data = fetch_issue(key)
    if not data:
        return

    save_issue(data, out_dir, raw_json=raw_json)
    print(f"  Saved -> {path}", file=sys.stderr)

    if current_depth < max_depth:
        related = extract_related_keys(data)
        for _rel, rkey in related:
            fetch_recursive(rkey, max_depth, visited, out_dir, raw_json, force, current_depth + 1)


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
        help="Save raw JSON instead of markdown",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download and overwrite already-saved issues",
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
    fetch_recursive(key, max_depth, visited, out_dir, raw_json=args.raw_json, force=args.force)
    print(f"\nDone. {len(visited)} issue(s) in {out_dir}/: {', '.join(sorted(visited))}")


if __name__ == "__main__":
    main()
