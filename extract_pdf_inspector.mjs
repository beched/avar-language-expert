#!/usr/bin/env node
/**
 * Extract text from born-digital PDFs to Markdown using firecrawl/pdf-inspector.
 *
 * Unlike extract_pdfs.py (pdfplumber), this is layout-aware: it reads
 * multi-column pages in column order instead of interleaving them line by line,
 * and it resolves font glyph maps instead of emitting `(cid:NNN)` placeholders.
 * That matters for `Russian Avar Dictionary.pdf`, which is two-column.
 *
 * It does NOT do OCR. Scanned PDFs (e.g. `Avar Language Guide.pdf`) still need
 * extract_ocr.py / tesseract.
 *
 * Usage:
 *     npm install @firecrawl/pdf-inspector
 *     node extract_pdf_inspector.mjs
 *     node extract_pdf_inspector.mjs --classify        # just report PDF types
 */

import { readFileSync, writeFileSync } from 'node:fs';
import { classifyPdf, extractPagesMarkdown } from '@firecrawl/pdf-inspector';

// [source_name, output_name, description]
// Only PDFs where pdf-inspector beats the existing extraction are listed here.
// `Modern Avar Language.pdf` and `avar-language-grammar.pdf` are deliberately
// absent -- see notes.md; pdf-inspector regresses on both.
const PDFS = [
  ['Russian Avar Dictionary.pdf', 'russian_avar_dictionary.md',
   'Comprehensive Russian-Avar dictionary'],
];

// Every PDF in sources/, for --classify.
const ALL = [
  'Avar Language Guide.pdf',
  'Modern Avar Language.pdf',
  'Russian Avar Dictionary.pdf',
  'avar-language-grammar.pdf',
  'avarskiy-sokolenok-1-2024.pdf',
];

function classify() {
  for (const name of ALL) {
    const c = classifyPdf(readFileSync(`sources/${name}`));
    console.log(
      `${name.padEnd(32)} ${String(c.pdfType).padEnd(10)} ` +
      `${c.pageCount} pages, ${(c.pagesNeedingOcr ?? []).length} need OCR`,
    );
  }
}

function extract(source, output, description) {
  const path = `sources/${source}`;
  const res = extractPagesMarkdown(readFileSync(path));

  const out = [
    `# ${source.replace(/\.pdf$/, '')}`,
    '',
    `> ${description}`,
    '',
    `*Source: ${source} (extracted with firecrawl/pdf-inspector)*`,
    '',
    '---',
    '',
  ];

  let extracted = 0;
  for (const page of res.pages) {
    const md = page.markdown.trim();
    if (!md) continue;
    // page.page is 0-indexed; docs/ use 1-based page headings.
    out.push(`## Page ${page.page + 1}`, '', md, '');
    extracted += 1;
  }

  writeFileSync(`docs/${output}`, out.join('\n'));
  const ocr = res.pagesNeedingOcr ?? [];
  console.log(
    `  ${source} -> docs/${output}: ${extracted}/${res.pages.length} pages` +
    (ocr.length ? `, ${ocr.length} image-only page(s) skipped by OCR` : ''),
  );
  return extracted;
}

if (process.argv.includes('--classify')) {
  classify();
} else {
  console.log('Extracting PDFs with pdf-inspector...');
  let total = 0;
  for (const [source, output, description] of PDFS) {
    total += extract(source, output, description);
  }
  console.log(`Done. ${total} pages extracted.`);
}
