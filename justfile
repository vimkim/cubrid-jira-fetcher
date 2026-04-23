# cubrid-jira-fetcher justfile

# Default: show available recipes
default:
    @just --list

# Output directory (override with: just dir=my_dir fetch CBRD-26463)
dir := "related_issues"

# Fetch an issue with 1 level of related issues (default)
# Usage: just fetch CBRD-26463
fetch issue:
    uv run cubrid-jira-fetch {{issue}} -d {{dir}}

# Fetch an issue without following related issues
# Usage: just fetch-single CBRD-26463
fetch-single issue:
    uv run cubrid-jira-fetch {{issue}} -d {{dir}} --no-recurse

# Fetch an issue with custom recursion depth
# Usage: just fetch-deep CBRD-26463 999999
fetch-deep issue depth="3":
    uv run cubrid-jira-fetch {{issue}} -d {{dir}} --depth {{depth}}

# Force re-download (overwrite existing files)
# Usage: just force CBRD-26463
force issue:
    uv run cubrid-jira-fetch {{issue}} -d {{dir}} --force

# Dump raw JSON for an issue
# Usage: just json CBRD-26463
json issue:
    uv run cubrid-jira-fetch {{issue}} -d {{dir}} --json

# Cache-first lookup for a single issue (prints markdown to stdout)
# Usage: just search CBRD-26463
search issue:
    uv run cubrid-jira-search {{issue}}

# Install the package (makes `cubrid-jira-fetch` and `cubrid-jira-search` available)
install:
    uv sync
