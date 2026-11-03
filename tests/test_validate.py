"""Tests for scripts/validate.py, with the STAC API mocked."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pystac.validation
import pytest
from pystac.errors import STACValidationError

import validate

API = "https://energybench.org/api"
SLUG = "example-wind-farms"

type Handler = Callable[[httpx.Request], httpx.Response]


def make_collection(slug: str = SLUG, items: int = 2) -> dict[str, Any]:
    """A benchmark Collection in the form the submission bot writes.

    Args:
        slug (str): Benchmark slug.
        items (int): How many plants to link.

    Returns:
        dict[str, Any]: The Collection.
    """
    return {
        "type": "Collection",
        "stac_version": "1.0.0",
        "stac_extensions": [
            "https://stac-extensions.github.io/themes/v1.0.0/schema.json"
        ],
        "id": f"benchmark-{slug}",
        "title": "Example wind farms",
        "description": "A made-up selection of wind farms, used only in tests.",
        "license": "other",
        "keywords": ["benchmark", "wind"],
        "providers": [
            {"name": "Test Person", "roles": ["producer"], "url": "https://orcid.org"},
            {
                "name": "Energybench Association",
                "roles": ["host"],
                "url": "https://energybench.org",
            },
        ],
        "extent": {
            "spatial": {"bbox": [[-73.9, -42.3, -68.8, -22.5]]},
            "temporal": {"interval": [["2015-01-01T00:00:00Z", None]]},
        },
        "summaries": {"energy:fuel_type": ["wind"]},
        "themes": [
            {
                "scheme": "https://energybench.org/domains",
                "concepts": [{"id": "benchmark"}],
            }
        ],
        "created": "2026-11-01T00:00:00Z",
        "links": [
            {"rel": "root", "href": f"{API}/", "type": "application/json"},
            {
                "rel": "via",
                "href": "./search.json",
                "type": "application/json",
                "title": "How this selection was made",
            },
            *(
                {
                    "rel": "item",
                    "href": f"{API}/collections/demo__v1.0.0/items/demo-{i}",
                    "type": "application/geo+json",
                    "title": f"Plant {i}",
                }
                for i in range(items)
            ),
        ],
    }


SEARCH: dict[str, Any] = {
    "searches": [{"collections": ["demo__v1.0.0"]}],
    "added": [],
    "removed": [],
    "resolved": "2026-11-01T00:00:00Z",
}


def write_benchmark(
    root: Path,
    slug: str = SLUG,
    collection: dict[str, Any] | None = None,
    search: dict[str, Any] | None = None,
) -> Path:
    """Write a benchmark folder the way the submission bot does.

    Args:
        root (Path): The `benchmarks/` folder.
        slug (str): Folder name.
        collection (dict[str, Any] | None): Collection; a valid one if None.
        search (dict[str, Any] | None): Search record; a valid one if None.

    Returns:
        Path: The benchmark folder.
    """
    folder = root / slug
    folder.mkdir(parents=True)
    for name, document in (
        ("collection.json", collection or make_collection(slug)),
        ("search.json", search or SEARCH),
    ):
        text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
        (folder / name).write_text(text, encoding="utf-8")
    return folder


def catalog(known: set[str], requests: list[dict[str, Any]] | None = None) -> Handler:
    """A mock STAC API search that finds only the given Items.

    Args:
        known (set[str]): "<collection>/<id>" of every Item in the catalog.
        requests (list[dict[str, Any]] | None): Collects each search body, if given.

    Returns:
        Handler: The request handler.
    """

    def handle(request: httpx.Request) -> httpx.Response:
        """Answer a POST /search like the STAC API.

        Args:
            request (httpx.Request): The request.

        Returns:
            httpx.Response: The matching Items' IDs.
        """
        assert request.method == "POST"
        assert request.url.path == "/api/search"
        body: dict[str, Any] = json.loads(request.content)
        if requests is not None:
            requests.append(body)
        (collection,) = body["collections"]
        ids = [i for i in body["ids"] if f"{collection}/{i}" in known]
        features = [{"id": i} for i in ids[: body["limit"]]]
        return httpx.Response(200, json={"features": features})

    return handle


def client_for(handler: Handler) -> httpx.Client:
    """An API client that answers from a handler instead of the network.

    Args:
        handler (Handler): The request handler.

    Returns:
        httpx.Client: The client.
    """
    return httpx.Client(
        base_url=f"{API}/", transport=httpx.MockTransport(handler), timeout=5
    )


ALL_KNOWN = {f"demo__v1.0.0/demo-{i}" for i in range(validate.MAX_ITEMS + 1)}


@pytest.fixture(autouse=True)
def offline_schemas(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Skip the STAC schema check, which downloads schemas, unless marked network.

    Args:
        request (pytest.FixtureRequest): The running test.
        monkeypatch (pytest.MonkeyPatch): Patches the schema validator.
    """
    if request.node.get_closest_marker("network") is None:

        def accept(_stac: dict[str, Any]) -> list[str]:
            """Accept any document.

            Args:
                _stac (dict[str, Any]): The document (unused).

            Returns:
                list[str]: No schemas checked.
            """
            return []

        monkeypatch.setattr(pystac.validation, "validate_dict", accept)


def test_valid_benchmark_passes(tmp_path: Path) -> None:
    """A benchmark as the bot writes it, with every Item in the catalog, passes.

    Args:
        tmp_path (Path): Temporary folder.
    """
    folder = write_benchmark(tmp_path)
    with client_for(catalog(ALL_KNOWN)) as client:
        assert validate.check(folder, client) == []


def test_search_is_chunked_per_release(tmp_path: Path) -> None:
    """Items are looked up per release Collection, at most 250 per request.

    Args:
        tmp_path (Path): Temporary folder.
    """
    collection = make_collection(items=600)
    collection["links"].append(
        {"rel": "item", "href": f"{API}/collections/other__v2/items/other-1"}
    )
    folder = write_benchmark(tmp_path, collection=collection)
    requests: list[dict[str, Any]] = []
    known = ALL_KNOWN | {"other__v2/other-1"}
    with client_for(catalog(known, requests)) as client:
        assert validate.check(folder, client) == []
    assert [(r["collections"], len(r["ids"])) for r in requests] == [
        (["demo__v1.0.0"], 250),
        (["demo__v1.0.0"], 250),
        (["demo__v1.0.0"], 100),
        (["other__v2"], 1),
    ]
    assert all(r["fields"] == {"include": ["id"]} for r in requests)


def test_missing_items_are_reported(tmp_path: Path) -> None:
    """Items that are not in the catalog are counted, with an example.

    Args:
        tmp_path (Path): Temporary folder.
    """
    folder = write_benchmark(tmp_path, collection=make_collection(items=3))
    with client_for(catalog({"demo__v1.0.0/demo-0"})) as client:
        problems = validate.check(folder, client)
    assert problems == ["2 items not in demo__v1.0.0, e.g. demo-1"]


def test_api_errors_are_problems(tmp_path: Path) -> None:
    """An API error is reported for the benchmark instead of crashing the run.

    Args:
        tmp_path (Path): Temporary folder.
    """
    folder = write_benchmark(tmp_path)
    with client_for(lambda _request: httpx.Response(503)) as client:
        (problem,) = validate.check(folder, client)
    assert problem.startswith("could not look up the items in the catalog")


BREAKS: list[tuple[str, Callable[[dict[str, Any]], object], str]] = [
    (
        "wrong-id",
        lambda c: c.update(id="benchmark-other"),
        f"id must be 'benchmark-{SLUG}'",
    ),
    ("short-title", lambda c: c.update(title="abc"), "title must be 5-120 characters"),
    (
        "long-title",
        lambda c: c.update(title="x" * 121),
        "title must be 5-120 characters",
    ),
    ("no-title", lambda c: c.pop("title"), "title must be 5-120 characters"),
    (
        "short-description",
        lambda c: c.update(description="Too short."),
        "description must be 20-4000 characters",
    ),
    (
        "long-description",
        lambda c: c.update(description="x" * 4001),
        "description must be 20-4000 characters",
    ),
    ("no-domain", lambda c: c.update(themes=[]), "must be in the 'benchmark' domain"),
    (
        "other-domain",
        lambda c: c.update(
            themes=[
                {
                    "scheme": "https://energybench.org/domains",
                    "concepts": [{"id": "generation"}],
                }
            ]
        ),
        "must be in the 'benchmark' domain",
    ),
    (
        "no-via",
        lambda c: c.update(links=[x for x in c["links"] if x["rel"] != "via"]),
        "search.json must be linked with rel 'via'",
    ),
    (
        "no-items",
        lambda c: c.update(links=[x for x in c["links"] if x["rel"] != "item"]),
        "must link at least one item",
    ),
    (
        "duplicate-plant",
        lambda c: c["links"].append(
            {"rel": "item", "href": f"{API}/collections/demo__v2.0.0/items/demo-0"}
        ),
        "each plant may appear once, in one release",
    ),
    (
        "unreleased-collection",
        lambda c: c["links"].append(
            {"rel": "item", "href": f"{API}/collections/demo/items/demo-9"}
        ),
        f"item link is not a released Item: {API}/collections/demo/items/demo-9",
    ),
    (
        "not-an-api-item",
        lambda c: c["links"].append(
            {"rel": "item", "href": "https://example.org/demo-9.json"}
        ),
        "item link is not a released Item: https://example.org/demo-9.json",
    ),
]
"""Ways to break a valid Collection: test ID, change, and the problem it causes."""


@pytest.mark.parametrize(
    ("name", "change", "expected"), BREAKS, ids=[b[0] for b in BREAKS]
)
def test_rule_violations(
    tmp_path: Path,
    name: str,
    change: Callable[[dict[str, Any]], object],
    expected: str,
) -> None:
    """Each broken rule is reported on its own.

    Args:
        tmp_path (Path): Temporary folder.
        name (str): Test ID (unused).
        change (Callable[[dict[str, Any]], object]): Breaks a valid Collection.
        expected (str): The one problem it should cause.
    """
    collection = make_collection()
    change(collection)
    folder = write_benchmark(tmp_path, collection=collection)
    known = ALL_KNOWN | {"demo__v2.0.0/demo-0"}
    with client_for(catalog(known)) as client:
        assert validate.check(folder, client) == [expected]


def test_too_many_items(tmp_path: Path) -> None:
    """More than 20 000 plants are rejected.

    Args:
        tmp_path (Path): Temporary folder.
    """
    collection = make_collection(items=validate.MAX_ITEMS + 1)
    folder = write_benchmark(tmp_path, collection=collection)
    with client_for(catalog(ALL_KNOWN)) as client:
        problems = validate.check(folder, client)
    assert problems == ["may link at most 20000 items, not 20001"]


@pytest.mark.parametrize("slug", ["Upper-Case", "under_score", "x" * 61, "a--b"])
def test_bad_folder_names(tmp_path: Path, slug: str) -> None:
    """Folder names must be short, lowercase and hyphenated.

    Args:
        tmp_path (Path): Temporary folder.
        slug (str): A bad folder name.
    """
    folder = write_benchmark(tmp_path, slug=slug, collection=make_collection(slug))
    with client_for(catalog(ALL_KNOWN)) as client:
        problems = validate.check(folder, client)
    assert problems == [
        "folder name must be lowercase words joined by hyphens, at most 60 characters"
    ]


def test_unreadable_collection(tmp_path: Path) -> None:
    """A collection.json that is not a JSON object stops the checks early.

    Args:
        tmp_path (Path): Temporary folder.
    """
    folder = write_benchmark(tmp_path)
    (folder / "collection.json").write_text("[]\n")
    with client_for(catalog(ALL_KNOWN)) as client:
        assert validate.check(folder, client) == [
            "collection.json unreadable: not a JSON object"
        ]
    (folder / "collection.json").unlink()
    with client_for(catalog(ALL_KNOWN)) as client:
        (problem,) = validate.check(folder, client)
    assert problem.startswith("collection.json unreadable:")


def test_search_record_problems(tmp_path: Path) -> None:
    """search.json must exist, be JSON and hold the searches and manual changes.

    Args:
        tmp_path (Path): Temporary folder.
    """
    folder = write_benchmark(tmp_path, search={"searches": [], "added": "x"})
    with client_for(catalog(ALL_KNOWN)) as client:
        assert validate.check(folder, client) == [
            "search.json needs 'added' as a list",
            "search.json needs 'removed' as a list",
        ]
        (folder / "search.json").write_text("{")
        (problem,) = validate.check(folder, client)
        assert problem.startswith("search.json unreadable:")
        (folder / "search.json").unlink()
        assert validate.check(folder, client) == ["search.json is missing"]


def test_invalid_stac_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first line of a STAC schema error is reported.

    Args:
        tmp_path (Path): Temporary folder.
        monkeypatch (pytest.MonkeyPatch): Makes the schema check fail.
    """

    def reject(_stac: dict[str, Any]) -> list[str]:
        """Fail like pystac does for an invalid document.

        Args:
            _stac (dict[str, Any]): The document (unused).

        Raises:
            STACValidationError: Always.
        """
        raise STACValidationError("bad extent\nlong details")

    monkeypatch.setattr(pystac.validation, "validate_dict", reject)
    folder = write_benchmark(tmp_path)
    with client_for(catalog(ALL_KNOWN)) as client:
        assert validate.check(folder, client) == ["not valid STAC: bad extent"]


@pytest.mark.network
def test_stac_schemas(tmp_path: Path) -> None:
    """The bot's Collection passes the real STAC and Themes schemas; a broken one fails.

    Args:
        tmp_path (Path): Temporary folder.
    """
    good = write_benchmark(tmp_path / "good")
    broken = make_collection()
    broken["extent"] = {"temporal": {"interval": [[None, None]]}}
    bad = write_benchmark(tmp_path / "bad", collection=broken)
    with client_for(catalog(ALL_KNOWN)) as client:
        assert validate.check(good, client) == []
        (problem,) = validate.check(bad, client)
    assert problem.startswith("not valid STAC:")


def test_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The command checks every folder, prints the results and sets the exit code.

    Args:
        tmp_path (Path): Temporary folder.
        monkeypatch (pytest.MonkeyPatch): Routes the API client to a mock.
        capsys (pytest.CaptureFixture[str]): Captures the output.
    """
    real_client = httpx.Client

    def mocked(**kwargs: Any) -> httpx.Client:  # noqa: ANN401
        """Build the client as asked, but answer from the mock catalog.

        Args:
            **kwargs (Any): The script's client options.

        Returns:
            httpx.Client: The client.
        """
        assert kwargs["base_url"] == "http://localhost/api/"
        return real_client(**kwargs, transport=httpx.MockTransport(catalog(ALL_KNOWN)))

    monkeypatch.setattr(httpx, "Client", mocked)
    root = tmp_path / "benchmarks"
    root.mkdir()
    (root / ".gitkeep").touch()
    args = ["--api", "http://localhost/api", "--root", str(root)]

    assert validate.main(args) == 0
    assert capsys.readouterr().out == f"No benchmarks in {root}/.\n"

    write_benchmark(root)
    assert validate.main(args) == 0
    assert capsys.readouterr().out == f"✓ {SLUG}\n"

    write_benchmark(root, slug="another-one", search={"searches": []})
    assert validate.main(args) == 1
    assert capsys.readouterr().out == (
        "✗ another-one\n"
        "    search.json needs 'added' as a list\n"
        "    search.json needs 'removed' as a list\n"
        f"✓ {SLUG}\n"
    )
