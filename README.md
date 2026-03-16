# cubrid-jira-fetcher

Fetch CUBRID JIRA issues and their related issues, saving each as a markdown file.

Uses the JIRA REST API over plain HTTP — bypassing the redirect loop that occurs when tools force-upgrade to HTTPS.

![Demo](./demo.gif)

## Requirements

- Python 3.14+
- [pandoc](https://pandoc.org/) (for Jira wiki → markdown conversion)
- [uv](https://github.com/astral-sh/uv) (optional, for `just` recipes)
- [just](https://github.com/casey/just) (optional)

Install pandoc:
```sh
brew install pandoc   # macOS / Linuxbrew
# or
sudo apt install pandoc
```

## Usage

### Direct

```sh
python fetcher.py CBRD-26463
python fetcher.py http://jira.cubrid.org/browse/CBRD-26463
```

### With just

```sh
just fetch CBRD-26463            # fetch issue + 1 level of related issues
just fetch-single CBRD-26463     # fetch only the given issue
just fetch-deep CBRD-26463 3     # fetch 3 levels deep
just force CBRD-26463            # re-download and overwrite existing files
just json CBRD-26463             # save raw JSON instead of markdown
```

Override the output directory:
```sh
just dir=my_issues fetch CBRD-26463
```

## Options

| Flag | Default | Description |
|---|---|---|
| `-d`, `--output-dir` | `related_issues/` | Directory to save files into |
| `--depth N` | `1` | Levels of related issues to follow |
| `--no-recurse` | — | Only fetch the given issue (same as `--depth 0`) |
| `--force` | — | Re-download and overwrite already-saved files |
| `--json` | — | Save raw JSON instead of markdown |

## Output

Each issue is saved as `{output-dir}/{KEY}.md` (or `.json` with `--json`).

```
related_issues/
├── CBRD-26463.md   ← the issue you requested
├── CBRD-26584.md   ← parent
├── CBRD-26433.md   ← related
└── CBRD-26521.md   ← related
```

Each markdown file contains:

- Title and link
- Metadata table (status, priority, type, assignee, reporter, resolution, components, versions, dates)
- Description (converted from Jira wiki markup via pandoc)
- Comments (converted from Jira wiki markup via pandoc)
- Related issues with links

## Caching

Already-saved files are skipped on subsequent runs. Related issues are still traversed so that deeper runs (`--depth 2` after a `--depth 1` run) work correctly. Use `--force` to re-download everything.
