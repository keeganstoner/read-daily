#!/usr/bin/env python3
"""Fetch + cache bartleby pages, extract content, page markers, and nav links."""
import re, html as htmllib, subprocess, time, sys
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
CACHE = Path(__file__).parent / 'cache'
CACHE.mkdir(exist_ok=True)
BASE = 'https://www.bartleby.com'


def cache_path(url):
    path = url.split('bartleby.com', 1)[-1]
    slug = path.strip('/').replace('/', '_') or 'index'
    if not slug.endswith('.html'):
        slug += '.html'
    return CACHE / slug


def fetch(url, delay=0.6):
    cp = cache_path(url)
    if cp.exists() and cp.stat().st_size > 1000:
        data = cp.read_bytes()
    else:
        time.sleep(delay)
        data = subprocess.run(['curl', '-sL', '-A', UA, url], capture_output=True).stdout
        cp.write_bytes(data)
    # modern bartleby pages are UTF-8; fall back to cp1252 for the odd legacy byte
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        return data.decode('cp1252', 'replace')


def content_block(html):
    """Return the raw HTML of the main reading content (inside bby-single-content),
    trimmed of the leading meta/title header and the trailing footer."""
    m = re.search(r'<div class="bby-single-content[^"]*"[^>]*>(.*)', html, re.S)
    if not m:
        return ''
    block = m.group(1)
    # cut footer: stop at the meta-footer div
    fi = block.find('bby-content-meta-footer')
    if fi > 0:
        block = block[:block.rfind('<div', 0, fi)]
    # drop everything up to and including the <h1>Paras...</h1> or first real <p id=...>
    h = re.search(r'</h1>', block)
    if h:
        block = block[h.end():]
    else:
        # no Paras header (poem pages): drop the Contents / bibliographic meta <p> and title <p>
        block = re.sub(r'^.*?</p>\s*</?\w*>?', '', block, count=1, flags=re.S)
    return block


def page_markers(html):
    return [int(n) for n in re.findall(r'<!--\s*PAGE\s*NUM="(\d+)"\s*-->', html)]


def nav_links(html):
    prev = nxt = None
    for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*(Previous Article|Next Article)', html):
        u = m.group(1)
        if not u.startswith('http'):
            u = BASE + u
        if not u.endswith('/'):
            u += '/'
        if m.group(2) == 'Previous Article':
            prev = u
        else:
            nxt = u
    return prev, nxt


def title_of(html):
    m = re.search(r'<title>([^<]+)</title>', html)
    return htmllib.unescape(m.group(1)).strip() if m else ''


def clean_text(block_html):
    """HTML content block -> readable plain text with paragraph/line breaks.

    Handles bartleby's mixed markup: prose <p>..</p>, poem lines in unclosed
    <p id=N>, and definition-list virtue tables (<dt>/<dd>)."""
    h = block_html
    h = re.sub(r'<!--.*?-->', '', h, flags=re.S)              # drop PAGE NUM comments
    # small-caps <SC>X</SC> -> uppercase X (bartleby uses for drop-cap style)
    h = re.sub(r'(?i)<sc>(.*?)</sc>', lambda m: m.group(1).upper(), h)
    # line/paragraph-level tags -> newline
    h = re.sub(r'(?i)</?(p|br|div|tr|dt|li|h[1-6]|blockquote|hr)\b[^>]*>', '\n', h)
    # cell/definition tags -> space (keep term + precept on one line)
    h = re.sub(r'(?i)</?(dd|td|th)\b[^>]*>', ' ', h)
    h = re.sub(r'<[^>]+>', '', h)                             # drop remaining tags
    h = htmllib.unescape(h)
    lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in h.split('\n')]
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


if __name__ == '__main__':
    import json
    days = json.load(open(Path(__file__).parent / 'january_parsed.json'))
    print(f"{'day':>3} {'markers':>14} {'words':>6}  title / start-url")
    for d in days:
        url = d['reading_urls'][0] if d['reading_urls'] else None
        if not url:
            print(f"{d['day']:>3}  NO URL  {d['title']}"); continue
        html = fetch(url)
        pm = page_markers(html)
        txt = clean_text(content_block(html))
        rng = f"{min(pm)}-{max(pm)}" if pm else "none"
        want = d['page_ranges'][0] if d['page_ranges'] else None
        cover = ''
        if pm and want:
            cover = 'COVERS' if (min(pm) <= want[0] and max(pm) >= want[1]) else \
                    ('partial' if (min(pm) <= want[1] and max(pm) >= want[0]) else 'MISS')
        print(f"{d['day']:>3} {rng:>14} {len(txt.split()):>6}  {cover:>7} | {d['title'][:34]:34} {url}")
        sys.stdout.flush()
