#!/usr/bin/env python3
"""Verify pinned standards identities, notices, digests and clause anchors offline."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Sequence
from urllib.parse import urlsplit


_MANIFEST = Path(__file__).resolve().parents[1] / "docs" / "standards" / "manifest.json"
_REFERENCE_IDS = frozenset(
    {
        "RDF11-CONCEPTS", "RDFC10", "TURTLE11", "TRIG11", "NTRIPLES11", "NQUADS11", "RDFXML11",
        "JSONLD11", "JSONLD11-API", "XML10", "XMLNS10", "RFC3986", "RFC3987", "RFC8259",
    }
)
_ASSET_FIELDS = frozenset(
    {"id", "title", "source_url", "resolved_url", "path", "media_type", "retrieved_at", "sha256", "notice"}
)
_REFERENCE_FIELDS = _ASSET_FIELDS | {"edition", "publication_date", "status", "license_ids", "anchors"}


class ReferenceValidationError(ValueError):
    """A reference catalog or one of its pinned assets is inconsistent."""


class _Document(HTMLParser):
    """Collect textual identity and both forms of HTML fragment identifiers."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: set[str] = set()
        self.text: list[str] = []
        self._hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._hidden += 1
        for key, value in attrs:
            if value and (key == "id" or (tag == "a" and key == "name")):
                self.anchors.add(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._hidden:
            self._hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self._hidden:
            self.text.append(data)


def html_anchors(text: str) -> set[str]:
    """Return the fragment identifiers present in an original HTML document."""
    document = _Document()
    document.feed(text)
    return document.anchors


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReferenceValidationError(message)


def _strings(value: Any, label: str) -> list[str]:
    _require(isinstance(value, list), f"{label} must be a list")
    _require(all(isinstance(item, str) and item.strip() for item in value), f"{label} must contain nonempty strings")
    _require(len(value) == len(set(value)), f"{label} contains duplicates")
    return value


def _date(value: str, label: str, *, month_allowed: bool = False) -> None:
    pattern = r"\d{4}-\d{2}(?:-\d{2})?" if month_allowed else r"\d{4}-\d{2}-\d{2}"
    _require(re.fullmatch(pattern, value) is not None, f"{label} must be an ISO date")
    try:
        date.fromisoformat(value + "-01" if len(value) == 7 else value)
    except ValueError as error:
        raise ReferenceValidationError(f"{label} is not a valid date") from error


def _has_control_characters(value: str) -> bool:
    return any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value)


def _https_url(value: str, label: str) -> None:
    message = f"{label} must be an HTTPS URL with a hostname and valid port"
    _require(not _has_control_characters(value) and not any(character.isspace() for character in value), message)
    try:
        url = urlsplit(value)
        hostname = url.hostname
        port = url.port
    except ValueError as error:
        raise ReferenceValidationError(message) from error
    _require(url.scheme == "https" and bool(hostname) and not url.fragment, message)
    _require(port is None or 0 <= port <= 65535, message)


def _contained_path(root: Path, value: str) -> Path:
    path = PurePosixPath(value)
    _require(
        not path.is_absolute() and not _has_control_characters(value)
        and not any(character in value for character in '\\:<>"|?*')
        and all(part not in {"", ".", ".."} for part in value.split("/"))
        and path.parts[0] == "references",
        f"unsafe asset path: {value!r}",
    )
    try:
        resolved = (root / path).resolve()
        reference_root = root.resolve() / "references"
    except (OSError, RuntimeError, ValueError) as error:
        raise ReferenceValidationError(f"cannot resolve asset path: {value!r}") from error
    _require(resolved.is_relative_to(reference_root), f"asset path escapes references: {value!r}")
    return resolved


def _asset(root: Path, item: Any, *, reference: bool) -> tuple[str, set[str]]:
    _require(isinstance(item, dict), "asset must be an object")
    expected = _REFERENCE_FIELDS if reference else _ASSET_FIELDS
    _require(set(item) == expected, f"asset fields differ from schema: {item.get('id', '<unnamed>')}")
    for field in expected - {"license_ids", "anchors"}:
        _require(isinstance(item[field], str) and bool(item[field].strip()), f"{field} must be a nonempty string")
    for field in ("source_url", "resolved_url"):
        _https_url(item[field], field)
    _date(item["retrieved_at"], "retrieved_at")
    _require(item["media_type"] in {"text/html", "text/plain"}, "unsupported media_type")
    _require(re.fullmatch(r"[a-f0-9]{64}", item["sha256"]) is not None, "sha256 must be 64 lowercase hex digits")
    path = _contained_path(root, item["path"])
    try:
        is_file = path.is_file()
        data = path.read_bytes() if is_file else None
    except (OSError, ValueError) as error:
        raise ReferenceValidationError(f"cannot read asset: {item['path']!r}") from error
    _require(data is not None, f"missing asset: {item['path']}")
    _require(hashlib.sha256(data).hexdigest() == item["sha256"], f"digest mismatch: {item['path']}")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReferenceValidationError(f"asset is not UTF-8: {item['path']}") from error
    document = _Document()
    if item["media_type"] == "text/html":
        document.feed(text)
        text = " ".join(document.text)
    normalized = " ".join(text.split())
    _require(" ".join(item["title"].split()) in normalized, f"title absent from asset: {item['id']}")
    if reference:
        _date(item["publication_date"], "publication_date", month_allowed=True)
        _require(item["status"] in normalized, f"status absent from asset: {item['id']}")
        _require(item["edition"] in normalized, f"edition absent from asset: {item['id']}")
        _require("Copyright" in normalized, f"copyright notice absent from asset: {item['id']}")
        _require(bool(_strings(item["license_ids"], "license_ids")), "license_ids must not be empty")
        _require(isinstance(item["anchors"], list), "anchors must be a list")
        names: set[str] = set()
        for anchor in item["anchors"]:
            _require(
                isinstance(anchor, dict) and set(anchor) == {"id", "section", "normative"}, "invalid anchor fields"
            )
            _require(isinstance(anchor["id"], str) and bool(anchor["id"]), "anchor id must be a nonempty string")
            _require(isinstance(anchor["section"], str) and bool(anchor["section"]), "anchor section must be nonempty")
            _require(type(anchor["normative"]) is bool, "anchor normative must be a boolean")
            _require(anchor["id"] not in names, f"duplicate anchor: {anchor['id']}")
            names.add(anchor["id"])
            _require(anchor["id"] in document.anchors, f"missing HTML anchor: {item['id']}#{anchor['id']}")
    return item["id"], document.anchors


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def check_catalog(manifest_path: Path = _MANIFEST) -> dict[str, Any]:
    """Validate the complete pinned inventory and return its parsed catalog."""
    try:
        catalog = json.loads(manifest_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReferenceValidationError(f"cannot read catalog: {error}") from error
    _require(
        isinstance(catalog, dict) and set(catalog) == {"schema_version", "references", "licenses"},
        "invalid catalog fields",
    )
    _require(type(catalog["schema_version"]) is int and catalog["schema_version"] == 1, "unsupported schema_version")
    for group in ("references", "licenses"):
        _require(isinstance(catalog[group], list) and bool(catalog[group]), f"{group} must be a nonempty list")
    ids: set[str] = set()
    paths: set[str] = set()
    resolved_paths: set[Path] = set()
    for group in ("references", "licenses"):
        for item in catalog[group]:
            identity, _ = _asset(manifest_path.parent, item, reference=group == "references")
            _require(identity not in ids, f"duplicate asset ID: {identity}")
            _require(item["path"] not in paths, f"duplicate asset path: {item['path']}")
            resolved = _contained_path(manifest_path.parent, item["path"])
            _require(resolved not in resolved_paths, f"duplicate resolved asset path: {item['path']}")
            ids.add(identity)
            paths.add(item["path"])
            resolved_paths.add(resolved)
    reference_ids = {item["id"] for item in catalog["references"]}
    _require(reference_ids == _REFERENCE_IDS, f"reference inventory differs: {sorted(reference_ids ^ _REFERENCE_IDS)}")
    license_ids = {item["id"] for item in catalog["licenses"]}
    for reference in catalog["references"]:
        _require(set(reference["license_ids"]) <= license_ids, f"unknown license ID: {reference['id']}")
    return catalog


def main(arguments: Sequence[str] | None = None) -> int:
    """Check a catalog without network access or asset modifications."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=_MANIFEST)
    args = parser.parse_args(arguments)
    try:
        catalog = check_catalog(args.manifest)
    except ReferenceValidationError as error:
        print(f"standards verification failed: {error}")
        return 1
    print(
        f"verified {len(catalog['references'])} standards and {len(catalog['licenses'])} license/notice assets offline"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
