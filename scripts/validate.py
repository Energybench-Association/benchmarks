"""VALIDATE.

Check every benchmark in this repository before it is merged and published.

For each `benchmarks/<slug>/`:
- the folder name is lowercase words joined by hyphens, at most 60 characters;
- `collection.json` is a valid STAC Collection (core and Themes schemas);
- its id is `benchmark-<slug>`, it is in the `benchmark` domain, its title is 5-120
  characters and its description 20-4000;
- every `item` link points at a released Item that exists in the public catalog,
  each plant appears once, and there are at most 20 000;
- `search.json` exists, records the searches and the plants added or removed by hand,
  and is linked with `via`.

These are the rules EnergyBench applies again when it publishes a merged benchmark.

Usage: `uv run scripts/validate.py [--api https://energybench.org/api]`.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import httpx
import pystac.validation
from pystac.errors import STACValidationError

type JSON = dict[str, Any]
"""A JSON object, such as a STAC Collection."""

API_URL = "https://energybench.org/api"
DOMAIN_SCHEME = "https://energybench.org/domains"
PREFIX = "benchmark-"
ITEM_PATH = re.compile(r"/collections/([^/]+)/items/([^/?#]+)$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SLUG = 60
MAX_ITEMS = 20_000
TITLE_LENGTH = (5, 120)
DESCRIPTION_LENGTH = (20, 4000)
SEARCH_CHUNK = 250


def read_json(path: Path) -> JSON:
    """Read a file that must hold one JSON object.

    Args:
        path (Path): The file.

    Returns:
        JSON: Its content.

    Raises:
        ValueError: If the file is not valid JSON or not an object.
        OSError: If the file cannot be read.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("not a JSON object")
    return document


def check_search(folder: Path) -> list[str]:
    """Check a benchmark's search record, `search.json`.

    Args:
        folder (Path): `benchmarks/<slug>/`.

    Returns:
        list[str]: Problems found; empty if none.
    """
    path = folder / "search.json"
    if not path.exists():
        return ["search.json is missing"]
    try:
        search = read_json(path)
    except (OSError, ValueError) as err:
        return [f"search.json unreadable: {err}"]
    problems: list[str] = []
    for key in ("searches", "added", "removed"):
        if not isinstance(search.get(key), list):
            problems.append(f"search.json needs '{key}' as a list")
    return problems


def check_metadata(collection: JSON, slug: str) -> list[str]:
    """Check a benchmark Collection's ID, title, description and domain.

    Args:
        collection (JSON): The benchmark Collection.
        slug (str): Its folder name.

    Returns:
        list[str]: Problems found; empty if none.
    """
    problems: list[str] = []
    if not SLUG.match(slug) or len(slug) > MAX_SLUG:
        problems.append(
            "folder name must be lowercase words joined by hyphens, "
            f"at most {MAX_SLUG} characters"
        )
    try:
        pystac.validation.validate_dict(collection)
    except STACValidationError as err:
        problems.append(f"not valid STAC: {str(err).splitlines()[0]}")
    if collection.get("id") != PREFIX + slug:
        problems.append(f"id must be '{PREFIX}{slug}'")
    title = str(collection.get("title", "")).strip()
    if not TITLE_LENGTH[0] <= len(title) <= TITLE_LENGTH[1]:
        problems.append(f"title must be {TITLE_LENGTH[0]}-{TITLE_LENGTH[1]} characters")
    description = str(collection.get("description", "")).strip()
    if not DESCRIPTION_LENGTH[0] <= len(description) <= DESCRIPTION_LENGTH[1]:
        problems.append(
            f"description must be {DESCRIPTION_LENGTH[0]}-{DESCRIPTION_LENGTH[1]} "
            "characters"
        )
    themes = collection.get("themes") or []
    if not any(
        isinstance(theme, dict)
        and theme.get("scheme") == DOMAIN_SCHEME
        and any(
            isinstance(concept, dict) and concept.get("id") == "benchmark"
            for concept in theme.get("concepts") or []
        )
        for theme in themes
    ):
        problems.append("must be in the 'benchmark' domain")
    return problems


def item_refs(links: list[JSON]) -> tuple[list[tuple[str, str]], list[str]]:
    """Read the pinned Items from a Collection's `item` links.

    Args:
        links (list[JSON]): The Collection's links.

    Returns:
        tuple[list[tuple[str, str]], list[str]]: (release Collection ID, Item ID)
            for each valid link, in order, and the problems found.
    """
    refs: list[tuple[str, str]] = []
    problems: list[str] = []
    for link in links:
        if link.get("rel") != "item":
            continue
        match = ITEM_PATH.search(str(link.get("href", "")))
        if not match or "__" not in match.group(1):
            problems.append(f"item link is not a released Item: {link.get('href')}")
            continue
        refs.append((match.group(1), match.group(2)))
    if not refs:
        problems.append("must link at least one item")
    if len(refs) > MAX_ITEMS:
        problems.append(f"may link at most {MAX_ITEMS} items, not {len(refs)}")
    if len({item_id for _, item_id in refs}) != len(refs):
        problems.append("each plant may appear once, in one release")
    return refs, problems


def missing_items(refs: list[tuple[str, str]], client: httpx.Client) -> list[str]:
    """Look up the pinned Items in the public catalog.

    Args:
        refs (list[tuple[str, str]]): (release Collection ID, Item ID) pairs.
        client (httpx.Client): Client for the public STAC API.

    Returns:
        list[str]: One problem per release Collection with Items that don't exist.

    Raises:
        httpx.HTTPError: If the API cannot be reached or returns an error.
    """
    by_collection: dict[str, list[str]] = {}
    for collection_id, item_id in refs:
        by_collection.setdefault(collection_id, []).append(item_id)
    problems: list[str] = []
    for collection_id, ids in by_collection.items():
        found: set[str] = set()
        for start in range(0, len(ids), SEARCH_CHUNK):
            chunk = ids[start : start + SEARCH_CHUNK]
            response = client.post(
                "search",
                json={
                    "collections": [collection_id],
                    "ids": chunk,
                    "limit": len(chunk),
                    "fields": {"include": ["id"]},
                },
            )
            response.raise_for_status()
            found |= {
                str(feature.get("id"))
                for feature in response.json().get("features", [])
            }
        missing = [item_id for item_id in ids if item_id not in found]
        if missing:
            problems.append(
                f"{len(missing)} items not in {collection_id}, e.g. {missing[0]}"
            )
    return problems


def check(folder: Path, client: httpx.Client) -> list[str]:
    """Check one benchmark folder.

    Args:
        folder (Path): `benchmarks/<slug>/`.
        client (httpx.Client): Client for the public STAC API.

    Returns:
        list[str]: Problems found; empty if none.
    """
    try:
        collection = read_json(folder / "collection.json")
    except (OSError, ValueError) as err:
        return [f"collection.json unreadable: {err}"]
    problems = check_metadata(collection, folder.name)
    links = [link for link in collection.get("links") or [] if isinstance(link, dict)]
    if not any(
        link.get("rel") == "via" and link.get("href") == "./search.json"
        for link in links
    ):
        problems.append("search.json must be linked with rel 'via'")
    problems += check_search(folder)
    refs, link_problems = item_refs(links)
    problems += link_problems
    try:
        problems += missing_items(refs, client)
    except httpx.HTTPError as err:
        problems.append(f"could not look up the items in the catalog: {err}")
    return problems


def main(argv: list[str] | None = None) -> int:
    """Check every benchmark and report the problems found.

    Args:
        argv (list[str] | None): Command-line arguments; `sys.argv` if None.

    Returns:
        int: Exit code, 1 if any benchmark has problems and 0 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    parser.add_argument("--api", default=API_URL, help="STAC API root")
    parser.add_argument(
        "--root", type=Path, default=Path("benchmarks"), help="benchmarks folder"
    )
    args = parser.parse_args(argv)
    api: str = args.api
    root: Path = args.root
    folders = sorted(path for path in root.iterdir() if path.is_dir())
    failed = False
    with httpx.Client(base_url=api.rstrip("/") + "/", timeout=60) as client:
        for folder in folders:
            problems = check(folder, client)
            print(f"{'✗' if problems else '✓'} {folder.name}")
            for problem in problems:
                print(f"    {problem}")
            failed = failed or bool(problems)
    if not folders:
        print(f"No benchmarks in {root}/.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
