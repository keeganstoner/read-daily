#!/usr/bin/env python3
"""Parse a mensetmanus 'fifteen minutes a day' month page into structured day records.

Each record: {day, title, preamble (list of text lines), read_line_text,
              page_ranges [(a,b),...], reading_urls [normalized bartleby urls]}.
"""
import re, html as htmllib, json, sys
from pathlib import Path

NOISE = re.compile(r'^(FIFTEEN MINUTES A DAY|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|'
                   r'SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\b.*$', re.I)
NOISE2 = re.compile(r'.*Reading Guide\s*$', re.I)
NUMHDR = re.compile(r'^\s*\d+\s+(FIFTEEN MINUTES A DAY)', re.I)


def strip_tags(s):
    s = re.sub(r'(?i)<br\s*/?>', '\n', s)
    s = re.sub(r'<[^>]+>', '', s)
    return htmllib.unescape(s)


def norm_url(href):
    """Strip web.archive.org wrapper and force https://www.bartleby.com host."""
    m = re.search(r'(?:web\.archive\.org/web/\d+/)?(?:https?://)?(?:www\.)?bartleby\.com(/[^\s"]*)', href)
    if not m:
        return None
    path = m.group(1)
    return 'https://www.bartleby.com' + path


def is_text_page(path):
    """True if a bartleby path points to an actual readable text page (ends in N.html,
    not a /people/ bio listing, not a bare index)."""
    if '/people/' in path:
        return False
    if re.search(r'/index\d*\.html$', path):
        return False
    # must end with <number>.html and have at least a volume + page component
    return bool(re.search(r'^/\d+(?:/\d+)*/\d+\.html$', path))


def parse_ranges(text):
    """From visible read-line text, return list of (start,end) printed-page ranges.
    Handles 'pp. 79-85', '119-120, 388-394', 'pp. 43-44; also pp. 31-43', 'p. 883'."""
    # normalize dashes
    t = text.replace('–', '-').replace('—', '-')
    # only look at the part from the first 'p' page indicator onward to avoid Vol. numbers,
    # but Vol. numbers are a problem; instead capture explicit ranges a-b and standalone after 'pp.'
    ranges = []
    # ranges like 79-85
    for m in re.finditer(r'(\d+)\s*-\s*(\d+)', t):
        a, b = int(m.group(1)), int(m.group(2))
        if 0 < a <= b and b - a < 200:   # sanity
            ranges.append((a, b))
    return ranges


def parse_anchors(read_html):
    """Return ordered list of (url, anchor_text) for bartleby text-page links whose
    visible text looks like a page reference (contains digits / p. / pp.)."""
    out = []
    for m in re.finditer(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', read_html, re.S | re.I):
        href, inner = m.group(1), strip_tags(m.group(2)).strip()
        url = norm_url(href)
        if not url:
            continue
        path = url[len('https://www.bartleby.com'):]
        if not is_text_page(path):
            continue
        # anchor text must reference a page (digits, optionally p./pp.)
        if re.search(r'\d', inner) and (re.search(r'p+\.', inner) or re.fullmatch(r'[\d\s,\-–—]+', inner)):
            out.append((url, inner))
    # dedupe preserve order
    seen, ded = set(), []
    for u, t in out:
        if u not in seen:
            seen.add(u); ded.append((u, t))
    return ded


def parse_month(html_path):
    raw = Path(html_path).read_text(encoding='latin-1')
    # region between the month <h2> and the closing nav <hr>/image
    start = raw.find('<h2>JANUARY</h2>')
    if start < 0:
        start = raw.find('<h2>')
    end = raw.find('<p align="center">\n<img', start)
    if end < 0:
        end = raw.find('<hr>', raw.find('Channing') - 400) if 'Channing' in raw else len(raw)
    region = raw[start:end]

    # find day boundaries: <b>N Title</b>
    days = []
    bolds = list(re.finditer(r'<b>\s*(\d+)\s+(.*?)</b>', region, re.S))
    for i, mb in enumerate(bolds):
        day = int(mb.group(1))
        title = strip_tags(mb.group(2)).strip()
        chunk_start = mb.end()
        chunk_end = bolds[i + 1].start() if i + 1 < len(bolds) else len(region)
        chunk = region[chunk_start:chunk_end]

        # the read line: from first occurrence of 'Read' (start of a line) to end of chunk
        rm = re.search(r'(?im)(^|<br>)\s*(Read\b.*)$', chunk, re.S)
        if rm:
            read_html = rm.group(2)
            pre_html = chunk[:rm.start(2)]
        else:
            read_html, pre_html = '', chunk

        # preamble lines
        pre_lines = []
        for line in strip_tags(pre_html).split('\n'):
            line = line.strip()
            if not line:
                continue
            if NOISE.match(line) or NOISE2.match(line) or NUMHDR.match(line):
                continue
            pre_lines.append(line)

        read_text = ' '.join(strip_tags(read_html).split())
        anchors = parse_anchors(read_html)
        ranges = parse_ranges(read_text)

        days.append({
            'day': day,
            'title': title,
            'preamble': pre_lines,
            'read_line': read_text,
            'page_ranges': ranges,
            'reading_urls': [u for u, _ in anchors],
            'anchor_texts': [t for _, t in anchors],
        })
    return days


if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else 'january_raw.html'
    days = parse_month(src)
    print(json.dumps(days, indent=2, ensure_ascii=False))
    sys.stderr.write(f'\nParsed {len(days)} days\n')
