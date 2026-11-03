# AGENTS.md

Guidance for AI coding agents working in this repository. `CLAUDE.md` is a symlink to this file.

## What this is

The public, community-curated benchmarks of [EnergyBench](https://energybench.org). Each benchmark
is a STAC Collection in `benchmarks/<slug>/` (`collection.json` plus `search.json`), listing its
plants as `item` links to released Items in the public STAC API (`https://energybench.org/api`).
Most arrive as pull requests opened from the website; maintainers review and squash-merge
them, and EnergyBench publishes `main` every few minutes. The repository holds data and the
validation that guards it; nothing here is released as a package.

## Layout

- `benchmarks/`: one folder per benchmark; the format is in CONTRIBUTING.md, "File format"
- `scripts/validate.py`: the checks the **Validate** workflow runs on every pull request
- `tests/`: pytest suite for `validate.py`, with the STAC API mocked
- `.github/workflows/`: Validate, CI (hooks, type checking, tests) and zizmor

## Commands

```bash
uv sync                        # environment with every dev tool
uv run scripts/validate.py     # validate every benchmark against the public API
uv run pytest                  # tests (warnings are errors)
uv run pyrefly check           # strict type checking
uv run ruff check --fix && uv run ruff format
uv run prek run --all-files    # every hook, as CI runs them
```

## Conventions

- Never add, edit or delete a benchmark unless asked; those are reviewed contributions. Don't
  reformat the JSON the website writes (two-space indent, UTF-8, final newline).
- `validate.py` mirrors the rules EnergyBench applies when it publishes a benchmark. Keep them in
  step with it: change the limits (title, description, slug length, item count) only together.
- This repository is public: no secrets, no private infrastructure details beyond the public site
  and API. Workflows use `pull_request`, never `pull_request_target`, and need no secrets.
- Describe how benchmarks are made and published only in terms of the website
  (energybench.org, its Explorer and Benchmarks pages) and the public STAC API. Never mention
  EnergyBench's other repositories or how the website works behind the scenes.
- Python (details in CONTRIBUTING.md, "Code conventions"):
  - Python >= 3.12; Black style via `ruff format`, line length 88.
  - Lowercase type hints (`list[str]`, `str | None`) on every function. Pyrefly runs in strict
    mode, and ruff runs the rule set in `pyproject.toml`.
  - Google-style docstrings on every function, method and class, tests included. Every argument
    goes in `Args:` with its type in brackets, plus `Returns:`/`Raises:`, and `Attributes:` for
    classes. Optional module docstrings start with the module name in capitals.
  - American English; loguru for logging; absolute imports only.
- Add dependencies with `uv add` (`--group <group>` for dev tools) and keep `uv.lock` in sync.
- Commit messages and the titles of pull requests outside `benchmarks/` are Conventional Commits.
  Branch prefixes are the Conventional Commit types (`feat/`, `fix/`, `docs/`, `chore/`, …).
- Workflows:
  - Pin every action to a full commit SHA with a `# vX.Y.Z` comment.
  - Grant permissions per job, with `permissions: {}` at the top, and set `timeout-minutes`.
  - zizmor and actionlint must pass.
