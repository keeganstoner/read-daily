#!/usr/bin/env python3
"""Emit semantic HTML for a month (one <h1> chapter per day) for pandoc -> EPUB.

Usage:
  python3 build_epub.py                 # all days of January (default)
  python3 build_epub.py june            # all days of June
  python3 build_epub.py june 1 5 10     # only June days 1, 5, 10
Reads {month}_parsed.json, background_{month}.json, sources_{month}.json;
writes epub_build/{book.html, epub.css, metadata.yaml}.
"""
import json, re, sys, html as H
from pathlib import Path
import assemble, fetcher
import parse_guide as PG

HERE = Path(__file__).parent
OUT = HERE / 'epub_build'
OUT.mkdir(exist_ok=True)
AUTHOR = 'Charles W. Eliot'      # EPUB author (the editor); the title is per-month
FOREWORD_MAX_WORDS = 1000        # full epigraph poem if this short, else the guide's snippet


def load_json(path):
    return json.load(open(path, encoding='utf-8')) if path.exists() else {}


def vol_of(read_line):
    m = re.search(r'vol\.?\s*(\d+)', read_line, re.I)
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


def foreword_html(month):
    """The month's opening epigraph poem as an italic 'Foreword' section.
    Follows the guide's link and uses the whole poem if short; otherwise the
    snippet printed on the guide page."""
    src_file = HERE / 'source' / f'{month}.html'
    if not src_file.exists():
        return ''
    raw = src_file.read_text(encoding='latin-1')
    s = raw.find(f'<h2>{month.upper()}</h2>')
    if s < 0:
        return ''
    epi = raw[s + len(f'<h2>{month.upper()}</h2>'):raw.find('<b>', s)]
    lines = re.split(r'(?i)<br\s*/?>', epi)
    attr_idx = next((i for i, l in enumerate(lines) if 'bartleby.com' in l), len(lines) - 1)
    snippet = [t for t in (PG.strip_tags(l).strip() for l in lines[:attr_idx]) if t]
    author = PG.strip_tags(lines[attr_idx]).split('(')[0].strip().title()
    url = None
    for m in re.finditer(r'href="([^"]+)"', epi):
        u = PG.norm_url(m.group(1))
        if u and PG.is_text_page(u[len('https://www.bartleby.com'):]):
            url = u
            break
    body = snippet
    if url:
        full = fetcher.clean_text(fetcher.content_block(fetcher.fetch(url)))
        if full and len(full.split()) <= FOREWORD_MAX_WORDS:
            body = [l for l in full.split('\n') if l.strip()]
    if not body:
        return ''
    ps = '\n'.join(f'<p>{H.escape(l)}</p>' for l in body)
    attr = f'<p class="attribution">— {H.escape(author)}</p>' if author else ''
    return f'<h1>Foreword</h1>\n<div class="foreword">\n{ps}\n{attr}\n</div>'


def day_html(day, month, bg, src):
    n, title = day['day'], day['title']
    text, sources, note = assemble.assemble_day(day)
    vol, pages = vol_of(day['read_line']), range_str(day['page_ranges'])
    parts = [f'<h1>{month} {n} — {H.escape(title)}</h1>']
    # citation line under the title (centered, light): author · work (year) / HC vol & pages
    cite = src.get(str(n))
    if cite:
        yr = f' ({H.escape(cite["written"])})' if cite.get('written') else ''
        work = f'<em>{H.escape(cite["work"])}</em>'
        author = cite.get('author', '')
        byline = f'{H.escape(author)} · {work}' if author else work
        parts.append(f'<div class="cite"><p>{byline}{yr}</p></div>')
    # author/work headnote (roman, labeled) — distinct from the compiler's italic note.
    # blurb is trusted authored HTML, inserted raw so <em> work-titles survive.
    blurb = bg.get(str(n))
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
div.foreword { margin: 1.5em 1.5em; }
div.foreword p { text-align: center; font-style: italic; text-indent: 0; margin: 0.15em 0; }
div.foreword p.attribution { margin-top: 1.3em; font-size: 0.9em; }
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
    args = sys.argv[1:]
    month = 'january'
    if args and not args[0].isdigit():
        month = args.pop(0).lower()
    want_filter = [int(x) for x in args]
    disp = month.capitalize()
    title = f'Harvard Classics {disp}'

    days_all = {d['day']: d for d in json.load(open(HERE / f'{month}_parsed.json', encoding='utf-8'))}
    bg = load_json(HERE / f'background_{month}.json')
    src = load_json(HERE / f'sources_{month}.json')

    want = want_filter or sorted(days_all)
    body, metas = [], []
    for n in want:
        h, m = day_html(days_all[n], disp, bg, src)
        body.append(h); metas.append(m)
    if not want_filter:                      # full month -> open with the epigraph foreword
        fw = foreword_html(month)
        if fw:
            body.insert(0, fw)
    doc = ('<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
           f'<title>{H.escape(title)}</title></head><body>\n'
           + '\n'.join(body) + '\n</body></html>\n')
    (OUT / 'book.html').write_text(doc, encoding='utf-8')
    (OUT / 'epub.css').write_text(CSS, encoding='utf-8')
    # pandoc reads this via --metadata-file (keeps title/author out of the shell command)
    (OUT / 'metadata.yaml').write_text(
        f'title: "{title}"\nauthor: "{AUTHOR}"\nlang: en\n', encoding='utf-8')
    print(f'month: {month} | days:', want)
    for m in metas:
        print(f"  day {m['day']:>2}  {m['words']:>5}w  {len(m['sources'])} src  {m['title'][:40]}")
    print('wrote', OUT / 'book.html')


if __name__ == '__main__':
    main()
