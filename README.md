# read-daily

A daily-reading ebook built from the Harvard Classics **"Fifteen Minutes a Day"** reading guide
([mensetmanus.net](https://www.mensetmanus.net/inspiration/fifteen_minutes_a_day/january.shtml)).
Each chapter is one calendar day. The day's recommended reading is pulled as clean text from
bartleby.com (with a 2006 Wayback Machine fallback for pages now dead on the live site), prefaced
by the guide's short context note in *italics*.

## Output

**`Harvard Classics - January.epub`** — the ebook (31 chapters). Send-to-Kindle accepts EPUB directly.

## How it works (`scrape/`)

| script | role |
|--------|------|
| `parse_guide.py` | parse the month's guide page → per-day records (title, preface, page range, source URLs) → `january_parsed.json` |
| `fetcher.py`     | fetch + cache live bartleby pages (`cache/`); extract clean text, page markers, nav links |
| `legacy.py`      | Wayback (2006) fallback for pages dead on live bartleby (`cache_wb/`) |
| `assemble.py`    | build each day's text: exact page-trim where page markers exist, else stitch forward to the guide's length; handles multi-part and poem readings |
| `build_epub.py`  | emit semantic HTML (one `<h1>` chapter per day) for pandoc |

Source guide HTML is kept in `scrape/source/`; fetched pages are cached, so rebuilds need no network
unless you clear the caches.

## Rebuild

Requires [pandoc](https://pandoc.org) (`brew install pandoc`).

```bash
cd scrape
python3 build_epub.py                       # all days -> epub_build/book.html (+ epub.css)
cd ..
pandoc scrape/epub_build/book.html -o "Harvard Classics - January.epub" \
  --metadata title="Harvard Classics — January" \
  --metadata author="Charles W. Eliot (ed.) — Fifteen Minutes a Day" \
  --metadata lang=en --toc --toc-depth=2 --split-level=1 \
  --css=scrape/epub_build/epub.css
```

A different month: scrape its guide page to `scrape/source/`, re-run `parse_guide.py`, then rebuild.

## Status

- ✅ January (31 days)
- ⏳ Other months — same pipeline, different source page
- ⏳ Poems as each day's second sub-chapter (not yet added)
- ℹ️ A few prose days run longer than the guide's page range: those volumes have no embedded page
  markers, so the natural bartleby block is kept rather than trimmed.
