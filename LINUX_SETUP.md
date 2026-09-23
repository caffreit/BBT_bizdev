# Linux setup

The repository contains a Python data-processing pipeline, a small local frontend, and Node-based Excel workbook builders.

## Requirements

- Python 3.12 or newer
- Node.js 22 or newer
- A Linux build of the private `@oai/artifact-tool` package. Codex Desktop supplies this in its bundled workspace runtime.

Do not reuse a `node_modules` directory copied from Windows. Some dependencies contain native binaries and must be installed on the target operating system. `@oai/artifact-tool` is private and is not available from the public npm registry; the optional dependency in `package.json` records the expected version but cannot bootstrap a standalone installation from npmjs.org.

## Install

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt
```

In Codex Desktop, locate the bundled workspace dependencies and make the repository's `node_modules` a symbolic link to its Linux Node package directory. Preserve any copied Windows directory under a different name until it is no longer needed.

If `python3 -m venv` reports that `ensurepip` is unavailable on Debian or Ubuntu, install the distribution's `python3-venv` package first.

## Verify

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q
npm run check
```

Start the local lead-triage frontend with:

```bash
.venv/bin/python frontend/server.py
```

It listens on the first available address from `http://127.0.0.1:8000/` through port 8009.

## Main entry points

- `build_bbt_bizdev_workbook.py`: run the primary discovery and workbook pipeline.
- `subscriber_enrichment.py`: enrich subscriber data; supports `--help` for its modes.
- `campaign_matcher.py`: create campaign profiles, match contacts, and export approved contacts.
- `frontend/server.py`: serve the local lead-triage frontend and company-research API.
- `build_subscriber_enrichment_workbook.mjs`: build the subscriber review workbook.
- `campaign_workbook.mjs`: build or extract a campaign review workbook.
- `scripts/build_canada_wp6_workbook.mjs`: reproduce the Canada WP6 baseline workbook.

Additional `collect_canada_*.py`, `enrich_canada_*.py`, `verify_canada_*.py`, and `score_canada_*.py` files are task-specific command-line entry points.

## Optional configuration

Network-backed enrichment paths may require one or more of:

- `OPENROUTER_API_KEY` or `BBT_OPENROUTER_API_KEY`
- `BBT_LEAD_ENRICHMENT_API_KEY`
- `BRAVE_SEARCH_API_KEY` or `BBT_BRAVE_SEARCH_API_KEY`
- `HUNTER_API_KEY` or `BBT_HUNTER_API_KEY`

The unit tests and local frontend static-file smoke test do not require these credentials. Some collection and research commands also depend on public external services being reachable.

## Line endings

`.gitattributes` defines LF endings for source and text files. Existing files have intentionally not been normalized because the working tree contained valuable changes when Linux setup was added. Normalize line endings only in a separately reviewed change after those changes are safely committed or otherwise backed up.
