#!/usr/bin/env python3
"""Build an animated GitHub contribution grid using the supplied Bubbles artwork."""
import base64
import datetime as dt
import json
import math
import os
from pathlib import Path
import sys
import urllib.request
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'assets' / 'bubbles.png'
OUT = ROOT / 'assets' / 'bubbles-contributions.svg'
GRAPHQL = '''query($login:String!) {
  user(login:$login) { contributionsCollection {
    contributionCalendar { weeks { contributionDays {
      date weekday contributionCount contributionLevel
    } } }
  } }
}'''


def get_weeks():
    if '--demo' in sys.argv:
        # Local example only, not the user's contribution data.
        import random
        rng = random.Random(31)
        return [[{'contributionCount': (rng.choice([0, 0, 0, 1, 2, 4, 8]) if (x + y) % 4 else 0),
                  'date': f'demo-{x}-{y}', 'weekday': y} for y in range(7)] for x in range(53)]
    username = os.getenv('GITHUB_USERNAME') or os.getenv('GITHUB_REPOSITORY_OWNER')
    token = os.getenv('GH_TOKEN') or os.getenv('GITHUB_TOKEN')
    if not username or not token:
        raise RuntimeError('Set GITHUB_USERNAME (or GITHUB_REPOSITORY_OWNER) and GH_TOKEN (or GITHUB_TOKEN).')
    payload = json.dumps({'query': GRAPHQL, 'variables': {'login': username}}).encode()
    req = urllib.request.Request('https://api.github.com/graphql', data=payload,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'User-Agent': 'bubbles-contribution-animator'})
    with urllib.request.urlopen(req, timeout=35) as res:
        data = json.load(res)
    if data.get('errors') or not data.get('data', {}).get('user'):
        raise RuntimeError('GitHub GraphQL failed: ' + json.dumps(data.get('errors', data)))
    return [week['contributionDays'] for week in data['data']['user']['contributionsCollection']['contributionCalendar']['weeks']]


def build(weeks):
    # Keep all weeks from the current contribution calendar; preserve actual weekday positions.
    cell = 12
    step = 15
    gx, gy = 76, 75
    width = gx + max(len(weeks), 1) * step + 80
    height = 265
    max_count = max((d['contributionCount'] for w in weeks for d in w), default=0)
    colors = ['#202b39', '#0f5e69', '#158aa0', '#2bbbd2', '#7be8f0']
    items, active = [], []
    for x, days in enumerate(weeks):
        for y, day in enumerate(days):
            y = day.get('weekday', y)
            if y > 6: continue
            count = day['contributionCount']
            level = 0 if count == 0 else min(4, max(1, math.ceil(count / max(1, max_count) * 4)))
            xx, yy = gx + x * step, gy + y * step
            items.append(f'<rect x="{xx}" y="{yy}" width="{cell}" height="{cell}" rx="3" fill="{colors[level]}"><title>{escape(day.get("date", ""))}: {count} contributions</title></rect>')
            if count: active.append((xx + cell/2, yy + cell/2, len(items)-1))
    # Snake-like route across *active* squares: progress smoothly left-to-right, changing altitude.
    # Limit excessive SVG keyframes by sampling while always including the last target.
    if len(active) > 120:
        picks = [active[round(i*(len(active)-1)/119)] for i in range(120)]
    else:
        picks = active
    if not picks:
        picks = [(gx + 6, gy + 3*step + 6, 0)]
    path_points = [(max(22, gx-42), 162)] + [(x,y) for x,y,_ in picks] + [(width-40, 157)]
    path = 'M ' + ' L '.join(f'{x:.1f},{y:.1f}' for x, y in path_points)
    duration = 28
    def motion(delay=0):
        return f'<animateMotion dur="{duration}s" begin="{delay}s" repeatCount="indefinite" rotate="0" path="{path}" calcMode="linear" />'
    # Embed the exact supplied PNG, unchanged, inside an animated SVG image container.
    data = base64.b64encode(SRC.read_bytes()).decode('ascii')
    # Mark passing contribution squares with a subtle pulse in timeline sequence.
    # CSS is avoided; SVG SMIL works in common browser SVG image displays.
    pulses=[]
    interval = duration / (len(picks) + 2)
    for i, (_, _, rect_index) in enumerate(picks):
        # Distinct glow at each target, synchronized approximately with the flying route.
        x, y, _ = picks[i]
        begin = (i+1)*interval
        pulses.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#affbff" opacity="0"><animate attributeName="opacity" values="0;0.9;0" keyTimes="0;0.35;1" dur="0.8s" begin="{begin:.3f}s;{begin+duration:.3f}s" repeatCount="indefinite" /></circle>')
    trails = []
    for i, (color, r, op) in enumerate([('#ff8bb7', 9, .35), ('#ffd777', 8, .42), ('#80e6ac', 7, .45), ('#65caff', 6, .55), ('#9d9afa', 5, .57)]):
        # Repeatable delayed movement creates a short rainbow trail behind Bubbles.
        trails.append(f'<circle r="{r}" fill="{color}" opacity="{op}">{motion((i+1)*0.16)}</circle>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Bubbles flying over GitHub contributions">
<title>Bubbles flying across GitHub contribution activity</title>
<desc>Self-contained animated contribution graph using actual public account contributions. The character is the user's supplied PNG embedded unchanged.</desc>
<g>{''.join(items)}</g>
<g>{''.join(pulses)}</g>
<g>{''.join(trails)}</g>
<g>{motion(0)}<image x="-55" y="-46" width="110" height="92" xlink:href="data:image/png;base64,{data}" /></g>
</svg>'''
    OUT.write_text(svg, encoding='utf-8')
    print(f'Generated {OUT} with {len(weeks)} weeks and {len(active)} active days')

if __name__ == '__main__':
    build(get_weeks())
