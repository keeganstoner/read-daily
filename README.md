# read-daily

A daily-reading ebook built from the Harvard Classics **"Fifteen Minutes a Day"** reading guide
([mensetmanus.net](https://www.mensetmanus.net/inspiration/fifteen_minutes_a_day/january.shtml)).
Each chapter is one calendar day, laid out as:

1. **Citation** — a centered, light byline under the title: *author · work (year written)*.
2. **Background headnote** — a short author/work orientation (era, place, what they're known for,
   and what the document is) in upright roman with a small-caps **Background** label. It sets up the
   reading without giving away its argument or message.
3. **Compiler's note** — the guide's original one-line context, in *italics*.
4. **The reading** — the day's recommended text, pulled as clean prose from bartleby.com (with a
   2006 Wayback Machine fallback for pages now dead on the live site). A footer gives the
   Harvard Classics volume and page range.

## Output

**`Harvard Classics - January.epub`** — the ebook (31 chapters). Send-to-Kindle accepts EPUB directly.

## How it works (`scrape/`)

| script | role |
|--------|------|
| `parse_guide.py` | parse the month's guide page → per-day records (title, preface, page range, source URLs) → `january_parsed.json` |
| `fetcher.py`     | fetch + cache live bartleby pages (`cache/`); extract clean text, page markers, nav links |
| `legacy.py`      | Wayback (2006) fallback for pages dead on live bartleby (`cache_wb/`) |
| `assemble.py`    | build each day's text: exact page-trim where page markers exist, else stitch forward to the guide's length; handles multi-part and poem readings |
| `build_epub.py`  | emit semantic HTML (one `<h1>` chapter per day) for pandoc, injecting the citation line + background headnote + styling |

Two editable data files drive the editorial apparatus (both Claude-written, Wikipedia-checked):
`background.json` (per-day author/work blurbs; work titles use `<em>`) and `sources.json`
(per-day `{author, work, written}` for the citation line — leave `author` empty for anonymous
works; volume/pages come from the guide). Source guide HTML is kept in `scrape/source/`; fetched
pages are cached, so rebuilds need no network unless you clear the caches.

## Rebuild

Requires [pandoc](https://pandoc.org) (`brew install pandoc`).

```bash
cd scrape
python3 build_epub.py                       # all days -> epub_build/{book.html, epub.css, metadata.yaml}
cd ..
pandoc scrape/epub_build/book.html -o "Harvard Classics - January.epub" \
  --metadata-file=scrape/epub_build/metadata.yaml \
  --toc --toc-depth=2 --split-level=1 \
  --css=scrape/epub_build/epub.css
```

Title (`Harvard Classics <Month>`) and author (`Charles W. Eliot`) live in `build_epub.py` and are
written to `metadata.yaml`, so they stay consistent and update with the month automatically.

A different month: scrape its guide page to `scrape/source/`, re-run `parse_guide.py`, then rebuild.

## Status

- ✅ January (31 days), each with a background headnote
- ⏳ Other months — same pipeline, different source page (+ a `background.json` for that month)
- ⏳ Poems as each day's second sub-chapter (not yet added)
- ℹ️ A few prose days run longer than the guide's page range: those volumes have no embedded page
  markers, so the natural bartleby block is kept rather than trimmed.
