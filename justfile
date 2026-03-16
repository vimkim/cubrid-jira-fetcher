# cubrid-jira-fetcher justfile

# Default: show available recipes
default:
    @just --list

# Output directory (override with: just dir=my_dir fetch CBRD-26463)
dir := "related_issues"

# Fetch an issue with 1 level of related issues (default)
# Usage: just fetch CBRD-26463
fetch issue:
    uv run fetcher.py {{issue}} -d {{dir}}

# Fetch an issue without following related issues
# Usage: just fetch-single CBRD-26463
fetch-single issue:
    uv run fetcher.py {{issue}} -d {{dir}} --no-recurse

# Fetch an issue with custom recursion depth
# Usage: just fetch-deep CBRD-26463 3
fetch-deep issue depth="5":
    uv run fetcher.py {{issue}} -d {{dir}} --depth {{depth}}

# Dump raw JSON for an issue
# Usage: just json CBRD-26463
json issue:
    uv run fetcher.py {{issue}} -d {{dir}} --json

# Install the package (makes `jira-fetch` available in the venv)
install:
    uv sync
