#!/usr/bin/env python3
"""
Build the Avar dictionary lookup artifacts from structured JSONL.

Inputs:
    docs/av-ru.dictionary.jsonl  canonical Avar -> Russian dictionary
    avar.db                      previous SQLite DB, used only for legacy rows

Outputs:
    avar.db                      enriched SQLite lookup database
    docs/avar_dictionary.md      human-readable dictionary for semantic search
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any


PAL_VARIANTS = str.maketrans(
    {
        "ӏ": "Ӏ",
        "І": "Ӏ",
        "і": "Ӏ",
        "I": "Ӏ",
        "l": "Ӏ",
        "1": "Ӏ",
        "|": "Ӏ",
        "!": "Ӏ",
        "Ⅰ": "Ӏ",
    }
)

RU_SPLIT_RE = re.compile(r"[,;]")
RU_WORD_RE = re.compile(r"[А-Яа-яЁё][А-Яа-яЁё-]{2,}")


def normalize_avar(text: str) -> str:
    """Normalize Avar lookup keys, especially the palochka variants."""
    return re.sub(r"\s+", " ", text.translate(PAL_VARIANTS).strip()).lower()


def normalize_ru(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).lower()


def clean_ru_term(text: str) -> str:
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\[[^]]*\]", "", text)
    text = text.replace("кого-либо", "").replace("что-либо", "")
    text = text.replace("кого-л.", "").replace("чего-л.", "").replace("что-л.", "")
    text = text.strip(" .:;,-")
    return normalize_ru(text)


def extract_ru_terms(text: str) -> set[str]:
    """Extract practical Russian lookup terms from a sense or example text."""
    terms: set[str] = set()
    cleaned = clean_ru_term(text)
    if cleaned:
        terms.add(cleaned)

    for part in RU_SPLIT_RE.split(text):
        term = clean_ru_term(part)
        if term:
            terms.add(term)

    for word in RU_WORD_RE.findall(text):
        terms.add(normalize_ru(word))

    return terms


def load_entries(jsonl_path: Path) -> list[dict[str, Any]]:
    entries = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no}: {exc}") from exc
    return entries


def read_legacy_rows(db_path: Path) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    if not db_path.exists():
        return [], []

    try:
        conn = sqlite3.connect(db_path)
        avar_rows = conn.execute(
            "SELECT word, translation FROM avar_rus WHERE word IS NOT NULL"
        ).fetchall()
        rus_rows = conn.execute(
            "SELECT word, translation FROM rus_avar WHERE word IS NOT NULL"
        ).fetchall()
        conn.close()
        return avar_rows, rus_rows
    except sqlite3.Error:
        return [], []


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE entries (
            id INTEGER PRIMARY KEY,
            headword TEXT NOT NULL,
            headword_norm TEXT NOT NULL,
            homonym TEXT,
            stress INTEGER,
            stem TEXT,
            entry_json TEXT NOT NULL
        );

        CREATE TABLE forms (
            form TEXT NOT NULL,
            form_norm TEXT NOT NULL,
            entry_id INTEGER NOT NULL REFERENCES entries(id),
            is_headword INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'forms'
        );

        CREATE TABLE senses (
            entry_id INTEGER NOT NULL REFERENCES entries(id),
            sense_idx INTEGER NOT NULL,
            ru_text TEXT,
            comment TEXT,
            labels_json TEXT,
            extra_json TEXT,
            PRIMARY KEY (entry_id, sense_idx)
        );

        CREATE TABLE examples (
            entry_id INTEGER NOT NULL REFERENCES entries(id),
            sense_idx INTEGER NOT NULL,
            example_idx INTEGER NOT NULL,
            av TEXT,
            ru TEXT,
            comment TEXT,
            labels_json TEXT,
            PRIMARY KEY (entry_id, sense_idx, example_idx)
        );

        CREATE TABLE see_also (
            entry_id INTEGER NOT NULL REFERENCES entries(id),
            target TEXT NOT NULL,
            target_norm TEXT NOT NULL,
            kind TEXT,
            link_helper TEXT
        );

        CREATE TABLE ru_index (
            ru_term TEXT NOT NULL,
            ru_term_norm TEXT NOT NULL,
            entry_id INTEGER NOT NULL REFERENCES entries(id),
            av_headword TEXT NOT NULL,
            source TEXT NOT NULL,
            sense_idx INTEGER,
            example_idx INTEGER
        );

        CREATE TABLE legacy_avar (
            word TEXT NOT NULL,
            word_norm TEXT NOT NULL,
            translation TEXT NOT NULL
        );

        CREATE TABLE legacy_rus (
            word TEXT NOT NULL,
            word_norm TEXT NOT NULL,
            translation TEXT NOT NULL
        );

        CREATE INDEX idx_entries_headword_norm ON entries(headword_norm);
        CREATE INDEX idx_forms_norm ON forms(form_norm);
        CREATE INDEX idx_senses_ru_text ON senses(ru_text);
        CREATE INDEX idx_examples_av ON examples(av);
        CREATE INDEX idx_examples_ru ON examples(ru);
        CREATE INDEX idx_see_also_target_norm ON see_also(target_norm);
        CREATE INDEX idx_ru_index_norm ON ru_index(ru_term_norm);
        CREATE INDEX idx_legacy_avar_norm ON legacy_avar(word_norm);
        CREATE INDEX idx_legacy_rus_norm ON legacy_rus(word_norm);

        CREATE VIEW avar_rus AS
        SELECT e.headword AS word, group_concat(s.ru_text, '; ') AS translation
        FROM entries e
        JOIN senses s ON s.entry_id = e.id
        WHERE s.ru_text IS NOT NULL AND s.ru_text <> ''
        GROUP BY e.id
        UNION ALL
        SELECT word, translation FROM legacy_avar;

        CREATE VIEW rus_avar AS
        SELECT ru_term AS word, group_concat(DISTINCT av_headword) AS translation
        FROM ru_index
        WHERE source = 'sense'
        GROUP BY ru_term_norm
        UNION ALL
        SELECT word, translation FROM legacy_rus;
        """
    )


def insert_entries(conn: sqlite3.Connection, entries: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    jsonl_avar_keys: set[str] = set()
    jsonl_ru_keys: set[str] = set()

    for entry_id, entry in enumerate(entries, 1):
        headword = entry["word"]
        headword_norm = normalize_avar(headword)
        jsonl_avar_keys.add(headword_norm)

        conn.execute(
            """
            INSERT INTO entries
                (id, headword, headword_norm, homonym, stress, stem, entry_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                headword,
                headword_norm,
                str(entry.get("homonym")) if entry.get("homonym") is not None else None,
                entry.get("stress"),
                entry.get("stem"),
                json.dumps(entry, ensure_ascii=False, sort_keys=True),
            ),
        )

        forms = list(dict.fromkeys([headword, *entry.get("forms", [])]))
        gender_forms = entry.get("gender_forms", [])
        for form in forms:
            form_norm = normalize_avar(form)
            jsonl_avar_keys.add(form_norm)
            conn.execute(
                """
                INSERT INTO forms (form, form_norm, entry_id, is_headword, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                (form, form_norm, entry_id, int(form == headword), "forms"),
            )
        for form in gender_forms:
            form_norm = normalize_avar(form)
            jsonl_avar_keys.add(form_norm)
            conn.execute(
                """
                INSERT INTO forms (form, form_norm, entry_id, is_headword, source)
                VALUES (?, ?, ?, 0, 'gender_forms')
                """,
                (form, form_norm, entry_id),
            )

        for sense_idx, sense in enumerate(entry.get("senses", []), 1):
            labels = sense.get("labels")
            extra = {
                key: value
                for key, value in sense.items()
                if key not in {"text", "comment", "labels", "examples"}
            }
            conn.execute(
                """
                INSERT INTO senses
                    (entry_id, sense_idx, ru_text, comment, labels_json, extra_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    sense_idx,
                    sense.get("text"),
                    sense.get("comment"),
                    json.dumps(labels, ensure_ascii=False) if labels else None,
                    json.dumps(extra, ensure_ascii=False, sort_keys=True) if extra else None,
                ),
            )

            if sense.get("text"):
                for term in extract_ru_terms(sense["text"]):
                    jsonl_ru_keys.add(normalize_ru(term))
                    conn.execute(
                        """
                        INSERT INTO ru_index
                            (ru_term, ru_term_norm, entry_id, av_headword, source, sense_idx)
                        VALUES (?, ?, ?, ?, 'sense', ?)
                        """,
                        (term, normalize_ru(term), entry_id, headword, sense_idx),
                    )

            for example_idx, example in enumerate(sense.get("examples", []), 1):
                ex_labels = example.get("labels")
                conn.execute(
                    """
                    INSERT INTO examples
                        (entry_id, sense_idx, example_idx, av, ru, comment, labels_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry_id,
                        sense_idx,
                        example_idx,
                        example.get("av"),
                        example.get("ru"),
                        example.get("comment"),
                        json.dumps(ex_labels, ensure_ascii=False) if ex_labels else None,
                    ),
                )
                if example.get("ru"):
                    for term in extract_ru_terms(example["ru"]):
                        jsonl_ru_keys.add(normalize_ru(term))
                        conn.execute(
                            """
                            INSERT INTO ru_index
                                (
                                    ru_term, ru_term_norm, entry_id, av_headword,
                                    source, sense_idx, example_idx
                                )
                            VALUES (?, ?, ?, ?, 'example', ?, ?)
                            """,
                            (term, normalize_ru(term), entry_id, headword, sense_idx, example_idx),
                        )

        for ref in entry.get("see_also", []):
            target = ref.get("target")
            if not target:
                continue
            conn.execute(
                """
                INSERT INTO see_also (entry_id, target, target_norm, kind, link_helper)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    target,
                    normalize_avar(target),
                    ref.get("kind"),
                    ref.get("link_helper"),
                ),
            )

    return jsonl_avar_keys, jsonl_ru_keys


def insert_legacy(
    conn: sqlite3.Connection,
    legacy_avar: list[tuple[str, str]],
    legacy_rus: list[tuple[str, str]],
    jsonl_avar_keys: set[str],
    jsonl_ru_keys: set[str],
) -> tuple[int, int]:
    avar_count = 0
    rus_count = 0

    seen_avar: set[tuple[str, str]] = set()
    for word, translation in legacy_avar:
        word_norm = normalize_avar(word)
        key = (word_norm, translation)
        if word_norm in jsonl_avar_keys or key in seen_avar:
            continue
        seen_avar.add(key)
        conn.execute(
            "INSERT INTO legacy_avar (word, word_norm, translation) VALUES (?, ?, ?)",
            (word, word_norm, translation),
        )
        avar_count += 1

    seen_rus: set[tuple[str, str]] = set()
    for word, translation in legacy_rus:
        word_norm = normalize_ru(word)
        key = (word_norm, translation)
        if word_norm in jsonl_ru_keys or key in seen_rus:
            continue
        seen_rus.add(key)
        conn.execute(
            "INSERT INTO legacy_rus (word, word_norm, translation) VALUES (?, ?, ?)",
            (word, word_norm, translation),
        )
        rus_count += 1

    return avar_count, rus_count


def write_markdown(entries: list[dict[str, Any]], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as out:
        out.write("# Avar-Russian Dictionary\n\n")
        out.write("> Generated from `av-ru.dictionary.jsonl` by `build_dictionary.py`.\n\n")
        out.write(
            "> Source data: "
            "[avar-me/sources](https://github.com/avar-me/sources), "
            "`data/av-ru.jsonl`.\n\n"
        )
        out.write("---\n\n")

        for entry in entries:
            out.write(f"## {entry['word']}\n\n")

            meta = []
            if entry.get("forms"):
                meta.append("Forms: " + ", ".join(entry["forms"]))
            if entry.get("gender_forms"):
                meta.append("Gender forms: " + ", ".join(entry["gender_forms"]))
            if entry.get("stem"):
                meta.append(f"Stem: {entry['stem']}")
            if entry.get("stress") is not None:
                meta.append(f"Stress: {entry['stress']}")
            if entry.get("labels"):
                meta.append("Labels: " + ", ".join(entry["labels"]))
            if meta:
                out.write("**" + " | ".join(meta) + "**\n\n")

            for sense in entry.get("senses", []):
                text = sense.get("text")
                labels = sense.get("labels")
                comment = sense.get("comment")
                if text:
                    out.write(f"### {text}\n\n")
                elif labels:
                    out.write("### " + ", ".join(labels) + "\n\n")
                if labels and text:
                    out.write("_" + ", ".join(labels) + "_\n\n")
                if comment:
                    out.write(f"Comment: {comment}\n\n")

                for example in sense.get("examples", []):
                    av = example.get("av")
                    ru = example.get("ru")
                    if av and ru:
                        out.write(f"- {av} — {ru}\n")
                    elif av:
                        out.write(f"- {av}\n")
                    elif ru:
                        out.write(f"- {ru}\n")
                if sense.get("examples"):
                    out.write("\n")

            if entry.get("see_also"):
                refs = []
                for ref in entry["see_also"]:
                    target = ref.get("target")
                    kind = ref.get("kind")
                    if target:
                        refs.append(f"{kind}: {target}" if kind else target)
                if refs:
                    out.write("See also: " + "; ".join(refs) + "\n\n")


def build(jsonl_path: Path, db_path: Path, markdown_path: Path) -> dict[str, int]:
    entries = load_entries(jsonl_path)
    legacy_avar, legacy_rus = read_legacy_rows(db_path)

    tmp_db_path = db_path.with_suffix(db_path.suffix + ".tmp")
    if tmp_db_path.exists():
        tmp_db_path.unlink()

    conn = sqlite3.connect(tmp_db_path)
    create_schema(conn)
    jsonl_avar_keys, jsonl_ru_keys = insert_entries(conn, entries)
    legacy_avar_count, legacy_rus_count = insert_legacy(
        conn, legacy_avar, legacy_rus, jsonl_avar_keys, jsonl_ru_keys
    )

    stats = {
        "entries": len(entries),
        "forms": conn.execute("SELECT COUNT(*) FROM forms").fetchone()[0],
        "senses": conn.execute("SELECT COUNT(*) FROM senses").fetchone()[0],
        "examples": conn.execute("SELECT COUNT(*) FROM examples").fetchone()[0],
        "ru_index": conn.execute("SELECT COUNT(*) FROM ru_index").fetchone()[0],
        "legacy_avar": legacy_avar_count,
        "legacy_rus": legacy_rus_count,
    }
    for key, value in stats.items():
        conn.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            (key, str(value)),
        )
    conn.commit()
    conn.execute("VACUUM")
    conn.close()

    tmp_db_path.replace(db_path)
    write_markdown(entries, markdown_path)
    return stats


def parse_args() -> argparse.Namespace:
    base = Path(__file__).parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=base / "docs" / "av-ru.dictionary.jsonl",
        help="Path to canonical Avar-Russian dictionary JSONL",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=base / "avar.db",
        help="SQLite DB to generate",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=base / "docs" / "avar_dictionary.md",
        help="Markdown dictionary export for semantic search",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = build(args.jsonl, args.db, args.markdown)
    print(f"Built {args.db}")
    print(f"Wrote {args.markdown}")
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
