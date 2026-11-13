"""Validate the supplied versioned knowledge base without indexing or LLM calls."""

from collections import Counter
from datetime import date
import hashlib
import json
import re

STATUSES = {"Действует", "Архив", "Черновик"}
VISIBILITY = {"cloud_ok", "local_only"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON member: {key}")
        result[key] = value
    return result


def fields(value, names, where):
    require(
        type(value) is dict and set(value) == set(names.split()),
        f"invalid fields: {where}",
    )


def text(value):
    return type(value) is str and bool(value.strip())


def inspect(raw):
    corpus = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object)
    fields(corpus, "schema_version title sections", "corpus")
    require(
        type(corpus["schema_version"]) is int and corpus["schema_version"] == 1,
        "unsupported corpus schema",
    )
    require(text(corpus["title"]), "corpus title is missing")
    require(
        type(corpus["sections"]) is list and len(corpus["sections"]) == 6,
        "expected six sections",
    )
    documents, paths, titles = [], set(), set()
    for section in corpus["sections"]:
        fields(section, "title subsections", "section")
        require(
            text(section["title"]) and section["title"] not in titles,
            "invalid or duplicate section",
        )
        titles.add(section["title"])
        require(type(section["subsections"]) is list, "subsections must be a list")
        for subsection in section["subsections"]:
            fields(subsection, "title documents", "subsection")
            require(text(subsection["title"]), "subsection title is missing")
            path = (section["title"], subsection["title"])
            require(path not in paths, "duplicate section path")
            paths.add(path)
            require(
                type(subsection["documents"]) is list and subsection["documents"],
                "empty subsection",
            )
            for doc in subsection["documents"]:
                fields(
                    doc,
                    "id version title status date owner visibility path replaces links sections",
                    "document",
                )
                require(
                    type(doc["id"]) is str and re.fullmatch(r"[A-Z]-\d{2}", doc["id"]),
                    "invalid document ID",
                )
                require(
                    type(doc["version"]) is str
                    and re.fullmatch(r"\d+\.\d+", doc["version"]),
                    "invalid version",
                )
                key = doc["id"] + "@" + doc["version"]
                require(
                    text(doc["title"]) and text(doc["owner"]),
                    f"missing metadata: {key}",
                )
                require(
                    type(doc["status"]) is str and doc["status"] in STATUSES,
                    f"invalid status: {key}",
                )
                require(
                    type(doc["visibility"]) is str and doc["visibility"] in VISIBILITY,
                    f"invalid processing label: {key}",
                )
                require(
                    doc["path"] == list(path),
                    f"document hierarchy differs from path: {key}",
                )
                require(
                    type(doc["date"]) is str
                    and re.fullmatch(r"\d{4}-\d{2}-\d{2}", doc["date"]),
                    f"invalid ISO date: {key}",
                )
                date.fromisoformat(doc["date"])
                require(
                    type(doc["links"]) is list
                    and all(text(link) for link in doc["links"]),
                    f"invalid links: {key}",
                )
                require(
                    doc["replaces"] is None or text(doc["replaces"]),
                    f"invalid replaces: {key}",
                )
                require(
                    type(doc["sections"]) is list and doc["sections"],
                    f"empty document: {key}",
                )
                anchors = set()
                for fragment in doc["sections"]:
                    fields(fragment, "anchor title body", f"section of {key}")
                    anchor = fragment["anchor"]
                    require(
                        type(anchor) is str
                        and re.fullmatch(r"s\d{2}", anchor)
                        and anchor not in anchors,
                        f"invalid or duplicate anchor: {key}",
                    )
                    anchors.add(anchor)
                    require(
                        text(fragment["title"])
                        and type(fragment["body"]) is list
                        and fragment["body"]
                        and all(text(paragraph) for paragraph in fragment["body"]),
                        f"invalid fragment: {key}",
                    )
                documents.append(doc)
    require(
        len(paths) == 12 and len(documents) == 36,
        "expected 12 subsections and 36 records",
    )
    by_pair = {}
    for doc in documents:
        key = doc["id"] + "@" + doc["version"]
        require(key not in by_pair, f"duplicate document revision: {key}")
        by_pair[key] = doc
    require(len({doc["id"] for doc in documents}) == 35, "expected 35 unique IDs")
    active = Counter(doc["id"] for doc in documents if doc["status"] == "Действует")
    require(
        all(count == 1 for count in active.values()),
        "more than one active revision for an ID",
    )
    for key, doc in by_pair.items():
        references = doc["links"] + ([doc["replaces"]] if doc["replaces"] else [])
        require(
            all(reference in by_pair for reference in references),
            f"unresolved reference: {key}",
        )
        if doc["replaces"]:
            previous = by_pair[doc["replaces"]]
            require(
                previous["id"] == doc["id"] and previous["status"] == "Архив",
                f"invalid replaced revision: {key}",
            )
            require(
                tuple(map(int, previous["version"].split(".")))
                < tuple(map(int, doc["version"].split("."))),
                f"replacement does not advance version: {key}",
            )
            require(
                previous["date"] <= doc["date"],
                f"replacement date precedes old revision: {key}",
            )
    require(
        "M-05@2.0" in by_pair and by_pair["M-05@2.0"]["status"] == "Действует",
        "current M-05 revision missing",
    )
    require(
        "M-05@1.1" in by_pair and by_pair["M-05@1.1"]["status"] == "Архив",
        "archived M-05 revision missing",
    )
    return {
        "status": "passed",
        "corpus_sha256": hashlib.sha256(raw).hexdigest(),
        "records": len(documents),
        "unique_ids": 35,
        "sections": 6,
        "subsections": len(paths),
        "document_sections": sum(len(doc["sections"]) for doc in documents),
        "statuses": dict(Counter(doc["status"] for doc in documents)),
        "processing_labels": dict(Counter(doc["visibility"] for doc in documents)),
        "references_resolved": True,
        "unique_revisions": True,
        "single_active_revision": True,
        "hierarchy_consistent": True,
        "replacement_links_valid": True,
    }
