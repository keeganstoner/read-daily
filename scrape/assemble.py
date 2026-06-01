#!/usr/bin/env python3
"""Assemble each day's reading text from bartleby, honoring the guide's page range
as closely as the source allows:
  - exact page trim where PAGE NUM markers exist (Franklin / vol 1)
  - smart forward-stitch by word budget where they don't (poems, short pieces)
  - multi-segment handling for split readings (Aesop, Burns, Dante, Thomas)
  - Wayback (2006) fallback for pages dead on the live site (Job, Burke, Pascal)
"""
import re, html as htmllib, json
from pathlib import Path
import fetcher, legacy

WPP = 220          # word-per-printed-page target for stitching (low, so prose isn't over-stitched)
MAX_STITCH = 12    # safety cap on extra Next-fetches per segment
HERE = Path(__file__).parent


def is_dead(html):
    c = re.search(r'canonical"\s*href="([^"]+)"', html)
    return (c and c.group(1).rstrip('/').endswith('/lit-hub/authors')) or \
           '<title>Authors - Collection' in html


def work_slug(html):
    c = re.search(r'canonical"\s*href="[^"]*?/lit-hub/hc/([^/"]+)/', html)
    return c.group(1) if c else None


def first_int(s):
    m = re.search(r'\d+', s)
    return int(m.group()) if m else None


def get_page(url):
    """Return dict(layout, text, markers, segs(pagenum->html), next_url, slug, title)."""
    html = fetcher.fetch(url)
    if is_dead(html):
        whtml = legacy.fetch_wb(url)
        title, text = legacy.clean_text_old(whtml)
        nxt = legacy.next_link_old(whtml)
        nxt = ('https://www.bartleby.com' + nxt) if nxt else None
        return dict(layout='legacy', text=text, markers=legacy.page_markers_old(whtml),
                    raw=whtml, next_url=nxt, slug='legacy:' + url.split('bartleby.com')[-1].rsplit('/', 1)[0],
                    title=title, url=url)
    block = fetcher.content_block(html)
    _, nxt = fetcher.nav_links(html)
    return dict(layout='modern', text=fetcher.clean_text(block), markers=fetcher.page_markers(html),
                raw=block, next_url=nxt, slug=work_slug(html), title=fetcher.title_of(html), url=url)


def split_by_markers(block_html):
    """modern content block -> ordered list of (pagenum, clean_text_chunk)."""
    parts = re.split(r'<!--\s*PAGE\s*NUM="(\d+)"\s*-->', block_html)
    out = []
    # parts[0] is pre-first-marker text (belongs to previous page); skip if blank
    for i in range(1, len(parts) - 1, 2):
        out.append((int(parts[i]), fetcher.clean_text(parts[i + 1])))
    return out


def assemble_segment(start_url, a, b, note):
    """Assemble text covering printed pages [a,b] starting from start_url."""
    p = get_page(start_url)
    sources = [start_url]

    # --- exact trim path (page markers available) ---
    if p['markers'] and p['layout'] == 'modern':
        pagemap = {}
        cur = p
        guard = 0
        # walk forward until we've seen page b (or run out)
        while True:
            for num, chunk in split_by_markers(cur['raw']):
                pagemap.setdefault(num, chunk)
            if max(pagemap) >= b or not cur['next_url'] or guard >= MAX_STITCH:
                break
            guard += 1
            nxt = get_page(cur['next_url'])
            if nxt['slug'] != p['slug'] or not nxt['markers']:
                break
            sources.append(cur['next_url']); cur = nxt
        have = sorted(k for k in pagemap if a <= k <= b)
        if have:
            text = '\n\n'.join(pagemap[k] for k in have)
            lo, hi = min(have), max(have)
            note.append(f'exact pp.{lo}-{hi} via page-markers')
            return text, sources
        # markers exist but not in range -> fall through to whole text

    # --- stitch path (no usable markers) ---
    pages = b - a + 1
    target = pages * WPP
    text = p['text']
    if len(text.split()) >= target:
        note.append(f'single block (~{len(text.split())}w ≥ target {target}w for {pages}pp)')
        return text, sources
    # under target -> stitch forward (skipping empty "heading" divider pages)
    cur = p
    extra = added = 0
    while len(text.split()) < target and cur['next_url'] and extra < MAX_STITCH:
        nxt = get_page(cur['next_url'])
        extra += 1
        if nxt['slug'] != p['slug']:        # left the work -> stop
            break
        if nxt['text'].strip():
            text += '\n\n' + nxt['text']
            sources.append(nxt['url'])
            added += 1
        cur = nxt                            # advance even through empty divider pages
    note.append(f'stitched {added} page(s) (+{extra} fetched) -> ~{len(text.split())}w (target {target}w for {pages}pp)')
    return text, sources


def merge_ranges(ranges):
    if not ranges:
        return []
    rs = sorted(ranges)
    out = [list(rs[0])]
    for a, b in rs[1:]:
        if a <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [tuple(x) for x in out]


def pick_start_url(a, urls, anchor_pages):
    """Choose the start url for a range beginning at page a."""
    cands = [(pg, u) for u, pg in zip(urls, anchor_pages) if pg is not None and pg <= a]
    if cands:
        return max(cands)[1]
    have = [(pg, u) for u, pg in zip(urls, anchor_pages) if pg is not None]
    if have:
        return min(have)[1]
    return urls[0]


def assemble_day(day):
    urls = day['reading_urls']
    anchor_pages = [first_int(t) for t in day['anchor_texts']]
    ranges = merge_ranges(day['page_ranges'])
    note = []
    segs = []
    all_sources = []
    if not ranges or not urls:
        # no parseable range: just take the first url's block
        p = get_page(urls[0])
        return p['text'], [urls[0]], ['no range; single block']
    for (a, b) in ranges:
        start = pick_start_url(a, urls, anchor_pages)
        t, srcs = assemble_segment(start, a, b, note)
        segs.append(t)
        all_sources += srcs
    text = '\n\n*          *          *\n\n'.join(segs)
    return text, all_sources, note


if __name__ == '__main__':
    import sys
    days = json.load(open(HERE / 'january_parsed.json'))
    want = set(int(x) for x in sys.argv[1:]) if len(sys.argv) > 1 else {1, 2, 3, 8, 12, 16, 20, 25, 27, 28}
    for d in days:
        if d['day'] not in want:
            continue
        text, sources, note = assemble_day(d)
        print('\n' + '=' * 78)
        print(f"DAY {d['day']}: {d['title']}  (guide {d['read_line'][-40:]})")
        print('NOTES:', ' | '.join(note))
        print('SOURCES:', len(sources), sources)
        print('WORDS:', len(text.split()))
        print('-' * 40)
        print(text[:700])
        print(' ... [TAIL] ... ')
        print(text[-300:])
