#!/usr/bin/env python3
"""Emit semantic HTML for selected days (one <h1> chapter each) for pandoc -> EPUB.

Usage: python3 build_epub.py 1 3 7 12 31   ->  writes epub_build/book.html + epub.css
"""
import json, re, sys, html as H
from pathlib import Path
import assemble

HERE = Path(__file__).parent
OUT = HERE / 'epub_build'
OUT.mkdir(exist_ok=True)
MONTH = 'January'

# Claude-written, Wikipedia-checked author/work blurbs (trusted HTML; may use <em>).
BG_PATH = HERE / 'background.json'
BG = json.load(open(BG_PATH, encoding='utf-8')) if BG_PATH.exists() else {}

# Curated citation fields per day: {author, work, written}. Vol/pages come from the guide.
SRC_PATH = HERE / 'sources.json'
SRC = json.load(open(SRC_PATH, encoding='utf-8')) if SRC_PATH.exists() else {}


def vol_of(read_line):
    m = re.search(r'Vol\.?\s*(\d+)', read_line)
    return m.group(1) if m else '?'


def range_str(ranges):
    return ', '.join(f'{a}–{b}' for a, b in ranges) if ranges else '?'


def preface_groups(preamble):
    groups, cur = [], []
    for pl in preamble:
        pl = pl.strip()
        if re.match(r'^\(.*\)\.?$', pl):
            if cur:
                groups.append(' '.join(cur)); cur = []
            groups.append(pl)
        else:
            cur.append(pl)
    if cur:
        groups.append(' '.join(cur))
    return groups


def text_to_html(text):
    """Clean reading text -> <p> blocks. A blank line separates blocks; a single
    newline inside a block (e.g. the virtue list) becomes <br/>."""
    out = []
    for block in re.split(r'\n{2,}', text.strip()):
        block = block.strip()
        if not block:
            continue
        esc = H.escape(block).replace('\n', '<br/>\n')
        out.append(f'<p>{esc}</p>')
    return '\n'.join(out)


def day_html(day):
    n, title = day['day'], day['title']
    text, sources, note = assemble.assemble_day(day)
    vol, pages = vol_of(day['read_line']), range_str(day['page_ranges'])
    parts = [f'<h1>{MONTH} {n} — {H.escape(title)}</h1>']
    # citation line under the title (centered, light): author · work (year) / HC vol & pages
    cite = SRC.get(str(n))
    if cite:
        yr = f' ({H.escape(cite["written"])})' if cite.get('written') else ''
        work = f'<em>{H.escape(cite["work"])}</em>'
        author = cite.get('author', '')
        byline = f'{H.escape(author)} · {work}' if author else work
        parts.append(f'<div class="cite"><p>{byline}{yr}</p></div>')
    # author/work headnote (roman, labeled) — distinct from the compiler's italic note.
    # blurb is trusted authored HTML, inserted raw so <em> work-titles survive.
    blurb = BG.get(str(n))
    if blurb:
        parts.append(f'<div class="headnote"><p><span class="hn-label">Background</span> — {blurb}</p></div>')
    # preface in a div (pandoc keeps div classes) AND <em> (guarantees italics)
    parts.append('<div class="preface">')
    for g in preface_groups(day['preamble']):
        parts.append(f'<p><em>{H.escape(g)}</em></p>')
    parts.append('</div>')
    parts.append('<hr/>')
    parts.append(text_to_html(text))
    # bottom: the Harvard Classics volume + page range
    bottom = f'— The Harvard Classics, Vol. {vol}, pp. {pages}'
    parts.append(f'<div class="source"><p><em>{H.escape(bottom)}</em></p></div>')
    return '\n'.join(parts), {'day': n, 'title': title, 'words': len(text.split()),
                              'sources': sources, 'note': note}


CSS = """\
body { line-height: 1.5; margin: 0 1em; }
h1 { page-break-before: always; text-align: center; font-size: 1.5em;
     margin: 1.5em 0 1em; line-height: 1.25; }
p { margin: 0; text-indent: 1.4em; }
div.cite { text-align: center; font-size: 0.8em; color: #666; margin: 0.2em 0 1.1em; }
div.cite p { text-indent: 0; margin: 0; line-height: 1.4; }
div.headnote { font-size: 0.92em; margin: 0.5em 1.2em 0.8em; }
div.headnote p { text-indent: 0; margin: 0; }
span.hn-label { font-weight: bold; font-variant: small-caps; }
div.preface p { font-style: italic; text-indent: 0; margin: 0.4em 1.2em; color: #333; }
hr { border: 0; border-top: 1px solid #999; width: 30%; margin: 1.2em auto; }
div.source p { text-indent: 0; font-style: italic; font-size: 0.85em;
               color: #555; margin-top: 1.6em; text-align: right; }
/* first paragraph after the rule: no indent (book style) */
hr + p { text-indent: 0; }
"""


def main():
    days_all = {d['day']: d for d in json.load(open(HERE / 'january_parsed.json'))}
    want = [int(x) for x in sys.argv[1:]] or sorted(days_all)
    body, metas = [], []
    for n in want:
        h, m = day_html(days_all[n])
        body.append(h); metas.append(m)
    doc = ('<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
           '<title>Fifteen Minutes a Day</title></head><body>\n'
           + '\n'.join(body) + '\n</body></html>\n')
    (OUT / 'book.html').write_text(doc, encoding='utf-8')
    (OUT / 'epub.css').write_text(CSS, encoding='utf-8')
    print('days:', want)
    for m in metas:
        print(f"  day {m['day']:>2}  {m['words']:>5}w  {len(m['sources'])} src  {m['title'][:40]}")
    print('wrote', OUT / 'book.html')


if __name__ == '__main__':
    main()
