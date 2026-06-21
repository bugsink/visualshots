# Visualshots

Visualshots is a local-first screenshot artifact generator for Bugsink UI review.

It captures a named scenario twice:

* `before`: the merge-base of `origin/main` and the branch tip;
* `after`: the branch tip.

The output is a small review bundle in `results/<scenario>/` containing screenshots, metadata, and an HTML page.
Each captured ref is written in light and dark mode:

* `before.png`
* `before-dark.png`
* `after.png`
* `after-dark.png`

## Usage

```bash
python visualshots.py list
python visualshots.py run --repo /path/to/bugsink --scenario projects --after HEAD
python visualshots.py run --repo /path/to/bugsink --scenario issue-stacktrace,issue-details --after HEAD
```

The tool creates temporary git worktrees and isolated SQLite databases. It does not modify the current checkout.
Scenarios that use sample events read `SAMPLES_DIR`, defaulting to an `event-samples` checkout next to the Bugsink
worktree.
Scenario setup runs Bugsink with strict event validation, so ingested samples must be schema-valid.

Use the Playwright Python image when running this in Docker:

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.60.0-noble
```

Install Python dependencies before running captures:

```bash
pip install playwright
```

The Playwright image already contains browser system dependencies and browsers. If you are not using that image, install
Firefox and its dependencies with:

```bash
python -m playwright install --with-deps firefox
```

Firefox is the default browser. Use `--browser chromium` or `--browser webkit` to override it.

Scenarios live in `scenarios/`. They are written as small Python modules with `setup()` and `capture(page, context)`
functions.
