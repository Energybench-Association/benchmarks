# Contributing

Thank you for helping to build EnergyBench's benchmarks! This guide is for everyone who submits,
reviews or maintains them. The [README](README.md) explains what a benchmark is and how one gets
published.

## Submitting a benchmark

Benchmarks can be created directly through the [EnergyBench Explorer](https://energybench.org/browse). You can select individual data items, use spatial or other search filters, and submit your selection through the website. The website then creates the benchmark files and opens a pull request on your behalf.

You can also create or modify a benchmark manually by opening a pull request that adds or updates a folder under `benchmarks/<slug>/`. Each folder must follow the [file format](#file-format) described below. We recommend using the Explorer to generate an initial benchmark definition rather than writing the files from scratch.

Before submitting your changes, run the validation script locally.

```bash
uv run scripts/validate.py
```

See [Development setup](#development-setup) for instructions on installing the required tools.

To withdraw a published benchmark, open a pull request that removes its folder from the repository.

## File format

Each benchmark is stored in a separate folder under `benchmarks/<slug>/` and consists of two files, `collection.json` and `search.json`.

Both files must use UTF-8 encoding, two-space indentation, and a final newline. Please preserve this formatting when editing existing files to keep pull request diffs consistent and easy to review.

### `collection.json`

The benchmark definition follows the [STAC 1.0.0](https://stacspec.org) Collection specification and uses the [Themes extension](https://github.com/stac-extensions/themes).

The Collection contains the benchmark metadata and links to the exact versions of the selected data items.

| Field | Requirements |
|---|---|
| `id` | Must be `benchmark-<slug>`, where `<slug>` matches the folder name. The slug must contain lowercase words separated by hyphens and cannot exceed 60 characters. |
| `title` | A descriptive title between 5 and 120 characters. |
| `description` | Between 20 and 4000 characters explaining the purpose of the benchmark and how the data was selected. |
| `themes` | Must identify the Collection as belonging to the `benchmark` domain using the EnergyBench domain scheme. |
| `license` | Uses the license of the source release Collections when they share one. Otherwise, it must be `various`. |
| `providers` | Identifies the contributor as the `producer`, including a profile URL, and the EnergyBench Association as the `host`. |
| `extent` | Defines the spatial and temporal extent of the selected data. |
| `summaries` | Contains distinct metadata values from the selected Items. For energy data, these include `energy:fuel_type`, `energy:entity_type`, `energy:status`, and `energy:measurement_type` where applicable. |
| `keywords` | Includes `benchmark` and relevant keywords describing the selected data. |
| `created` | Records the time at which the benchmark was submitted. |

The `themes` field must include the following entry.

```json
{
  "themes": [
    {
      "scheme": "https://energybench.org/domains",
      "concepts": [
        {
          "id": "benchmark"
        }
      ]
    }
  ]
}
```

The Collection must also contain the following links.

- A `root` link to the EnergyBench STAC API at `https://energybench.org/api/`.
- A `via` link to `./search.json`, with the title `How this selection was made`.
- A `license` link for the applicable terms of use of each source release.
- An `item` link for every selected data item, referencing an existing Item in a published release of the EnergyBench catalog.

For example, an Item link may reference

```text
https://energybench.org/api/collections/cen__v0.1.1/items/cen-1899
```

Release Collections follow the naming convention `<dataset>__<release>`. By referencing a specific release, the benchmark preserves the exact version of the data used when it was created.

Each Item may appear only once in a benchmark and must reference a single release. A benchmark must contain at least one Item and may contain no more than 20,000.

### `search.json`

The `search.json` file records how the benchmark selection was constructed. It contains the original STAC API searches, any manual changes to their results, and the time at which the selection was resolved.

An example is shown below.

```json
{
  "searches": [
    {
      "collections": ["cen__v0.1.1"],
      "filter-lang": "cql2-json",
      "filter": {}
    }
  ],
  "added": ["cen__v0.1.1/cen-1948"],
  "removed": ["cen__v0.1.1/cen-1793"],
  "resolved": "2026-11-01T11:37:23Z"
}
```

The file contains four fields.

- `searches` contains the STAC API search request bodies used to construct the initial selection.
- `added` lists Items that were manually included in addition to the search results.
- `removed` lists Items that were manually excluded from the search results.
- `resolved` records when the searches were executed, using a UTC timestamp.

Items in `added` and `removed` use the format `<release>/<item-id>`, where the release identifies the source Collection.

A benchmark does not need to originate from a search. For manually constructed selections, `searches` may be empty, with all selected Items listed in `added`.

The final selection is stored in `collection.json` as links to specific released Items. This ensures that the benchmark remains reproducible even if the results of the original searches change.

## Reviewing a benchmark

Every pull request requires approval from a maintainer, as defined in [CODEOWNERS](.github/CODEOWNERS), and must pass the automated **Validate** check.

Validation checks the structure and metadata of the benchmark files, verifies the required fields and constraints, and confirms that all referenced Items exist in the public EnergyBench catalog.

Maintainers also review the scientific and practical suitability of each submission. The following criteria are used during review.

- [ ] **Purpose.** The title and description clearly explain the intended use of the benchmark and provide enough information for other researchers to understand its scope.
- [ ] **Data selection.** The selected data is appropriate for the stated purpose. The selection process is documented in `search.json`, and substantial manual additions or removals should be explained.
- [ ] **Existing benchmarks.** The submission does not duplicate an existing benchmark with the same purpose and data selection. Changes to an existing benchmark should normally be submitted as updates to its folder.
- [ ] **Content.** The title and description are appropriate for a public research repository. They must not contain unrelated links or personal information beyond the contributor's own attribution.
- [ ] **Attribution.** The `producer` entry in `providers` correctly identifies the person responsible for creating the benchmark.
- [ ] **Data versions.** All Items reference the intended data releases. Newer releases should not be substituted automatically, since this would change the benchmark's underlying data.

Reviewers can request changes through the pull request discussion. Maintainers may also make minor corrections directly to the submission branch, such as improving a description or correcting metadata. Automated validation runs again after any changes.

Once the pull request is approved and all checks pass, it can be squash-merged into `main`. EnergyBench periodically synchronizes the repository with the public catalog, so merged benchmarks are normally published within a few minutes.

Changes outside `benchmarks/`, including modifications to validation scripts, tests, or GitHub Actions workflows, must be reviewed as code changes. Such changes may affect how all future benchmark submissions are validated.

## Development setup

Development requires Git and [uv](https://docs.astral.sh/uv/getting-started/installation/).

You should [fork the repository](https://github.com/Energybench-Association/benchmarks/fork) and submit pull requests against `main`.

The project uses uv to manage Python versions, dependencies, and development tools. Install the environment and Git hooks with the following commands.

```bash
uv sync
uv run prek install
```

The first command creates the `.venv` environment and installs the dependencies defined in `uv.lock`. The second installs the pre-commit and commit-message hooks.

The project uses [prek](https://prek.j178.dev) to run the hooks configured in `.pre-commit-config.yaml`. The configuration is also compatible with the standard `pre-commit` tool.

The main development commands are listed below.

| Task | Command |
|---|---|
| Validate all benchmarks | `uv run scripts/validate.py` |
| Validate against a different STAC API | `uv run scripts/validate.py --api http://localhost/api` |
| Run tests | `uv run pytest` |
| Run strict type checking | `uv run pyrefly check` |
| Lint and format the code | `uv run ruff check --fix && uv run ruff format` |
| Run all Git hooks | `uv run prek run --all-files` |

If you change dependencies in `pyproject.toml`, you must also commit the updated `uv.lock`. The `uv-lock` hook checks that both files are consistent.

## Code conventions

- **Python version and formatting.** Python 3.12 or newer is required. Code is formatted using `ruff format`, following Black-style conventions with a maximum line length of 88 characters.
- **Type annotations.** All functions must have complete type annotations. Use modern Python syntax such as `list[str]` and `str | None`. Pyrefly performs strict type checking, while Ruff enforces annotation requirements.
- **Docstrings.** Every function, method, and class must have a [Google-style docstring](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings), including test code. Arguments must be documented with their types in brackets, together with `Returns` and `Raises` sections.
- **Language.** Comments and docstrings must use American English. Spelling is checked automatically.
- **Imports and logging.** Use absolute imports throughout the project. If logging is required, use [loguru](https://loguru.readthedocs.io).
- **Testing.** Tests should mock interactions with the STAC API so they can run offline. The only exception is a test that retrieves the STAC JSON schemas. All warnings are treated as errors during testing.

## Commit messages and pull requests

Changes to the repository's code, configuration, or documentation must use [Conventional Commits](https://www.conventionalcommits.org) for commit messages and pull request titles.

Examples include

```text
fix: accept empty searches
docs: explain search.json
```

Branch names should begin with a corresponding change type, such as `feat/`, `fix/`, `docs/`, `ci/`, or `chore/`.

Pull requests are squash-merged, and the pull request title becomes the commit message on `main`. Individual commits are also checked by the `commit-msg` hook.

These naming requirements apply to changes outside `benchmarks/`. Automatically generated benchmark submissions do not need to follow the same naming conventions.

Every pull request must pass the **Validate** and **ci-ok** checks before merging. The `ci-ok` check covers the configured hooks, strict type checking, and automated tests.

## Dependency updates

Dependabot checks for updates to Python dependencies, GitHub Actions, and prek hooks every week. Related updates are grouped into pull requests to simplify review.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Please report unacceptable behavior to renewbench@lists.kit.edu.
