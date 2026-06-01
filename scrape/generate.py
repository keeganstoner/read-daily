#!/usr/bin/env python3
"""Generate one .txt per January day: italic preamble (the guide's context note)
followed by the assembled reading text, plus an index.json and a review summary."""
import json, re, sys
from pathlib import Path
import assemble

HERE = Path(__file__).parent
OUT = HERE.parent / 'january'
OUT.mkdir(exist_ok=True)
MONTH = 'January'


def vol_of(read_line):
    m = re.search(r'Vol\.?\s*(\d+)', read_line)
    return m.group(1) if m else '?'


def range_str(ranges):
    return ', '.join(f'{a}–{b}' for a, b in ranges) if ranges else '?'


def build(day):
    text, sources, note = assemble.assemble_day(day)
    n = day['day']
    title = day['title']
    lines = [f'# Day {n} — {title}', '']
    # italic preamble: merge the guide's hard-wrapped sentence fragments into
    # paragraphs, keeping parenthetical date-notes as their own line.
    groups, cur = [], []
    for pl in day['preamble']:
        pl = pl.strip()
        if re.match(r'^\(.*\)\.?$', pl):            # parenthetical date note
            if cur:
                groups.append(' '.join(cur)); cur = []
            groups.append(pl)
        else:
            cur.append(pl)
    if cur:
        groups.append(' '.join(cur))
    for g in groups:
        lines.append(f'*{g}*')
        lines.append('')
    lines.append('---')          # divider between preface and reading
    lines.append('')
    lines.append(text.strip())
    lines.append('')
    vol = vol_of(day['read_line'])
    lines.append(f'— *The Harvard Classics, Vol. {vol}, pp. {range_str(day["page_ranges"])} '
                 f'(via bartleby.com)*')
    content = '\n'.join(lines).rstrip() + '\n'

    fname = f'{MONTH.lower()}-{n:02d}.txt'
    (OUT / fname).write_text(content, encoding='utf-8')
    return {
        'day': n, 'title': title, 'file': fname,
        'vol': vol, 'page_ranges': day['page_ranges'],
        'words': len(text.split()), 'sources': sources, 'note': note,
        'preamble': day['preamble'],
    }


def main():
    days = json.load(open(HERE / 'january_parsed.json'))
    want = set(int(x) for x in sys.argv[1:]) if len(sys.argv) > 1 else None
    index = []
    print(f"{'day':>3} {'words':>6}  {'src':>3}  title")
    for d in days:
        if want and d['day'] not in want:
            continue
        meta = build(d)
        index.append(meta)
        flag = '  <-- short?' if meta['words'] < 250 else ''
        print(f"{meta['day']:>3} {meta['words']:>6}  {len(meta['sources']):>3}  {meta['title'][:42]}{flag}")
    (OUT / 'index.json').write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\nWrote {len(index)} files + index.json to {OUT}")


if __name__ == '__main__':
    main()
