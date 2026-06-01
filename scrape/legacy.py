#!/usr/bin/env python3
"""Fallback fetch + extract for bartleby pages that are dead on the live site,
using the 2006 Wayback snapshot (old table-based layout)."""
import re, html as htmllib, subprocess, time
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
CACHE = Path(__file__).parent / 'cache_wb'
CACHE.mkdir(exist_ok=True)
TS = '20060615130542'


def _slug(url):
    path = url.split('bartleby.com', 1)[-1]
    s = path.strip('/').replace('/', '_') or 'index'
    return s if s.endswith('.html') else s + '.html'


def fetch_wb(bartleby_url, delay=0.6):
    """Fetch the raw (id_) 2006 snapshot of a bartleby URL."""
    cp = CACHE / _slug(bartleby_url)
    if cp.exists() and cp.stat().st_size > 500:
        return cp.read_text(encoding='latin-1')
    path = bartleby_url.split('bartleby.com', 1)[-1]
    wb = f'https://web.archive.org/web/{TS}id_/http://www.bartleby.com{path}'
    time.sleep(delay)
    data = subprocess.run(['curl', '-sL', '-A', UA, wb], capture_output=True).stdout
    cp.write_bytes(data)
    # 2006 bartleby snapshots are windows-1252 / iso-8859-1
    return data.decode('cp1252', 'replace')


def page_markers_old(html):
    return [int(n) for n in re.findall(r'PAGE\s*NUM="(\d+)"', html)]


def clean_text_old(html):
    """Extract reading text from the old table layout (between CHAPTER markers)."""
    m = re.search(r'<!--\s*BEGIN CHAPTER\s*-->(.*?)<!--\s*END CHAPTER\s*-->', html, re.S | re.I)
    body = m.group(1) if m else html
    # also grab chapter title if present
    tm = re.search(r'<!--\s*BEGIN CHAPTERTITLE\s*-->(.*?)<!--\s*END CHAPTERTITLE\s*-->', html, re.S | re.I)
    title = ''
    if tm:
        title = re.sub(r'<[^>]+>', ' ', tm.group(1))
        title = re.sub(r'\s+', ' ', htmllib.unescape(title)).strip()

    h = body
    # remove paragraph/verse number cells: <A NAME="N">[N]...</A>
    h = re.sub(r'(?is)<a name="\d+">.*?</a>', '', h)
    h = re.sub(r'(?is)<a name="txt\d+">.*?</a>', '', h)
    # remove footnote reference links <A HREF="#note...">n</A>
    h = re.sub(r'(?is)<a href="#note[^"]*">.*?</a>', '', h)
    # each text row ends -> paragraph break
    h = re.sub(r'(?i)</tr>', '\n\n', h)
    h = re.sub(r'(?i)<br\s*/?>', '\n', h)
    # small fonts used for drop-cap first word: <FONT SIZE="-1">HERE</FONT> after a capital
    h = re.sub(r'<[^>]+>', '', h)
    h = htmllib.unescape(h)
    lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in h.split('\n')]
    text = re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()
    # strip leftover bracketed verse numbers like [1]
    text = re.sub(r'\[\s*\d+\s*\]', '', text)
    # drop footnote definition lines ("Note 4. ... [back]") and stray [back] markers
    text = '\n'.join(ln for ln in text.split('\n') if not re.match(r'\s*Note\s+\d+\.', ln))
    text = text.replace('[back]', '')
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\n[ \t]+', '\n', text)
    return title, re.sub(r'\n{3,}', '\n\n', text).strip()


def next_link_old(html):
    """Find the 'Next' page URL in old layout nav (returns bartleby path or None)."""
    # old nav uses images/links; look for a link whose text or alt is NEXT, or rel
    for m in re.finditer(r'<a href="([^"]+\.html)"[^>]*>\s*(?:<img[^>]*alt="?next"?[^>]*>|next|NEXT|&gt;)', html, re.I):
        return m.group(1)
    return None


if __name__ == '__main__':
    for url in ['https://www.bartleby.com/44/2/1.html',
                'https://www.bartleby.com/24/1/1.html',
                'https://www.bartleby.com/48/3/7.html']:
        html = fetch_wb(url)
        title, txt = clean_text_old(html)
        print(f'\n===== {url} =====')
        print('title:', title)
        print('markers:', page_markers_old(html))
        print('next:', next_link_old(html))
        print('words:', len(txt.split()))
        print('--- head ---')
        print(txt[:600])
