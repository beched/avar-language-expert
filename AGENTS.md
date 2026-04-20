# Avar Language Materials

This directory contains materials about the Avar (Avaric) language, structured for semantic search and Q&A with Cursor.

## Directory Structure

```
/auto/
├── docs/                           # ← Cursor indexes these (ask questions here)
│   ├── avar_grammar_1967.md        # ★ PRIMARY: Clean grammar (Мадиева, 76 KB)
│   ├── avar_grammar_1999.md        # ★ PRIMARY: Clean grammar (Алексеев, 76 KB)
│   ├── avar_grammar_book.md        # ★ PRIMARY: Full grammar book (516 KB)
│   ├── avar_wikipedia.md           # Real Avar text (7.4 MB, 3,711 articles)
│   ├── ob_avarskom.md              # Educational channel (2024)
│   ├── hakikat.md                  # Newspaper corpus (2021-2026)
│   ├── hitinal_avaraze.md          # Language channel corpus (2022-2025)
│   ├── avar_mats.md                # Language lessons channel (2021-2026)
│   ├── avarskiy_sokolenok_2024.md  # Children's magazine (2024, 59 KB)
│   ├── modern_avar_language.md     # ⚠ PDF extraction, has OCR errors
│   ├── avar_language_guide.md      # ⚠ OCR extraction, noisy
│   └── russian_avar_dictionary.md  # ⚠ PDF extraction, formatting issues
│
├── sources/                        # Original files
│   ├── avar-language.html          # Clean HTML (1967 grammar)
│   ├── avar-language-2.html        # Clean HTML (1999 grammar)
│   ├── avar-language-grammar.pdf   # Full grammar book (clean text from p.23)
│   ├── Modern Avar Language.pdf
│   ├── Avar Language Guide.pdf     # Scanned, requires OCR
│   ├── Russian Avar Dictionary.pdf
│   ├── avarskiy-sokolenok-1-2024.pdf  # Children's magazine (2-column layout)
│   └── avwiki-*.xml                # Avar Wikipedia dump
│
├── avar.db                         # SQLite dictionary (~37K entries)
├── notes.md                        # ★ Grammar notes (non-obvious patterns)
├── extract_html.py                 # HTML → Markdown converter
├── extract_telegram.py             # Telegram exports → clean text
├── extract_pdfs.py                 # PDF text extraction
├── extract_sokolenok.py            # 2-column PDF extraction (magazine)
├── extract_ocr.py                  # OCR for scanned PDFs
├── extract_wiki.py                 # Wikipedia XML extraction
└── AGENTS.md                       # This file
```

## Data Quality

| File | Quality | Lines | Use For |
|------|---------|-------|---------|
| `avar_grammar_1967.md` | ★★★ Excellent | 968 | Grammar rules, phonetics, morphology |
| `avar_grammar_1999.md` | ★★★ Excellent | 822 | Modern grammar description |
| `avar_grammar_book.md` | ★★★ Excellent | 4,455 | Full grammar book (516 KB) |
| `ob_avarskom.md` | ★★★ Excellent | 6,409 | Educational materials, examples (2024) |
| `hakikat.md` | ★★★ Excellent | 103,088 | Modern Avar corpus (newspaper, 2021-2026) |
| `hitinal_avaraze.md` | ★★★ Excellent | 9,080 | Modern Avar corpus (2022-2025) |
| `avar_mats.md` | ★★★ Excellent | 66,189 | Language lessons, vocabulary, grammar (2021-2026) |
| `avarskiy_sokolenok_2024.md` | ★★★ Excellent | 1,162 | Children's magazine, real Avar prose/poetry (2024) |
| `avar_wikipedia.md` | ★★☆ Good | 100,888 | Real-world Avar text examples |
| `russian_avar_dictionary.md` | ★★☆ Good | 61,694 | Word lookups |
| `avar_language_guide.md` | ★☆☆ Poor | 9,038 | Reference only (OCR noise) |
| `modern_avar_language.md` | ★☆☆ Poor | 17,706 | Reference only (OCR artifacts) |
| `notes.md` | ★★★ Curated | — | Non-obvious grammar patterns, examples |

**Recommendation:** 
- **Grammar**: Use the three grammar sources (1967, 1999, book) + `ob_avarskom.md`
- **Grammar in Avar**: The Wikipedia dump contains ~22 grammar/linguistics articles **written in Avar itself** (see section below) — invaluable for native terminology, examples, and metalinguistic descriptions
- **Non-obvious patterns**: Check `notes.md` first for curated insights on tricky constructions
- **Real usage examples**: Search `hakikat.md` (103K lines, ~24K posts from 2021-2026), `hitinal_avaraze.md` (9K lines, 2022-2025), or `avarskiy_sokolenok_2024.md` (children's magazine, prose & poetry)
- **Educational content**: `ob_avarskom.md` and `avar_mats.md` have lessons, explanations, vocabulary with translations

## Wikipedia Grammar Articles (in Avar)

The file `avar_wikipedia.md` contains a cluster of linguistics/grammar articles from Avar Wikipedia, all **written in Avar**. These are unique — the grammar books are all in Russian, but these articles describe Avar grammar using Avar metalinguistic terminology. Especially valuable for understanding how native speakers conceptualize their own language.

### Категория:Авар грамматика (Avar Grammar category)

| Article | Line | Topic |
|---------|------|-------|
| `## Авар грамматика` | 86250 | ★ **Comprehensive grammar overview**: nouns, cases (24 cases!), adjectives, numerals, pronouns, verbs, adverbs, conjunctions, particles, postpositions, interjections — all in one article |
| `## Авар цӀар` | 86671 | Nouns (цӀар) |
| `## Авар гӀемерлъул форма` | 88234 | Plural formation |
| `## Авар вербал` | 86177 | Verbs |
| `## Авар адйективал` | 86149 | Adjectives |
| `## Авар цӀарубакӀал` | 86065 | Pronouns |
| `## Авар рикӀкӀен` | 85984 | Numerals |
| `## Авар тӀадрагӀи` | 57422 | Adverbs |
| `## Авар адвербал` | 86610 | Adverbs (second article) |
| `## Авар энклитикал` | 86797 | Enclitics/particles |
| `## Авар хадурегӀел` | 86945 | Postpositions |
| `## Авар интерйекцияби` | 86653 | Interjections |
| `## Авар свералаби` | 54378 | Declension paradigms |
| `## Авар сверухълъи` | 81606 | Syntax/case relations |
| `## Авараб редупликация` | 84680 | Reduplication |

### Категория:Авар мацӀ (Avar Language category)

| Article | Line | Topic |
|---------|------|-------|
| `## Авар фонология` | 54831 | Phonology |
| `## Авар ортография` | 53245 | Orthography |
| `## Авар алфабет` | 59837 | Alphabet |
| `## Авар мацӀалъул романизация` | 85511 | Romanization |
| `## Авар мацӀалда рагӀилӀугьин` | 61296 | Word formation |
| `## Авар мацӀалъул история` | 62585 | Language history |
| `## Авар рагӀул этимология` | 85481 | Word etymology |
| `## Аваралде рачӀарал рагӀаби` | 85896 | Loanwords into Avar |
| `## Аваризмал` | 85682 | Avarisms (Avar influence on other languages) |
| `## Авар хъвавул реформа 1952` | 92923 | Writing reform of 1952 |

**Tip:** To read a specific article, use line offsets — e.g., read from line 86250 for the main grammar article. The `## Авар грамматика` article (lines 86250–86609, ~360 lines) is the single most comprehensive grammar reference in Avar.

## SQLite Dictionary (`avar.db`)

```sql
-- Avar → Russian (~17,600 entries)
SELECT word, translation FROM avar_rus WHERE word LIKE '%...%';

-- Russian → Avar (~19,500 entries)
SELECT word, translation FROM rus_avar WHERE word LIKE '%...%';
```

## Example Questions

**Grammar (uses clean HTML sources):**
- "How are noun classes structured in Avar?"
- "What are the Avar personal pronouns?"
- "Explain the ergative case in Avar"
- "What are the locative cases in Avar?"

**Real-world usage (search in corpus):**
- "Show examples of Avar sentences about geography"
- Find conditional constructions: `grep "букIарабани" docs/hakikat.md -C 2`
- Search for specific verbs: `grep "кваназе" docs/hakikat.md -C 3`

**Dictionary:**
- Use SQLite: `SELECT * FROM rus_avar WHERE word = 'дом';`

## Special Characters in Avar

Avar uses Cyrillic with additional characters:
- **Pharyngeals:** гӀ, хӀ, гъ, хъ
- **Ejectives:** кӀ, пӀ, тӀ, цӀ, чӀ
- **Laterals:** лъ, кь, тл
- **Laryngeal:** гӀ (pharyngeal voiced), лӀ

### Palochka (Ӏ) variant problem — IMPORTANT for searching

The Avar palochka character (Ӏ, U+04C0) is part of digraphs like кӀ, тӀ, цӀ, хӀ, гӀ, лӀ, пӀ, чӀ. However, across our corpus **9 different characters** are used inconsistently to represent it:

| Character | Unicode | Dominant in |
|-----------|---------|-------------|
| Ӏ | U+04C0 (uppercase palochka) | `avar_wikipedia.md`, `avar_mats.md` |
| ӏ | U+04CF (lowercase palochka) | `ob_avarskom.md` |
| І | U+0406 (Ukrainian I) | `avar_wikipedia.md`, `avar_mats.md` |
| I | U+0049 (Latin I) | `hakikat.md`, `avar_grammar_*.md` |
| l | U+006C (Latin lowercase L) | `hakikat.md`, `hitinal_avaraze.md` |
| 1 | U+0031 (digit 1) | `hakikat.md`, `avar_mats.md` |
| \| | U+007C (pipe) | scattered |
| ! | U+0021 (exclamation mark) | `hakikat.md` |
| і | U+0456 (Ukrainian lowercase i) | rare |

**When searching for a word containing palochka** (e.g. кӀалъай, тӀад, цӀар, хӀалтӀизе, гӀумру), you MUST search with **multiple variants** or use a regex character class. A single-variant grep will miss most occurrences.

**Recommended search pattern:** Replace each Ӏ in the search term with a character class `[Ӏӏ1IlІі|!]`. For example, to search for кӀалъай:

```bash
rg "к[Ӏӏ1IlІі|!]алъай" docs/
```

For programmatic/SQL searches in `avar.db`, the dictionary uses a consistent encoding, so exact match works there.

## Re-extracting

```bash
# Grammar articles (HTML → Markdown, best quality)
python extract_html.py

# Telegram channels (HTML → clean text)
python extract_telegram.py

# Wikipedia dump (XML → Markdown)
pip install mwparserfromhell && python extract_wiki.py

# PDFs (lower quality, text extraction)
pip install pdfplumber && python extract_pdfs.py

# Children's magazine (2-column PDF)
python extract_sokolenok.py

# Scanned PDFs (requires OCR with tesseract)
pip install pdf2image pytesseract && python extract_ocr.py
```
