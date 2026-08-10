#!/usr/bin/env python3
"""Build n8fury profile cards: desktop + mobile, dark + light.

CSS-driven animation with prefers-reduced-motion, flame flicker, textLength
font hardening, mobile reflow, and an optional WakaTime activity section.

Usage:
    python build_card.py                 # static card only
    python build_card.py waka.json       # with WakaTime activity section

If the WakaTime file is missing, unreadable, or contains no language data,
the activity section is silently omitted and the card renders exactly as it
does without it. A dead API key can never produce a broken card.
"""
import re
import sys
import json
import html
import pathlib

SRC = pathlib.Path('assets/flame.txt')   # ASCII art, one row per line
OUT = pathlib.Path('assets')

# ── static content ────────────────────────────────────────────────────────
HOST = 'n8fury@DR460NR1D3R'
ROWS = [
    ('User',                  'MD. Mamdud Hasan (n8fury)'),
    ('OS',                    'Arch Linux, Windows 11 + WSL2'),
    ('Host',                  'Zeroozen Energy Limited'),
    ('Kernel',                'Web Dev, REST-Oriented Backend'),
    ('Shell',                 'Cloud5 \u2014 Design & Dev Studio'),
    ('Locale',                'Dhaka, Bangladesh'),
    (None,                    None),
    ('Languages.Programming', 'JavaScript, Python, C++'),
    ('Languages.Computer',    'HTML, CSS, Markdown, LaTeX'),
    ('Stack.Backend',         'Node.js, NestJS, REST APIs'),
    ('Stack.Data',            'PostgreSQL, MongoDB, TimescaleDB'),
    ('Stack.IoT/ML',          'ESP32, MQTT, TensorFlow'),
    ('Stack.Infra',           'Docker, Linux, VPS, Vercel'),
    (None,                    None),
    ('@Projects',             None),
    ('E-Commerce',            'MERN stack storefront'),
    ('ag-qrew-qwen',          'Agentic QA system \u2014 hackathon'),
    ('RAG.Chatbot',           'Retrieval-augmented LLM bot'),
]

TOP_LANGS = 2
CAT_MIN = 10             # a category must clear this percent to be worth naming

# WakaTime's raw category labels -> how they read on the card
CAT_LABEL = {'AI Coding': 'AI assisted Coding'}

WEEKEND = {'Saturday', 'Sunday'}
NUMWORD = {1: 'one', 2: 'two', 3: 'three',
           4: 'four', 5: 'five', 6: 'six', 7: 'seven'}

# Time-of-day bucket -> (rhythm phrasing, peak phrasing)
TIME_WORD = {
    'Morning': ('morning hours',    'mornings'),
    'Daytime': ('daytime hours',    'afternoons'),
    'Evening': ('evening hours',    'evenings'),
    'Night':   ('late-night hours', 'late nights'),
}

DAYS = ['Monday', 'Tuesday', 'Wednesday',
        'Thursday', 'Friday', 'Saturday', 'Sunday']
TIMES = ['Morning', 'Daytime', 'Evening', 'Night']


# WakaTime counts config/markup/tooling files as "languages". None of these say
# anything about what you build, and "Other" is meaningless on a card.
LANG_IGNORE = {
    'Other', 'Text', 'Git', 'Git Config', 'TSConfig', 'TOML',
    'Image (svg)', 'INI', 'Properties',
}


def readme_stats(path='README.md'):
    """Day-of-week and time-of-day come from GitHub COMMIT history, not from the
    WakaTime API -- waka-readme-stats already computes them into the README
    between the waka section markers. Reading them there gives a ~6.6k-commit
    sample instead of the single week the free WakaTime tier retains.
    Returns {} on any problem; the peak rows are then simply omitted."""
    try:
        txt = pathlib.Path(path).read_text(encoding='utf-8')
    except Exception:
        return {}
    m = re.search(
        r'<!--START_SECTION:waka-->(.*?)<!--END_SECTION:waka-->', txt, re.S)
    if not m:
        print('  readme: waka section not found -- peak rows skipped')
        return {}
    pat = re.compile(
        r'^\s*(?:[^\w\s]+\s*)?([A-Za-z]+)\s+([\d,]+)\s+commits?\b.*?([\d.]+)\s*%', re.M)
    rows = {n: (int(c.replace(',', '')), float(pc))
            for n, c, pc in pat.findall(m.group(1))}
    days = {k: v for k, v in rows.items() if k in DAYS}
    times = {k: v for k, v in rows.items() if k in TIMES}
    if not days or not times:
        print('  readme: commit tables incomplete -- peak rows skipped')
        return {}
    out = {
        'day':   max(days, key=lambda k: days[k][0]),
        'time':  max(times, key=lambda k: times[k][0]),
        'days':  days, 'times': times,
        'total': sum(v[0] for v in days.values()),
    }
    print(
        f"  readme: peak {out['day']} / {out['time']} from {out['total']} commits")
    return out


def pace_words(avg):
    """'3 hrs 6 mins' -> 'About three hours a day'. The vocabulary is coarse on
    purpose: a few minutes of drift must not change the wording."""
    if not avg:
        return None
    hm = re.search(r'(\d+)\s*hrs?', avg)
    mm = re.search(r'(\d+)\s*mins?', avg)
    t = (int(hm.group(1)) if hm else 0) + (int(mm.group(1)) if mm else 0) / 60
    if t < 1:
        return 'Under an hour a day'
    if t < 1.5:
        return 'About an hour a day'
    n = round(t)
    return 'Eight-plus hours a day' if n >= 8 else f'About {NUMWORD.get(n, n)} hours a day'


def join_and(names):
    if len(names) < 2:
        return names[0] if names else ''
    return f"{', '.join(names[:-1])} and {names[-1]}"


ACTIVITY_FIELDS = ['Focus', 'Peak', 'Rhythm', 'Quietest', 'Pace', 'Mode']


def waka_rows(path, rm=None):
    """Turn a WakaTime stats payload into card rows. Returns [] only when no
    WakaTime file was given at all.

    A quiet week is data, not a failure: every field in ACTIVITY_FIELDS is
    always emitted, with an empty value where the payload has nothing to say.
    The section keeps its shape whether the week was busy, idle, or the API key
    is dead -- rows never appear and disappear between builds."""
    if not path:
        return []

    d = {}
    try:
        raw = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
        d = raw.get('data', raw)
    except Exception as e:
        print(f'  waka: unreadable ({e}) -- values left blank')

    langs = [l for l in d.get('languages', [])
             if l.get('percent', 0) > 0 and l.get('name') not in LANG_IGNORE][:TOP_LANGS]
    total = d.get('human_readable_total') or ''

    rm = rm or {}
    vals = {}

    if langs:
        vals['Focus'] = join_and([l['name'] for l in langs])

    if rm:
        wknd = sum(v[1] for k, v in rm['days'].items() if k in WEEKEND)
        when = 'Weekends' if wknd >= 35 else (
            'Weekdays' if wknd <= 22 else 'All week')
        vals['Rhythm'] = f"{when}, {TIME_WORD[rm['time']][0]}"
        vals['Peak'] = f"{rm['day']} {TIME_WORD[rm['time']][1]}"
        quiet = min(rm['days'], key=lambda k: rm['days'][k][0])
        vals['Quietest'] = f'{quiet}s'

    pace = pace_words(d.get('human_readable_daily_average'))
    if pace:
        vals['Pace'] = pace

    # WakaTime "categories" -- how the time was spent, not what it was spent on.
    # Deliberately NOT project names: those are local folder names and leak
    # private work.
    cats = [CAT_LABEL.get(c['name'], c['name'])
            for c in d.get('categories', []) if c.get('percent', 0) >= CAT_MIN]
    if cats:
        vals['Mode'] = join_and(cats[:2])

    rows = [('@Last 7 Days', None)] + [(k, vals.get(k, ''))
                                       for k in ACTIVITY_FIELDS]

    blank = [k for k in ACTIVITY_FIELDS if not vals.get(k)]
    print(f'  waka: {len(langs)} languages, total {total!r}'
          + (f', blank {blank}' if blank else ''))
    return rows


# ── palettes ──────────────────────────────────────────────────────────────
DARK = dict(bg0='#151010', bg1='#0A0707', g0='#EF4444', g1='#F97316', g2='#FBBF24',
            key='#F97316', val='#E5E7EB', dim='#57534E', head='#EF4444',
            accent='#10B981', tex='#FCA5A5', texop='0.04')
LIGHT = dict(bg0='#FDFBFA', bg1='#F0E9E4', g0='#B91C1C', g1='#C2410C', g2='#B45309',
             key='#C2410C', val='#1C1917', dim='#D6D3D1', head='#9F1239',
             accent='#047857', tex='#78716C', texop='0.05')

TITLE = ('MD. Mamdud Hasan (n8fury) \u2014 Software Engineer at Zeroozen Energy. '
         'Backend, IoT and data systems for light electric vehicles.')
DESC = ('Terminal-style profile card: ASCII flame artwork with a neofetch-style '
        'listing of role, location, languages, stack, projects and coding activity.')

MONO = "'Courier New', Consolas, Menlo, 'Liberation Mono', 'DejaVu Sans Mono', monospace"


def ascii_rows():
    """ASCII art from a plain text file -- never from a generated SVG, so the
    build can never end up reading its own output."""
    return [ln.rstrip() for ln in SRC.read_text(encoding='utf-8').splitlines() if ln.strip()]


def flame(rows, x, y0, lh, scale=1.0):
    n = len(rows)
    out = [
        f'<g class="art" transform="translate({x:g},{y0:g}) scale({scale:g})">']
    for band, (lo, hi) in enumerate([(0, n // 3), (n // 3, 2 * n // 3), (2 * n // 3, n)]):
        out.append(f'<text class="ascii f{band}" x="0" y="0">')
        for i in range(lo, hi):
            out.append(f'<tspan x="0" y="{i * lh:.1f}" xml:space="preserve">'
                       f'{html.escape(rows[i])}</tspan>')
        out.append('</text>')
    out.append('</g>')
    return '\n'.join(out)


def cells(txt):
    """Monospace cell width. Emoji render ~2 cells wide but len() counts 1, so
    padding and textLength must both be computed from this, not from len()."""
    w = 0
    for ch in txt:
        o = ord(ch)
        if o == 0xFE0F:                                   # variation selector
            continue
        w += 2 if (o >= 0x1F000 or 0x2600 <= o <= 0x27BF) else 1
    return w


def adv(txt, px):
    return cells(txt) * px * 0.6


# ── desktop ───────────────────────────────────────────────────────────────
def desktop(pal, art_rows, rows, act):
    """Two columns: ASCII art over the activity block on the left, the info
    list on the right. Putting activity under the art uses space the card
    already occupies instead of growing the card downward."""
    W, FS, STEP = 1180, 15, 28
    RX, RY, RCOLS = 500, 48, 72          # right column: info list
    LX, LCOLS = 30, 50                   # left column: activity, under the art
    lines, clips, n = [], [], 0

    def emit(x, y, segs, width, cols):
        nonlocal n
        clips.append(f'<clipPath id="lc{n}"><rect class="lc" x="{x}" y="{y - 17}" '
                     f'width="{cols * FS * 0.6:.0f}" height="{STEP}" '
                     f'style="animation-delay:{0.5 + n * 0.085:.3f}s; transform-origin:{x}px 0"/></clipPath>')
        body = ''.join(
            f'<tspan class="{c}">{html.escape(t)}</tspan>' for c, t in segs)
        lines.append(f'<g clip-path="url(#lc{n})"><text x="{x}" y="{y}" '
                     f'textLength="{width:.1f}" lengthAdjust="spacingAndGlyphs">{body}</text></g>')
        n += 1

    def render(col_rows, x, y0, cols, head=None):
        grid = cols * FS * 0.6
        y = y0
        if head:
            rule = '\u2014' * \
                max(1, round((grid - adv(head, 17) - adv(' ', FS)) / (FS * 0.6)))
            emit(x, y, [('head', head), ('dim', ' ' + rule)], grid, cols)
            y += STEP
        for key, val in col_rows:
            if key is None:
                emit(x, y, [('dim', '. ')], adv('. ', FS), cols)
            elif key.startswith('@'):
                label = '- ' + key[1:]
                r = '\u2014' * max(1, cols - cells(label) - 1)
                emit(x, y, [('accent', label), ('dim', ' ' + r)], grid, cols)
            else:
                segs = [('dim', '. ')]
                for j, part in enumerate(key.split('.')):
                    if j:
                        segs.append(('dim', '.'))
                    segs.append(('key', part))
                pad = max(1, cols - 2 - cells(key) - 2 - cells(val) - 1)
                segs.append(('dim', ': ' + '.' * pad + ' '))
                if val:
                    segs.append(('val', val))
                emit(x, y, segs, adv('. ' + key + ': ' +
                     '.' * pad + ' ' + val, FS), cols)
            y += STEP
        return y - STEP          # baseline of the last row, not the next slot

    def seg_pair(key, val, cols):
        """One key/value cell inside a full-width row."""
        if key is None:
            return [('dim', ' ' * cols)], ' ' * cols
        segs = [('dim', '. ')]
        for j, part in enumerate(key.split('.')):
            if j:
                segs.append(('dim', '.'))
            segs.append(('key', part))
        pad = max(1, cols - 2 - cells(key) - 2 - cells(val) - 1)
        segs.append(('dim', ': ' + '.' * pad + ' '))
        if val:
            segs.append(('val', val))
        return segs, '. ' + key + ': ' + '.' * pad + ' ' + val

    def render_pairs(items, x, y0, colw, gap):
        """Activity spans the full card width, two fields per row -- uses the
        empty band under both columns instead of growing the card downward."""
        total = colw * 2 + gap
        grid = total * FS * 0.6
        y = y0
        label = '- ' + items[0][0][1:]
        r = '\u2014' * max(1, total - cells(label) - 1)
        emit(x, y, [('accent', label), ('dim', ' ' + r)], grid, total)
        y += STEP
        rest = items[1:]
        for i in range(0, len(rest), 2):
            a = rest[i]
            b = rest[i + 1] if i + 1 < len(rest) else (None, None)
            sa, pa = seg_pair(a[0], a[1], colw)
            sb, pb = seg_pair(b[0], b[1], colw)
            emit(x, y, sa + [('dim', ' ' * gap)] + sb,
                 adv(pa + ' ' * gap + pb, FS), total)
            y += STEP
        return y - STEP

    art = flame(art_rows, LX, 56, 7.3)
    art_end = 56 + len(art_rows) * 7.3

    right_end = render(rows, RX, RY, RCOLS, head=HOST)
    act_end = render_pairs(act, LX, max(
        art_end, right_end) + 36, 60, 4) if act else 0

    H = int(max(right_end, act_end, art_end) + 30)
    return shell(pal, W, H, art, '\n'.join(lines), '\n'.join(clips), FS, 17, False)


# ── mobile ────────────────────────────────────────────────────────────────
def mobile(pal, art_rows, rows):
    W, PAD, FS, SC = 600, 24, 19, 0.60
    art_h = len(art_rows) * 7.3 * SC
    art_w = 96 * 8.3 * 0.6 * SC
    y = PAD + 6
    art = flame(art_rows, (W - art_w) / 2, y, 7.3, SC)
    y += art_h + 30

    lines, delay = [], 0.35

    def row(segs, dy):
        nonlocal y, delay
        y += dy
        body = ''.join(
            f'<tspan class="{c}">{html.escape(t)}</tspan>' for c, t in segs)
        w = adv(''.join(t for _, t in segs), FS)
        lines.append(f'<text class="mr" x="{PAD}" y="{y:.0f}" textLength="{w:.1f}" '
                     f'lengthAdjust="spacingAndGlyphs" style="animation-delay:{delay:.2f}s">{body}</text>')
        delay += 0.06

    row([('head', HOST)], 0)
    y += 6
    for key, val in rows:
        if key is None:
            y += 10
            continue
        if key.startswith('@'):
            row([('accent', '- ' + key[1:])], 34)
            continue
        segs = []
        for j, part in enumerate(key.split('.')):
            if j:
                segs.append(('dim', '.'))
            segs.append(('key', part))
        segs.append(('dim', ': '))
        if val:
            segs.append(('val', val))
        row(segs, 27)
    return shell(pal, W, int(y + PAD + 8), art, '\n'.join(lines), '', FS, FS + 1, True)


# ── shared shell ──────────────────────────────────────────────────────────
def shell(pal, W, H, art, lines, clips, fs, hfs, is_mobile):
    reveal = '' if is_mobile else f'''  <mask id="reveal" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">
    <rect id="revealbar" x="0" y="0" width="{W}" height="{H}" fill="#fff"/>
  </mask>
'''
    motion = '''
    #revealbar { transform-box: view-box; transform-origin: 0 0;
                 animation: reveal 2.4s cubic-bezier(.25,.1,.25,1) backwards; }
    @keyframes reveal { from { transform: scaleY(0); } }
    .lc { transform-box: view-box; animation: type .34s linear backwards; }
    @keyframes type { from { transform: scaleX(0); } }
''' if not is_mobile else '''
    .mr { animation: rise .5s ease-out backwards; }
    @keyframes rise { from { opacity: 0; transform: translateY(6px); } }
    .art { animation: fade 1.2s ease-out backwards; }
    @keyframes fade { from { opacity: 0; } }
'''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img">
<title>{html.escape(TITLE)}</title>
<desc>{html.escape(DESC)}</desc>
<defs>
  <linearGradient id="ag" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop id="gs0" offset="0%" stop-color="{pal['g0']}"/>
    <stop id="gs1" offset="100%" stop-color="{pal['g1']}"/>
  </linearGradient>
  <radialGradient id="bg" cx="30%" cy="20%" r="80%">
    <stop offset="0%" stop-color="{pal['bg0']}"/>
    <stop offset="100%" stop-color="{pal['bg1']}"/>
  </radialGradient>
  <pattern id="tex" width="4" height="4" patternUnits="userSpaceOnUse">
    <rect width="4" height="1" fill="{pal['tex']}" opacity="{pal['texop']}"/>
  </pattern>
{reveal}{clips}
  <style>
    .ascii  {{ font-family: {MONO}; font-size: 8.3px; fill: url(#ag); letter-spacing: -0.2px; }}
    text    {{ font-family: {MONO}; font-size: {fs}px; white-space: pre; }}
    .key    {{ fill: {pal['key']}; font-weight: bold; }}
    .val    {{ fill: {pal['val']}; }}
    .dim    {{ fill: {pal['dim']}; }}
    .head   {{ fill: {pal['head']}; font-size: {hfs}px; font-weight: bold; }}
    .accent {{ fill: {pal['accent']}; font-weight: bold; }}
{motion}
    .f0 {{ animation: fk0 2.3s ease-in-out infinite; }}
    .f1 {{ animation: fk1 3.1s ease-in-out infinite; }}
    .f2 {{ animation: fk2 4.3s ease-in-out infinite; }}
    @keyframes fk0 {{ 0%,100%{{opacity:1}} 28%{{opacity:.70}} 52%{{opacity:.95}} 76%{{opacity:.80}} }}
    @keyframes fk1 {{ 0%,100%{{opacity:1}} 34%{{opacity:.84}} 68%{{opacity:.93}} }}
    @keyframes fk2 {{ 0%,100%{{opacity:1}} 46%{{opacity:.91}} }}

    #gs0 {{ animation: h0 9s linear infinite; }}
    #gs1 {{ animation: h1 9s linear infinite; }}
    @keyframes h0 {{ 0%,100%{{stop-color:{pal['g0']}}} 33%{{stop-color:{pal['g1']}}} 66%{{stop-color:{pal['g2']}}} }}
    @keyframes h1 {{ 0%,100%{{stop-color:{pal['g1']}}} 33%{{stop-color:{pal['g2']}}} 66%{{stop-color:{pal['g0']}}} }}

    @media (prefers-reduced-motion: reduce) {{
      #revealbar, .lc, .mr, .art, .f0, .f1, .f2, #gs0, #gs1 {{
        animation: none !important; transform: none !important; opacity: 1 !important;
      }}
    }}
  </style>
</defs>

<rect width="{W}" height="{H}" fill="url(#bg)"/>
<rect width="{W}" height="{H}" fill="url(#tex)"/>

<g{' mask="url(#reveal)"' if not is_mobile else ''}>
{art}
{lines}
</g>
</svg>
'''


if __name__ == '__main__':
    waka = sys.argv[1] if len(sys.argv) > 1 else None
    art = ascii_rows()
    act = waka_rows(waka, readme_stats())
    rows = ROWS
    OUT.mkdir(parents=True, exist_ok=True)
    for name, doc in {
        'dark.svg':         desktop(DARK, art, rows, act),
        'light.svg':        desktop(LIGHT, art, rows, act),
        'mobile-dark.svg':  mobile(DARK, art, rows + ([(None, None)] + act if act else [])),
        'mobile-light.svg': mobile(LIGHT, art, rows + ([(None, None)] + act if act else [])),
    }.items():
        (OUT / name).write_text(doc, encoding='utf-8')
        h = re.search(r'height="(\d+)"', doc).group(1)
        print(f'  {name:18} {len(doc):>6} bytes   height {h}')
