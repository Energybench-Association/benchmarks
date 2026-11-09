# EnergyBench Benchmarks

This repository contains community benchmarks for [EnergyBench](https://www.energybench.org). Each benchmark defines a subset of EnergyBench data and references specific data versions to ensure that results can be reproduced.

Benchmarks can include energy data, weather data, or any combination of the two, depending on their intended purpose.

The repository contains the benchmark definitions and the validation checks used before publication. Published benchmarks are available at [energybench.org/benchmarks](https://www.energybench.org/benchmarks).

## What is a benchmark?

A benchmark is a selection of EnergyBench data created for a particular research or evaluation task. For example, a benchmark might contain wind power generation data from Chile, weather data for a particular region, or a combination of both.

Each benchmark has a title, a description of its purpose, and a fixed selection of data linked to specific releases.

Each benchmark is stored in its own folder under `benchmarks/<slug>/` and contains two files.

- `collection.json` defines the benchmark as a [STAC](https://stacspec.org) Collection. It has the ID `benchmark-<slug>` and belongs to the `benchmark` domain. Each selected plant is linked to an existing Item in the public EnergyBench catalog. These links include the exact data release, such as `cen-pt1h__v0.1.0`, so the benchmark always references the same data version.
- `search.json` records how the plants were selected. This includes the searches used to find plants and any plants that were manually added or removed. The file is referenced from the Collection using a `via` link.

The file formats are described in more detail in [CONTRIBUTING.md](CONTRIBUTING.md#file-format).

## Submitting a benchmark

The easiest way to create a benchmark is through the EnergyBench website.

1. Open the [Explorer](https://www.energybench.org/browse) and select the plants you want to include. You can select individual plants, choose a region on the map, or include all plants matching a search.
2. Give your benchmark a title and describe its purpose. You can then submit it using your GitHub or ORCID account so that your contribution is credited.
3. EnergyBench automatically creates a pull request in this repository with the benchmark definition and identifies you as its producer.

You can also submit a benchmark manually by creating a folder in the required format and opening a pull request. Instructions are available in [CONTRIBUTING.md](CONTRIBUTING.md).

Changes to existing benchmarks, new versions, and withdrawals are also handled through pull requests. If you find a problem with a published benchmark, you can report it by opening an issue.

## Review and validation

All benchmark submissions are reviewed publicly by the maintainers. The review considers whether the benchmark has a clear purpose, whether the selected plants are appropriate for that purpose, and whether a similar benchmark already exists. Anyone can participate in the discussion.

Every pull request also runs an automated **Validate** check to ensure that the benchmark follows the required format.

The validation checks that

- The folder name contains only lowercase words separated by hyphens and is no longer than 60 characters.
- `collection.json` is a valid STAC Collection that follows the core and Themes schemas. Its ID must be `benchmark-<slug>`, its domain must be `benchmark`, its title must contain between 5 and 120 characters, and its description must contain between 20 and 4000 characters.
- Every selected plant exists in a published release of the EnergyBench catalog. Plants cannot appear more than once, and a benchmark can contain up to 20,000 plants.
- `search.json` records the original searches and any manual changes to the selection. It must also be linked from the Collection using `via`.

You can run the same validation locally using [uv](https://docs.astral.sh/uv/).

```bash
uv run scripts/validate.py
```

## Publishing

Once a pull request has been reviewed and merged, the benchmark is published automatically. EnergyBench checks the repository's `main` branch every few minutes and updates the public catalog with any new or modified benchmarks.

Removing a benchmark folder from the repository also removes the corresponding benchmark from the catalog.

When a benchmark is published, each selected plant is represented as an Item within the benchmark's Collection. The Item contains a `derived_from` link to the original data release and references the same data asset. This preserves the connection to the exact data version used when the benchmark was created.

## Using a benchmark

Published benchmarks are available through the [EnergyBench STAC API](https://www.energybench.org/api) and can be accessed using standard STAC tools such as `pystac-client`.

The following example opens a benchmark and lists its plants and corresponding data assets.

```python
from pystac_client import Client

api = Client.open("https://www.energybench.org/api/")
benchmark = api.get_collection("benchmark-<slug>")
print(benchmark.title, benchmark.description)

for item in api.search(collections=[benchmark.id]).items():
    print(item.id, item.assets["data"].href)
```

The [getting-started guide](https://www.energybench.org/docs/getting-started) explains how to open and work with the underlying data.

## License

The contents of this repository, including all benchmark definitions in `benchmarks/`, are available under the [MIT License](LICENSE).

The underlying energy data is not covered by this license. Each dataset retains the license and terms of use of its original provider. This information is recorded in the corresponding release Collection, linked from the benchmark Collection, and available on the [EnergyBench citation page](https://www.energybench.org/cite).
