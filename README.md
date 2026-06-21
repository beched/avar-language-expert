# Avar Language Corpus

A curated corpus for studying **Avar** (Авар мацӀ, ISO `av`) — a Northeast Caucasian language of Dagestan — optimized for semantic search, grammar Q&A, and dictionary lookups with an AI assistant (Cursor / Claude / etc.).

> For agent-specific conventions (indexing, search quirks, the palochka character chaos), see [`AGENTS.md`](AGENTS.md).
> For hand-curated grammar observations, see [`notes.md`](notes.md).

## What's here

| Kind | Size | Source |
|------|------|--------|
| Reference grammars (RU) | ~670 KB MD | Мадиева 1967, Алексеев 1999, full grammar book |
| Wikipedia dump (AV) | 7.4 MB | 3,711 articles, including ~25 grammar/linguistics articles **written in Avar** |
| Telegram channels | ~180K lines | `hakikat` (newspaper 2021–2026), `hitinal_avaraze`, `avar_mats`, `ob_avarskom` |
| Children's magazine | 59 KB | Аваристан Сокъолен 2024 |
| Dictionary | 22,842 entries / 36,845 examples | `docs/av-ru.dictionary.jsonl` from [`avar-me/sources`](https://github.com/avar-me/sources); `avar.db` + `docs/avar_dictionary.md` generated lookups |
| PDFs (OCR, noisy) | reference-only | Modern Avar Language, Avar Language Guide |

See [`AGENTS.md`](AGENTS.md#data-quality) for the full quality matrix.

## Quick start

### Ask questions with Cursor
Open this folder in Cursor. The `docs/` folder is indexed — ask things like:
- *"How does the ergative case work in Avar?"*
- *"What are the 24 cases listed in Avar Wikipedia's grammar overview?"*
- *"Show me conditional constructions from the hakikat corpus."*

### Look up words
```bash
sqlite3 avar.db "SELECT word, translation FROM avar_rus WHERE word = 'абизе';"
sqlite3 avar.db "SELECT word, translation FROM rus_avar WHERE word = 'говорить';"
sqlite3 avar.db "SELECT e.headword, f.form, s.ru_text FROM forms f JOIN entries e ON e.id = f.entry_id LEFT JOIN senses s ON s.entry_id = e.id AND s.sense_idx = 1 WHERE f.form_norm = 'абула';"
```

For readable entries with examples, search `docs/avar_dictionary.md`. For structured processing, use `docs/av-ru.dictionary.jsonl`; `avar.db` is generated from it. The JSONL source is [`avar-me/sources`](https://github.com/avar-me/sources), specifically `data/av-ru.jsonl`.

### Grep the corpus (mind the palochka)
Avar's palochka `Ӏ` is encoded as **9 different characters** across sources (`Ӏ ӏ І і I l 1 | !`). Always use a character class:
```bash
rg "к[Ӏӏ1IlІі|!]алъай" docs/
```

## Re-extracting from sources

```bash
python build_dictionary.py    # dictionary JSONL → SQLite + searchable MD
python extract_html.py        # clean HTML grammars → MD
python extract_telegram.py    # Telegram HTML exports → MD
python extract_wiki.py        # Wikipedia XML → MD (needs mwparserfromhell)
python extract_pdfs.py        # text-layer PDFs (needs pdfplumber)
python extract_sokolenok.py   # 2-column children's magazine
python extract_ocr.py         # scanned PDFs (needs tesseract, pdf2image, pytesseract)
```

Dependencies are intentionally not pinned in a `requirements.txt` — install as needed:
```bash
pip install mwparserfromhell pdfplumber pdf2image pytesseract
```

## Layout

```
auto/
├── docs/       # extracted Markdown (indexed by Cursor)
├── sources/    # original HTML / PDF / XML
├── avar.db     # generated SQLite dictionary index
├── build_dictionary.py
├── notes.md    # curated grammar notes
├── AGENTS.md   # conventions for AI agents
└── extract_*.py
```

## License / provenance

All extracted texts derive from third-party sources (Wikipedia CC BY-SA, published grammars, public Telegram channels, printed dictionaries). The structured Avar-Russian dictionary JSONL comes from [`avar-me/sources`](https://github.com/avar-me/sources).
