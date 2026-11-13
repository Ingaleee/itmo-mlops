"""Versioned SQLite FTS5 snapshots; search filters precede ranking."""

from collections import defaultdict
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid

import pymorphy3
from app.corpus import inspect, unique_object
from app.token_budget import Budget, TOKENIZER_SHA

MORPH = pymorphy3.MorphAnalyzer()
STOP = set(
    "а и или в во на по для как какой какая какие что это с со из ли бы при к до после от у не их нас нам он она они сколько чем почему откуда когда сейчас нужно надо будет бы быть же ещё также об этом том то его ее число взялось".split()
)
SYNONYMS = {
    "пуш": "уведомление",
    "push": "уведомление",
    "резерв": "бюджет",
    "расширение": "приемка расширяем",
    "удвоение": "скачивание трафик",
    "видеозвонки": "звонки",
    "предел": "лимит",
    "подписчик": "канал",
}
EXCLUDED_CONTEXT = {("S-06", "1.0", "s02")}
ALIASES = {
    MORPH.parse(key)[0].normal_form: [
        MORPH.parse(w)[0].normal_form for w in value.split()
    ]
    for key, value in SYNONYMS.items()
}


def tokens(text):
    # Treat a grouped amount as one value; common groups such as 000 are not
    # independent evidence for an unrelated limit or budget.
    text = re.sub(r"(?<=\d)[\s\u00a0](?=\d{3}(?:\D|$))", "", text)
    words = re.findall(r"[a-zа-я0-9_]+", text.lower().replace("ё", "е"))
    expanded = []
    for word in words:
        if word in STOP:
            continue
        stem = MORPH.parse(word)[0].normal_form
        expanded.append(stem)
        expanded.extend(ALIASES.get(stem, []))
    return list(dict.fromkeys(expanded))


def build(corpus_path: Path, target: Path):
    raw = corpus_path.read_bytes()
    report = inspect(raw)
    corpus = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object)
    generation = hashlib.sha256(
        raw + b"fts5-morph3-token150-v5" + TOKENIZER_SHA.encode()
    ).hexdigest()[:16]
    budget = Budget()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with closing(sqlite3.connect(temporary)) as db:
            db.executescript("""
                CREATE TABLE metadata(generation TEXT NOT NULL, corpus_sha256 TEXT NOT NULL);
                CREATE TABLE documents(doc_id TEXT, version TEXT, status TEXT, visibility TEXT,
                  section TEXT, subsection TEXT, body TEXT, PRIMARY KEY(doc_id, version));
                CREATE TABLE chunks(id INTEGER PRIMARY KEY, doc_id TEXT, version TEXT, anchor TEXT,
                  chunk_id TEXT UNIQUE, section_title TEXT, excerpt TEXT, eligible INTEGER);
                CREATE VIRTUAL TABLE search USING fts5(title, path, heading, body, content='');
            """)
            db.execute(
                "INSERT INTO metadata VALUES (?, ?)",
                (generation, report["corpus_sha256"]),
            )
            for section in corpus["sections"]:
                for subsection in section["subsections"]:
                    for doc in subsection["documents"]:
                        db.execute(
                            "INSERT INTO documents VALUES (?,?,?,?,?,?,?)",
                            (
                                doc["id"],
                                doc["version"],
                                doc["status"],
                                doc["visibility"],
                                *doc["path"],
                                json.dumps(doc, ensure_ascii=False),
                            ),
                        )
                        for fragment in doc["sections"]:
                            for n, paragraph in enumerate(fragment["body"]):
                                for start, excerpt in enumerate(
                                    budget.chunks(paragraph)
                                ):
                                    chunk = f"{doc['id']}@{doc['version']}#{fragment['anchor']}:{n}:{start}"
                                    eligible = (
                                        doc["id"],
                                        doc["version"],
                                        fragment["anchor"],
                                    ) not in EXCLUDED_CONTEXT
                                    cursor = db.execute(
                                        "INSERT INTO chunks(doc_id,version,anchor,chunk_id,section_title,excerpt,eligible) VALUES (?,?,?,?,?,?,?)",
                                        (
                                            doc["id"],
                                            doc["version"],
                                            fragment["anchor"],
                                            chunk,
                                            fragment["title"],
                                            excerpt,
                                            int(eligible),
                                        ),
                                    )
                                    db.execute(
                                        "INSERT INTO search(rowid,title,path,heading,body) VALUES (?,?,?,?,?)",
                                        (
                                            cursor.lastrowid,
                                            " ".join(tokens(doc["title"])),
                                            " ".join(tokens(" ".join(doc["path"]))),
                                            " ".join(tokens(fragment["title"])),
                                            " ".join(tokens(excerpt)),
                                        ),
                                    )
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert db.execute("SELECT count(*) FROM documents").fetchone()[0] == 36
            db.commit()
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return {**report, "generation": generation}


class Knowledge:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        # An operation reads one complete snapshot during atomic replacement.
        with closing(
            sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
        ) as db:
            db.row_factory = sqlite3.Row
            yield db

    def metadata(self):
        with self.connect() as db:
            return dict(db.execute("SELECT * FROM metadata").fetchone())

    def get(self, doc_id, version):
        with self.connect() as db:
            row = db.execute(
                "SELECT body FROM documents WHERE doc_id=? AND version=?",
                (doc_id, version),
            ).fetchone()
            if row is None:
                raise ValueError("Document revision not found")
            return json.loads(row[0])

    def tree(self):
        result = defaultdict(lambda: defaultdict(list))
        with self.connect() as db:
            generation = db.execute("SELECT generation FROM metadata").fetchone()[0]
            for row in db.execute(
                "SELECT * FROM documents ORDER BY section,subsection,doc_id,version"
            ):
                doc = json.loads(row["body"])
                result[row["section"]][row["subsection"]].append(
                    {
                        key: doc[key]
                        for key in ("id", "version", "title", "status", "visibility")
                    }
                )
        return {
            "generation": generation,
            "sections": [
                {
                    "id": a,
                    "title": a,
                    "subsections": [
                        {"id": b, "title": b, "documents": docs}
                        for b, docs in sub.items()
                    ],
                }
                for a, sub in result.items()
            ],
        }

    def search(
        self, query, limit=5, path=None, statuses=None, doc_id=None, version=None
    ):
        if not isinstance(query, str) or not 2 <= len(query.strip()) <= 500:
            raise ValueError("Query must contain 2–500 characters")
        if type(limit) is not int or not 1 <= limit <= 10:
            raise ValueError("Limit must be an integer between 1 and 10")
        statuses = ["Действует"] if statuses is None else statuses
        if not statuses or set(statuses) - {"Действует", "Архив", "Черновик"}:
            raise ValueError("Invalid statuses")
        if path is not None and (
            not isinstance(path, list)
            or not 1 <= len(path) <= 2
            or any(not isinstance(p, str) for p in path)
        ):
            raise ValueError("Path must contain section and optional subsection")
        if version and not doc_id:
            raise ValueError("Version selection requires document ID")
        words = tokens(query)
        exact = re.findall(r"\b([A-Za-z]-\d{2})(?:@(\d+\.\d+))?\b", query)
        if exact and not doc_id:
            doc_id, supplied_version = exact[0]
            doc_id = doc_id.upper()
            if supplied_version:
                version = supplied_version
        filters = [
            "d.status IN (" + ",".join("?" for _ in statuses) + ")",
            "c.eligible=1",
        ]
        values = list(statuses)
        if path:
            filters.append(
                "(d.section=?"
                + (" AND d.subsection=?" if len(path) == 2 else " OR d.subsection=?")
                + ")"
            )
            values.extend(path if len(path) == 2 else [path[0], path[0]])
        for key, value in (("doc_id", doc_id), ("version", version)):
            if value:
                filters.append(f"d.{key}=?")
                values.append(value)
        match = " OR ".join('"' + word.replace('"', '""') + '"' for word in words)
        with self.connect() as db:
            generation = db.execute("SELECT generation FROM metadata").fetchone()[0]
            if not match and not doc_id:
                return {"generation": generation, "cards": []}
            if doc_id:
                sql = (
                    "SELECT c.*,d.body AS document,0 AS rank FROM chunks c JOIN documents d USING(doc_id,version) WHERE "
                    + " AND ".join(filters)
                    + " ORDER BY c.id"
                )
                args = values
            else:
                sql = (
                    "SELECT c.*,d.body AS document,bm25(search,3,0.5,2,1) AS rank FROM search JOIN chunks c ON c.id=search.rowid JOIN documents d ON d.doc_id=c.doc_id AND d.version=c.version WHERE search MATCH ? AND "
                    + " AND ".join(filters)
                    + " ORDER BY rank,c.id LIMIT 300"
                )
                args = [match, *values]
            rows = db.execute(sql, args).fetchall()
            cards = {}
            for row in rows:
                doc = json.loads(row["document"])
                key = (doc["id"], doc["version"])
                if key not in cards:
                    cards[key] = {
                        k: doc[k]
                        for k in (
                            "id",
                            "version",
                            "title",
                            "status",
                            "visibility",
                            "path",
                            "links",
                        )
                    }
                    cards[key].update(rank=len(cards), fragments=[])
                if len(cards[key]["fragments"]) < 3:
                    cards[key]["fragments"].append(
                        {
                            "anchor": row["anchor"],
                            "chunk_id": row["chunk_id"],
                            "heading": row["section_title"],
                            "text": row["excerpt"],
                            "rank": row["rank"],
                        }
                    )
        ranked = list(cards.values())
        if ranked and not doc_id:
            # The best lexical hit points to canonical related sources. Boost
            # only revisions already matched under the same status/path filters.
            links = set(ranked[0]["links"])
            ranked = [
                ranked[0],
                *[c for c in ranked[1:] if c["id"] + "@" + c["version"] in links],
                *[c for c in ranked[1:] if c["id"] + "@" + c["version"] not in links],
            ]
        ranked = ranked[:limit]
        for n, card in enumerate(ranked, 1):
            card["rank"] = n
        return {"generation": generation, "cards": ranked}
