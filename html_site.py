"""Sodobna javna spletna stran (index / spremembe / iskanje)."""

from __future__ import annotations

import json
import logging
from collections import OrderedDict
from datetime import date, datetime
from pathlib import Path

from config import CONFIG, HTML_DIR

logger = logging.getLogger('kzs')

# Fonts & shell – Syne (display) + Figtree (UI); cool arena light, signal green
SITE_CSS = r"""
:root {
  --bg: #f2f3f5;
  --bg-2: #eaecef;
  --ink: #17181c;
  --muted: #6b7280;
  --accent: #3f4654;
  --accent-ink: #17181c;
  --heat: #b45309;
  --surface: rgba(255,255,255,0.78);
  --line: rgba(23,24,28,0.1);
  --radius: 0;
  --font-display: "Manrope", "Segoe UI", sans-serif;
  --font-body: "Manrope", "Segoe UI", sans-serif;
  --ease: cubic-bezier(0.22, 1, 0.36, 1);
  --pad: clamp(1.1rem, 3vw, 2.4rem);
}
*, *::before, *::after { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  min-height: 100vh;
  color: var(--ink);
  font-family: var(--font-body);
  font-size: 1.05rem;
  line-height: 1.5;
  background:
    radial-gradient(1100px 640px at 88% -8%, rgba(63,70,84,0.08), transparent 55%),
    radial-gradient(800px 480px at -8% 28%, rgba(180,83,9,0.05), transparent 50%),
    linear-gradient(165deg, var(--bg), var(--bg-2));
  background-attachment: fixed;
}
body::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  opacity: 0.28;
  background-image:
    linear-gradient(rgba(23,24,28,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(23,24,28,0.04) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at 50% 20%, #000 20%, transparent 75%);
}
a { color: var(--ink); text-underline-offset: 3px; }
a:hover { color: var(--muted); }
a.player, a.team, a.league-link, span.league-link {
  font-weight: 600;
  color: var(--ink);
  text-decoration: none;
  background-image: linear-gradient(currentColor, currentColor);
  background-size: 0% 1.5px;
  background-position: 0 100%;
  background-repeat: no-repeat;
  transition: background-size 0.35s var(--ease), color 0.2s;
}
a.player:hover, a.team:hover, a.league-link:hover {
  background-size: 100% 1.5px;
}
.shell {
  position: relative;
  z-index: 1;
  width: min(1120px, 100%);
  margin: 0 auto;
  padding: 0 var(--pad) 5rem;
}
.topnav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.15rem 0 0.5rem;
  font-family: var(--font-body);
  font-size: 0.92rem;
  font-weight: 600;
}
.topnav .brand-mark {
  font-family: var(--font-display);
  font-weight: 800;
  font-size: 1.15rem;
  letter-spacing: -0.04em;
  color: var(--ink);
  text-decoration: none;
}
.topnav .links { display: flex; flex-wrap: wrap; gap: 0.35rem 1.15rem; }
.topnav .links a {
  color: var(--muted);
  text-decoration: none;
  position: relative;
}
.topnav .links a[aria-current="page"],
.topnav .links a:hover { color: var(--ink); }
.topnav .links a[aria-current="page"]::after {
  content: "";
  position: absolute;
  left: 0; right: 0; bottom: -0.35rem;
  height: 2px;
  background: var(--accent);
  transform-origin: left;
  animation: growX 0.55s var(--ease) both;
}
.meta { color: var(--muted); font-size: 0.92em; }
.badge {
  display: inline-block;
  font-family: var(--font-body);
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 0.22rem 0.45rem;
  margin-right: 0.4rem;
  color: var(--ink);
  background: rgba(23,24,28,0.06);
  border: 1px solid var(--line);
}
.badge[data-kind="prestop"] {
  color: #9a3412;
  background: rgba(180,83,9,0.1);
  border-color: rgba(180,83,9,0.28);
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  font-family: var(--font-body);
  font-weight: 700;
  font-size: 0.95rem;
  padding: 0.85rem 1.35rem;
  border: 1.5px solid var(--ink);
  background: var(--ink);
  color: #fff;
  text-decoration: none;
  cursor: pointer;
  transition: transform 0.35s var(--ease), background 0.25s, color 0.25s, box-shadow 0.35s;
}
.btn:hover {
  transform: translateY(-2px);
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.btn-ghost {
  background: transparent;
  color: var(--ink);
}
.btn-ghost:hover {
  background: var(--ink);
  color: #fff;
  border-color: var(--ink);
}
.btn-load {
  width: 100%;
  margin-top: 1.25rem;
  background: transparent;
  color: var(--ink);
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin: 1rem 0 1.25rem;
}
.filters button {
  font-family: var(--font-body);
  font-size: 0.82rem;
  font-weight: 650;
  padding: 0.45rem 0.8rem;
  border: 1px solid var(--line);
  background: var(--surface);
  backdrop-filter: blur(10px);
  color: var(--muted);
  cursor: pointer;
  transition: color 0.2s, border-color 0.2s, background 0.2s;
}
.filters button:hover { color: var(--ink); border-color: var(--ink); }
.filters button.active {
  color: var(--ink);
  border-color: var(--ink);
  background: rgba(23,24,28,0.06);
}

/* —— reveal motion —— */
.rise {
  opacity: 0;
  transform: translateY(18px);
  transition: opacity 0.7s var(--ease), transform 0.7s var(--ease);
}
.rise.in { opacity: 1; transform: none; }
/* prvi zaslon: ne čakaj na IO */
.hero .rise, .page-head .rise, .search-hero .rise { opacity: 1; transform: none; }
.hero .rise { animation: softRise 0.85s var(--ease) both; }
.hero .rise:nth-child(2) { animation-delay: 0.08s; }
.hero .rise:nth-child(3) { animation-delay: 0.16s; }
.hero .rise:nth-child(4) { animation-delay: 0.24s; }
@keyframes softRise {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: none; }
}
@media (prefers-reduced-motion: reduce) {
  .rise { opacity: 1; transform: none; transition: none; }
  .hero .rise { animation: none; }
  .topnav .links a[aria-current="page"]::after { animation: none; }
  .court-line, .court-accent, .hero-orb, .brand-xl { animation: none !important; }
}

@keyframes growX { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes drawLine {
  to { stroke-dashoffset: 0; }
}
@keyframes floatOrb {
  0%, 100% { transform: translate3d(0,0,0) scale(1); }
  50% { transform: translate3d(12px,-18px,0) scale(1.04); }
}
@keyframes brandIn {
  from { opacity: 0; letter-spacing: 0.12em; filter: blur(6px); }
  to { opacity: 1; letter-spacing: -0.03em; filter: blur(0); }
}
@keyframes pulseDot {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.35); opacity: 0.55; }
}

/* —— hero —— */
.hero {
  position: relative;
  min-height: min(92vh, 820px);
  display: grid;
  align-content: end;
  padding: 2rem 0 3.5rem;
  overflow: clip;
}
.hero-stage {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}
.hero-stage svg {
  width: 100%;
  height: 100%;
  display: block;
}
.court-line {
  fill: none;
  stroke: rgba(11,16,32,0.22);
  stroke-width: 2.5;
  stroke-dasharray: 1600;
  stroke-dashoffset: 1600;
  animation: drawLine 2.2s var(--ease) 0.15s forwards;
}
.court-accent {
  fill: none;
  stroke: rgba(63,70,84,0.45);
  stroke-width: 3;
  stroke-dasharray: 900;
  stroke-dashoffset: 900;
  animation: drawLine 1.8s var(--ease) 0.45s forwards;
}
.hero-orb {
  position: absolute;
  width: min(42vw, 320px);
  aspect-ratio: 1;
  right: 4%;
  top: 12%;
  border-radius: 50%;
  background:
    radial-gradient(circle at 35% 30%, #fff 0%, #ffe0d4 28%, var(--heat) 62%, #9a1f00 100%);
  opacity: 0.9;
  animation: floatOrb 7s ease-in-out infinite;
  mix-blend-mode: multiply;
}
.hero-copy { position: relative; z-index: 1; max-width: min(22ch, 100%); }
.brand-xl {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 800;
  font-size: clamp(3.6rem, 12vw, 7rem);
  line-height: 0.92;
  letter-spacing: -0.04em;
  font-variation-settings: normal;
  color: var(--ink);
  animation: brandIn 1.1s var(--ease) both;
}
.hero h1 {
  margin: 1.1rem 0 0.55rem;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: clamp(1.55rem, 3.4vw, 2.35rem);
  letter-spacing: -0.03em;
  line-height: 1.15;
}
.hero .lede {
  margin: 0 0 1.6rem;
  color: var(--muted);
  font-size: 1.08rem;
  max-width: 34ch;
}
.cta-row { display: flex; flex-wrap: wrap; gap: 0.75rem; }
.live-dot {
  display: inline-block;
  width: 0.55rem;
  height: 0.55rem;
  margin-right: 0.4rem;
  border-radius: 50%;
  background: var(--accent);
  animation: pulseDot 1.6s ease-in-out infinite;
  vertical-align: middle;
}

/* —— feed —— */
.page-head { padding: 1.5rem 0 0.5rem; }
.page-head h1 {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: clamp(1.85rem, 4vw, 2.6rem);
  letter-spacing: -0.03em;
  line-height: 1.1;
}
.page-head .sub { margin: 0.55rem 0 0; color: var(--muted); max-width: 42ch; }
.day-block {
  margin: 1.75rem 0;
  padding-top: 0.25rem;
}
.day-block[hidden] { display: none !important; }
.day-label {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  margin: 0 0 0.85rem;
  font-family: var(--font-display);
  font-weight: 750;
  font-size: 1.15rem;
  letter-spacing: -0.02em;
}
.day-label .count {
  font-family: var(--font-body);
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--muted);
}
.feed-list { list-style: none; margin: 0; padding: 0; }
.feed-item {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.35rem 1rem;
  align-items: baseline;
  padding: 0.95rem 0;
  border-top: 1px solid var(--line);
  transition: background 0.25s, padding-left 0.35s var(--ease);
}
.feed-item:hover { padding-left: 0.35rem; background: rgba(255,255,255,0.35); }
.feed-item .when {
  color: var(--muted);
  font-size: 0.86rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.feed-item .body { min-width: 0; }
.preview-strip {
  margin-top: 2.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--line);
}
.preview-strip h2 {
  margin: 0 0 0.85rem;
  font-family: var(--font-display);
  font-size: 1.05rem;
  letter-spacing: -0.02em;
}
.preview-strip .more-link {
  display: inline-block;
  margin-top: 1rem;
  font-weight: 700;
  text-decoration: none;
  color: var(--ink);
}
.preview-strip .more-link:hover { color: var(--muted); }

/* —— search page —— */
.search-hero { padding: 1.75rem 0 1rem; }
.search-hero h1 {
  margin: 0 0 1rem;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: clamp(1.85rem, 4vw, 2.6rem);
  letter-spacing: -0.03em;
}
.search-box input {
  width: 100%;
  font: inherit;
  font-size: 1.15rem;
  font-weight: 550;
  padding: 1rem 1.15rem;
  border: 1.5px solid var(--ink);
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(8px);
  color: var(--ink);
  outline: none;
  transition: border-color 0.2s, box-shadow 0.25s;
}
.search-box input:focus {
  border-color: var(--ink);
  box-shadow: 0 0 0 3px rgba(23,24,28,0.12);
}
.search-box .hint { margin: 0.5rem 0 0; color: var(--muted); font-size: 0.88rem; }
#search-results {
  display: none;
  margin: 1.25rem 0 2rem;
  border-top: 1px solid var(--line);
}
#search-results.visible { display: block; }
#search-results h2 {
  font-family: var(--font-display);
  font-size: 1.1rem;
  margin: 1rem 0 0.5rem;
}
#search-results ul { list-style: none; margin: 0; padding: 0; }
#search-results li {
  padding: 0.7rem 0;
  border-top: 1px solid var(--line);
}
#search-results .team-line { display: block; color: var(--muted); font-size: 0.9rem; }
.toolbar { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 1rem 0; }
.toolbar button {
  font-family: var(--font-body);
  font-size: 0.85rem;
  font-weight: 650;
  padding: 0.45rem 0.85rem;
  border: 1px solid var(--line);
  background: var(--surface);
  cursor: pointer;
}
.toolbar button:hover { border-color: var(--ink); }
.league-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem 1.1rem;
  margin: 1rem 0 1.4rem;
  font-size: 0.92rem;
  font-weight: 600;
}
.league-nav a { text-decoration: none; color: var(--ink); }
.league-nav .league-ext { color: var(--muted); text-decoration: none; margin-left: 0.15rem; }
details.league {
  border-top: 1px solid var(--line);
  padding: 0.35rem 0 0.6rem;
  background: transparent;
}
details.league > summary {
  cursor: pointer;
  list-style: none;
  padding: 0.7rem 0;
  font-family: var(--font-body);
  font-size: 1rem;
  font-weight: 550;
  letter-spacing: -0.01em;
  color: var(--ink);
}
details.league > summary::-webkit-details-marker { display: none; }
details.league > summary::before {
  content: "+";
  display: inline-block;
  width: 1.1rem;
  color: var(--muted);
  font-family: var(--font-body);
  font-weight: 500;
}
details.league[open] > summary::before { content: "–"; }
a.league-link, span.league-link {
  font-weight: 550;
  color: inherit;
}
details.team {
  border-top: 1px solid var(--line);
  padding: 0.2rem 0;
}
details.team summary {
  cursor: pointer;
  list-style: none;
  padding: 0.45rem 0;
  font-weight: 650;
}
details.team summary::-webkit-details-marker { display: none; }
.fav-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 1.05rem;
  color: #9aa3b5;
  padding: 0 0.3rem 0 0;
}
.fav-btn.is-fav { color: var(--heat); }
ul.players {
  columns: 2;
  column-gap: 1.5rem;
  padding-left: 1rem;
  margin: 0.35rem 0 0.7rem;
}
@media (max-width: 640px) {
  ul.players { columns: 1; }
  .hero-orb { opacity: 0.45; width: 55vw; top: 4%; }
  .feed-item { grid-template-columns: 1fr; }
}
ul.players li { break-inside: avoid; margin: 0.2rem 0; }
.dual-tag { font-weight: 500; }
ul.dual-list { padding-left: 1.1rem; margin: 0.35rem 0 0.9rem; }
h3.dual-league {
  font-family: var(--font-display);
  font-size: 1.05rem;
  margin: 1.25rem 0 0.45rem;
  letter-spacing: -0.02em;
  border-bottom: 1px solid var(--line);
  padding-bottom: 0.25rem;
}
.dual-club h4 { margin: 0.75rem 0 0.25rem; font-size: 1rem; }
#browse.hidden { display: none; }
#scrape-warn {
  color: #9a2b0a;
  background: rgba(255,77,26,0.1);
  border: 1px solid rgba(255,77,26,0.35);
  padding: 0.55rem 0.8rem;
  margin: 0.75rem 0;
}
.site-footer {
  margin-top: 3rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.88rem;
}
"""

FONTS_LINK = (
    'https://fonts.googleapis.com/css2?'
    'family=Manrope:wght@400;500;600;700;800&display=swap'
)


def _nav(active: str) -> str:
    def item(href, label, key):
        cur = ' aria-current="page"' if key == active else ''
        return f'<a href="{href}"{cur}>{label}</a>'

    return f"""
<header class="topnav">
  <a class="brand-mark" href="index.html">KZS</a>
  <nav class="links" aria-label="Glavna">
    {item('index.html', 'Domov', 'home')}
    {item('spremembe.html', 'Spremembe', 'changes')}
    {item('iskanje.html', 'Iskanje', 'search')}
  </nav>
</header>
"""


def _doc(title: str, body: str, extra_head: str = '', active: str = 'home') -> str:
    return f"""<!DOCTYPE html>
<html lang="sl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#f2f3f5">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS_LINK}" rel="stylesheet">
<style>
{SITE_CSS}
</style>
{extra_head}
</head>
<body>
<div class="shell">
{_nav(active)}
{body}
</div>
<script>
(function(){{
  const mark = (el) => el.classList.add('in');
  const visible = (el) => {{
    const r = el.getBoundingClientRect();
    return r.top < (window.innerHeight * 0.95) && r.bottom > 0;
  }};
  const nodes = [...document.querySelectorAll('.rise')];
  nodes.forEach((el, i) => {{
    el.style.transitionDelay = Math.min(i * 0.035, 0.45) + 's';
  }});
  // Takoj pokaži kar je že na zaslonu (brez čakanja na IO)
  nodes.filter(visible).forEach(mark);
  if ('IntersectionObserver' in window) {{
    const io = new IntersectionObserver((entries) => {{
      entries.forEach(e => {{
        if (e.isIntersecting) {{ mark(e.target); io.unobserve(e.target); }}
      }});
    }}, {{ threshold: 0.08, rootMargin: '0px 0px -4% 0px' }});
    nodes.filter(el => !el.classList.contains('in')).forEach(el => io.observe(el));
  }} else {{
    nodes.forEach(mark);
  }}
}})();
</script>
</body>
</html>
"""


def _parse_day(iso_ts: str):
    if not iso_ts:
        return None
    try:
        return datetime.fromisoformat(str(iso_ts).replace('Z', '+00:00')).date()
    except ValueError:
        return None


def _day_label(d: date, today: date) -> str:
    if d == today:
        return 'Danes'
    if (today - d).days == 1:
        return 'Včeraj'
    months = (
        '', 'januar', 'februar', 'marec', 'april', 'maj', 'junij',
        'julij', 'avgust', 'september', 'oktober', 'november', 'december',
    )
    return f'{d.day}. {months[d.month]} {d.year}'


def _fan_days(history_entries, team_links=None, team_links_league=None):
    """Združi fan spremembe po dnevih (najnovejši dan prvi)."""
    from html_report import FAN_TYPES, TYPE_LABELS, _change_html, _format_ts_short, _esc

    buckets: OrderedDict[str, dict] = OrderedDict()
    # walk newest first
    for entry in reversed(list(history_entries or [])):
        ts = entry.get('ts')
        day = _parse_day(ts)
        key = day.isoformat() if day else (str(ts)[:10] or 'unknown')
        if key not in buckets:
            buckets[key] = {'date': day, 'items': []}
        for change in entry.get('changes') or []:
            t = change.get('type')
            if t not in FAN_TYPES:
                continue
            full = _change_html(change, team_links, team_links_league)
            inner = full[4:-5] if full.startswith('<li>') and full.endswith('</li>') else full
            # tint badge for prestop
            if t == 'prestop':
                inner = inner.replace(
                    "class='badge'",
                    "class='badge' data-kind='prestop'",
                    1,
                )
            when = _format_ts_short(ts)
            buckets[key]['items'].append({
                'type': t,
                'html': (
                    f"<li class='feed-item rise' data-filter='{_esc(t)}'>"
                    f"<div class='body'>{inner}</div>"
                    f"<span class='when'>{_esc(when)}</span>"
                    f"</li>"
                ),
            })

    today = date.today()
    # OrderedDict insertion was newest-first walk → already newest first if we insert on first see
    # But first-seen while walking newest→oldest means newest days first. Good.
    # Within a day, items were appended in entry order (newest entry first, then its changes).
    days = []
    for key, bucket in buckets.items():
        d = bucket['date']
        label = _day_label(d, today) if d else key
        days.append({
            'key': key,
            'label': label,
            'count': len(bucket['items']),
            'items_html': ''.join(it['html'] for it in bucket['items']),
        })
    return days


def _hero_svg() -> str:
    return """
<svg class="hero-stage" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
  <path class="court-line" d="M80 720 H1120 V80 H80 Z"/>
  <path class="court-accent" d="M600 720 V80"/>
  <circle class="court-line" cx="600" cy="400" r="90"/>
  <path class="court-accent" d="M80 280 H280 V520 H80"/>
  <path class="court-accent" d="M1120 280 H920 V520 H1120"/>
  <circle class="court-line" cx="180" cy="400" r="55"/>
  <circle class="court-line" cx="1020" cy="400" r="55"/>
</svg>
"""


def write_home(days, scrape_iso: str) -> str:
    preview_items = []
    if days:
        # first day, up to 5
        from html_report import _esc, _format_ts_short
        # reuse rendered items from first day — strip rise delay overload
        raw = days[0]['items_html']
        # take first 5 feed-item blocks roughly via split
        parts = raw.split("</li>")
        preview_items = [p + '</li>' for p in parts[:5] if p.strip()]
        preview = ''.join(preview_items).replace(" class='feed-item rise'", " class='feed-item rise'")
    else:
        preview = '<li class="meta">Še ni registracij.</li>'

    when = ''
    try:
        from html_report import _format_ts_short, _esc
        when = _esc(_format_ts_short(scrape_iso))
    except Exception:
        when = scrape_iso

    n_today = days[0]['count'] if days else 0
    body = f"""
<section class="hero">
  {_hero_svg()}
  <div class="hero-orb" aria-hidden="true"></div>
  <div class="hero-copy">
    <p class="brand-xl">KZS</p>
    <h1 class="rise">Kdo se je pravkar registriral?</h1>
    <p class="lede rise">Živa sled novih igralcev in prestopov v slovenski košarki.</p>
    <div class="cta-row rise">
      <a class="btn" href="spremembe.html">Zadnje spremembe</a>
      <a class="btn btn-ghost" href="iskanje.html">Išči igralca</a>
    </div>
  </div>
</section>

<section class="preview-strip rise">
  <h2><span class="live-dot" aria-hidden="true"></span>
    Danes · {n_today} registracij
    <span class="meta"> · posodobljeno {when}</span>
  </h2>
  <ul class="feed-list">
    {preview}
  </ul>
  <a class="more-link" href="spremembe.html">Vse spremembe →</a>
</section>

<footer class="site-footer">Neuradni pregled registracij · vir podatkov KZS</footer>
"""
    return _doc('KZS – registracije', body, active='home')


def write_changes(days, scrape_iso: str) -> str:
    from html_report import _esc, _format_ts_short

    panels = []
    for i, day in enumerate(days):
        hidden = ' hidden' if i > 0 else ''
        panels.append(
            f"""
<section class="day-block" data-day-index="{i}"{hidden}>
  <h2 class="day-label rise">{_esc(day['label'])}
    <span class="count">{day['count']} sprememb</span>
  </h2>
  <ul class="feed-list">
    {day['items_html'] or '<li class="meta">Ni registracij.</li>'}
  </ul>
</section>
"""
        )

    load_btn = ''
    if len(days) > 1:
        load_btn = """
<button type="button" class="btn btn-load" id="btn-load-more">
  Naloži prejšnji dan
</button>
"""

    when = _esc(_format_ts_short(scrape_iso))
    body = f"""
<div class="page-head">
  <h1 class="rise">Zadnje spremembe</h1>
  <p class="sub rise">Novi igralci, prestopi in dodatne registracije · posodobljeno {when}</p>
</div>

<div class="filters rise" id="feed-filters">
  <button type="button" class="filter-btn active" data-filter="all">Vse</button>
  <button type="button" class="filter-btn" data-filter="nov_igralec,nov_igralec_dvojna">Novi</button>
  <button type="button" class="filter-btn" data-filter="prestop">Prestopi</button>
  <button type="button" class="filter-btn" data-filter="dodatna_registracija">Dodatne</button>
</div>

<div id="days">
{''.join(panels) if panels else '<p class="meta">Ni sprememb.</p>'}
</div>
{load_btn}

<footer class="site-footer"><a href="index.html">← Domov</a> · <a href="iskanje.html">Iskanje</a></footer>

<script>
(function(){{
  // day load-more
  let next = 1;
  const btn = document.getElementById('btn-load-more');
  const blocks = [...document.querySelectorAll('.day-block')];
  function revealNext() {{
    if (next >= blocks.length) return;
    const el = blocks[next];
    el.hidden = false;
    el.querySelectorAll('.rise').forEach((n,i) => {{
      n.classList.remove('in');
      n.style.transitionDelay = (i * 0.035) + 's';
      requestAnimationFrame(() => n.classList.add('in'));
    }});
    next += 1;
    if (btn) {{
      if (next >= blocks.length) {{
        btn.remove();
      }} else {{
        const label = blocks[next].querySelector('.day-label');
        const name = label ? label.childNodes[0].textContent.trim() : 'prejšnji dan';
        btn.textContent = 'Naloži še: ' + name;
      }}
    }}
  }}
  if (btn) {{
    if (blocks.length > 1) {{
      const label = blocks[1].querySelector('.day-label');
      const name = label ? label.childNodes[0].textContent.trim() : 'prejšnji dan';
      btn.textContent = 'Naloži še: ' + name;
    }}
    btn.addEventListener('click', revealNext);
  }}

  // filters
  document.querySelectorAll('#feed-filters .filter-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('#feed-filters .filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const keys = (btn.getAttribute('data-filter') || 'all').split(',');
      document.querySelectorAll('.feed-item').forEach(li => {{
        const t = li.getAttribute('data-filter');
        li.style.display = (keys[0] === 'all' || keys.includes(t)) ? '' : 'none';
      }});
    }});
  }});
}})();
</script>
"""
    return _doc('KZS – zadnje spremembe', body, active='changes')


def write_search(data, scrape_iso: str) -> str:
    from html_report import (
        CONFIG as CFG,
        _dual_grouped_by_club,
        _dual_registrations,
        _esc,
        _flatten_players,
        _format_ts_short,
        _league_anchor,
        _league_label,
        _league_url,
        _other_teams_by_player,
        _player_anchor,
        _team_anchor,
    )

    data = data or {}
    players = _flatten_players(data)
    dual = _dual_registrations(data)
    other_by_player = _other_teams_by_player(dual)
    total_teams = sum(len(teams) for teams in data.values())
    unique_players = len({p['id'] for p in players if p['id']})

    league_nav = []
    league_sections = []
    for league, teams in data.items():
        label = _league_label(league)
        lid = _esc(league)
        league_nav.append(
            f'<a href="#liga-{lid}">{_esc(label)}</a>'
            f' <a class="league-ext" href="{_esc(_league_url(league))}" '
            f'target="_blank" rel="noopener" title="Odpri na KZS">↗</a>'
        )
        team_blocks = []
        for team in sorted(teams, key=lambda t: (t.get('name') or '').lower()):
            tid = team.get('team_id') or ''
            tid_esc = _esc(tid)
            tname = team.get('name') or ''
            tlink = team.get('link') or ''
            coach = (team.get('coach') or {}).get('name')
            coach_html = (
                f"<p class='meta'>Trener: {_esc(coach)}</p>" if coach else ''
            )
            player_lis = []
            for player in sorted(
                team.get('players') or [], key=lambda p: (p.get('name') or '').lower()
            ):
                pid = str(player.get('player_id') or '')
                line = _player_anchor(player.get('name'), pid)
                others = [
                    t for t in other_by_player.get(pid, [])
                    if t.get('team_id') != tid
                ]
                if others:
                    other_html = ', '.join(
                        _team_anchor(
                            t['name'],
                            t.get('link'),
                            t.get('team_id'),
                            t.get('competition_id'),
                        )
                        for t in others
                    )
                    line += f" <span class='meta dual-tag'>({other_html})</span>"
                player_lis.append(f'<li>{line}</li>')
            players_ul = (
                f"<ul class='players'>{''.join(player_lis)}</ul>"
                if player_lis
                else "<p class='meta'>Ni igralcev.</p>"
            )
            team_name_html = _team_anchor(
                tname,
                link=tlink,
                team_id=team.get('team_id'),
                competition_id=team.get('competition_id'),
            )
            team_blocks.append(
                f"""
<details class="team" id="ekipa-{tid_esc}" data-team-id="{tid_esc}" data-team="{_esc(tname.lower())}">
  <summary>
    <button type="button" class="fav-btn" data-team-id="{tid_esc}" title="Favorit" aria-label="Favorit">☆</button>
    {team_name_html}
    <span class="meta">({len(team.get('players') or [])})</span>
  </summary>
  {coach_html}
  {players_ul}
</details>
"""
            )
        league_sections.append(
            f"""
<details class="league" id="liga-{lid}">
  <summary>
    {_league_anchor(league, label)}
    <span class="meta">({len(teams)} ekip)</span>
  </summary>
  <div class="league-body">
  {''.join(team_blocks)}
  </div>
</details>
"""
        )

    dual_blocks = []
    current_league = None
    for group in _dual_grouped_by_club(dual):
        club = group['club']
        league = club.get('league')
        if league != current_league:
            current_league = league
            dual_blocks.append(
                f"<h3 class='dual-league'>{_league_anchor(league)}</h3>"
            )
        club_html = _team_anchor(
            club['name'],
            club.get('link'),
            club.get('team_id'),
            club.get('competition_id'),
        )
        lis = []
        for p in group['players']:
            others = ' · '.join(
                f"{_team_anchor(t['name'], t.get('link'), t.get('team_id'), t.get('competition_id'))}"
                f" <span class='meta'>({_esc(t['league_label'])})</span>"
                for t in p['others']
            )
            lis.append(
                f"<li>{_player_anchor(p['name'], p['id'])} → {others}</li>"
            )
        dual_blocks.append(
            f"<div class='dual-club'>"
            f"<h4>{club_html} "
            f"<span class='meta'>({len(group['players'])})</span></h4>"
            f"<ul class='dual-list'>{''.join(lis)}</ul>"
            f"</div>"
        )

    dual_section = ''
    if dual_blocks:
        dual_section = f"""
<details class="league" id="dvojne-registracije">
  <summary>
    <span class="league-link">Dvojne registracije</span>
    <span class="meta">({len(dual)} igralcev)</span>
  </summary>
  <div class="league-body">
  {''.join(dual_blocks)}
  </div>
</details>
"""

    players_json = json.dumps(players, ensure_ascii=False)
    when = _esc(_format_ts_short(scrape_iso))
    base = CFG['base_url']

    body = f"""
<div class="search-hero">
  <h1 class="rise">Iskanje</h1>
  <p class="meta rise">{total_teams} ekip · {unique_players} igralcev · {len(dual)} dvojnih · posodobljeno {when}</p>
  <p class="meta" id="scrape-warn" hidden></p>
</div>

<div class="search-box rise">
  <input type="search" id="q" placeholder="Ime, priimek, ekipa, liga…" autocomplete="off" autofocus>
  <p class="hint">☆ favorit · klik na ime odpre KZS</p>
</div>
<div id="search-results"></div>

<div class="toolbar rise">
  <button type="button" id="btn-open-leagues">Odpri lige</button>
  <button type="button" id="btn-close-leagues">Zapri lige</button>
</div>

<div id="browse">
  <section id="favorites" hidden>
    <h2 class="day-label">Favoriti</h2>
    <div id="favorites-body"></div>
  </section>
  <div class="league-nav rise">
    <a href="#dvojne-registracije">Dvojne ({len(dual)})</a>
    {''.join(league_nav)}
  </div>
  {dual_section}
  {''.join(league_sections)}
</div>

<footer class="site-footer"><a href="index.html">← Domov</a> · <a href="spremembe.html">Spremembe</a></footer>

<script id="player-data" type="application/json">{players_json}</script>
<script id="scrape-meta" type="application/json">{json.dumps({"iso": scrape_iso}, ensure_ascii=False)}</script>
<script>
(function () {{
  const data = JSON.parse(document.getElementById('player-data').textContent);
  const scrapeMeta = JSON.parse(document.getElementById('scrape-meta').textContent);
  const input = document.getElementById('q');
  const results = document.getElementById('search-results');
  const browse = document.getElementById('browse');
  const FAV_KEY = 'kzs-favorites';
  const BASE = '{base}';

  function fold(s) {{
    return (s || '').toString().toLowerCase()
      .normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').replace(/đ/g, 'd');
  }}
  function matches(row, tokens) {{
    const hay = fold([row.name, row.first, row.last, row.team, row.league, row.league_label, row.id].join(' '));
    return tokens.every(t => hay.includes(t));
  }}
  function escapeHtml(s) {{
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }}
  function render(list) {{
    if (!list.length) {{
      results.innerHTML = '<h2>Zadetki (0)</h2><p class="meta">Ni zadetkov.</p>';
      return;
    }}
    const items = list.slice(0, 80).map(r => {{
      const href = r.link || (BASE + '/igralec/' + r.id);
      const teamHtml = r.team_link
        ? '<a class="team" href="' + r.team_link + '" target="_blank" rel="noopener">' + escapeHtml(r.team) + '</a>'
        : escapeHtml(r.team);
      return '<li class="rise in"><a class="player" href="' + href + '" target="_blank" rel="noopener">' +
        escapeHtml(r.name) + '</a><span class="team-line">' + teamHtml +
        ' · ' + escapeHtml(r.league_label) + '</span></li>';
    }}).join('');
    const more = list.length > 80
      ? '<p class="meta">Prikazanih 80 / ' + list.length + '</p>' : '';
    results.innerHTML = '<h2>Zadetki (' + list.length + ')</h2><ul>' + items + '</ul>' + more;
  }}
  function runSearch() {{
    const raw = input.value.trim();
    if (!raw) {{
      results.classList.remove('visible');
      results.innerHTML = '';
      browse.classList.remove('hidden');
      return;
    }}
    const tokens = fold(raw).split(/\\s+/).filter(Boolean);
    results.classList.add('visible');
    browse.classList.add('hidden');
    render(data.filter(r => matches(r, tokens)));
  }}
  let timer = null;
  input.addEventListener('input', () => {{ clearTimeout(timer); timer = setTimeout(runSearch, 110); }});
  input.addEventListener('keydown', (e) => {{
    if (e.key === 'Enter') {{
      const first = results.querySelector('a.player');
      if (first) {{ e.preventDefault(); window.open(first.href, '_blank', 'noopener'); }}
    }}
  }});

  (function updateAge() {{
    const iso = scrapeMeta.iso;
    const warnEl = document.getElementById('scrape-warn');
    if (!iso) return;
    const then = new Date(iso);
    if (isNaN(then)) return;
    const hours = (Date.now() - then.getTime()) / 3600000;
    if (hours >= 26) {{
      warnEl.hidden = false;
      warnEl.textContent = 'Podatki so starejši od ~1 dneva – preveri, ali scraper teče.';
    }}
  }})();

  document.getElementById('btn-open-leagues').addEventListener('click', () => {{
    document.querySelectorAll('details.league').forEach(d => {{ d.open = true; }});
  }});
  document.getElementById('btn-close-leagues').addEventListener('click', () => {{
    document.querySelectorAll('details.league').forEach(d => {{ d.open = false; }});
  }});

  function loadFavs() {{
    try {{ return JSON.parse(localStorage.getItem(FAV_KEY) || '[]'); }}
    catch (e) {{ return []; }}
  }}
  function saveFavs(ids) {{ localStorage.setItem(FAV_KEY, JSON.stringify(ids)); }}
  function renderFavorites() {{
    const ids = loadFavs();
    const box = document.getElementById('favorites');
    const body = document.getElementById('favorites-body');
    body.innerHTML = '';
    document.querySelectorAll('.fav-btn').forEach(btn => {{
      const id = btn.getAttribute('data-team-id');
      btn.classList.toggle('is-fav', ids.includes(id));
      btn.textContent = ids.includes(id) ? '★' : '☆';
    }});
    if (!ids.length) {{ box.hidden = true; return; }}
    box.hidden = false;
    ids.forEach(id => {{
      const src = document.querySelector('details.team[data-team-id="' + id + '"]');
      if (!src) return;
      const clone = src.cloneNode(true);
      clone.id = 'fav-' + id;
      clone.open = true;
      body.appendChild(clone);
    }});
  }}
  document.addEventListener('click', (e) => {{
    const btn = e.target.closest('.fav-btn');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    const id = btn.getAttribute('data-team-id');
    let ids = loadFavs();
    if (ids.includes(id)) ids = ids.filter(x => x !== id);
    else ids.push(id);
    saveFavs(ids);
    renderFavorites();
  }});
  renderFavorites();

  function openHash() {{
    const id = (location.hash || '').slice(1);
    if (!id) return;
    const el = document.getElementById(id);
    if (!el) return;
    if (el.tagName === 'DETAILS') el.open = true;
    el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
  }}
  window.addEventListener('hashchange', openHash);
  openHash();
}})();
</script>
"""
    return _doc('KZS – iskanje', body, active='search')


def write_public_pages(roster_data=None, history_entries=None, scrape_meta=None):
    """
    Zapiše index.html, spremembe.html, iskanje.html in zgodovina.html (redirect).
    """
    if not CONFIG.get('generate_html', True):
        return None

    from html_report import _team_links_map
    from storage import read_change_history, read_from_disc, read_last_scrape

    if roster_data is None:
        try:
            roster_data, _ = read_from_disc()
        except Exception:
            roster_data = {}

    scrape_meta = scrape_meta or read_last_scrape() or {}
    scrape_iso = scrape_meta.get('iso') or datetime.now().isoformat(timespec='seconds')

    if history_entries is None:
        history_entries = read_change_history(months_back=3)

    team_links, team_links_league = _team_links_map(roster_data)
    days = _fan_days(history_entries, team_links, team_links_league)

    HTML_DIR.mkdir(parents=True, exist_ok=True)

    home = write_home(days, scrape_iso)
    changes = write_changes(days, scrape_iso)
    search = write_search(roster_data, scrape_iso)

    (HTML_DIR / 'index.html').write_text(home, encoding='utf-8')
    (HTML_DIR / 'spremembe.html').write_text(changes, encoding='utf-8')
    (HTML_DIR / 'iskanje.html').write_text(search, encoding='utf-8')

    # Back-compat: stara povezava zgodovina → spremembe
    (HTML_DIR / 'zgodovina.html').write_text(
        """<!DOCTYPE html>
<html lang="sl"><head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=spremembe.html">
<title>Preusmeritev…</title>
<link rel="canonical" href="spremembe.html">
</head><body>
<p><a href="spremembe.html">Naprej na spremembe</a></p>
</body></html>
""",
        encoding='utf-8',
    )

    logger.info('Javna stran posodobljena: index / spremembe / iskanje')
    print(f'🌐 HTML SITE: {HTML_DIR / "index.html"}')
    return str(HTML_DIR / 'index.html')
