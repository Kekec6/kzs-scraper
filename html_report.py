"""HTML poročila, pregled lig/ekip/igralcev in iskanje."""

import html
import json
import logging
from datetime import datetime
from pathlib import Path

from config import CONFIG, HTML_DIR, html_filename

logger = logging.getLogger('kzs')

TYPE_LABELS = {
    'nov_igralec': 'Nov igralec',
    'nov_igralec_dvojna': 'Nov igralec (dvojna reg.)',
    'prestop': 'Prestop',
    'dodatna_registracija': 'Dodatna registracija',
    'igralec_odsel': 'Igralec odšel',
    'nov_trener_v_ekipo': 'Nov trener',
    'trener_odsel_iz_ekipe': 'Trener odšel',
    'sprememba_trener': 'Sprememba trenerja',
}

# Kaj ljubitelji gledajo: kdo → kam (brez odhodov/trenerjev)
FAN_TYPES = frozenset({
    'nov_igralec',
    'nov_igralec_dvojna',
    'prestop',
    'dodatna_registracija',
})

LEAGUE_LABELS = {
    'liga-otp-banka': '1. SKL OTP Banka',
    '2-skl-za-moske': '2. SKL moški',
    '3-skl-za-moske': '3. SKL moški',
    '4-skl-za-moske': '4. SKL moški',
    '1-skl-za-zenske': '1. SKL ženske',
}

LEAGUE_ORDER = {
    'liga-otp-banka': 0,
    '2-skl-za-moske': 1,
    '3-skl-za-moske': 2,
    '4-skl-za-moske': 3,
    '1-skl-za-zenske': 4,
}

COMMON_CSS = """
  :root {
    --bg: #f6f3ee;
    --ink: #1c1917;
    --muted: #57534e;
    --accent: #0f766e;
    --card: #fffdf9;
    --line: #e7e5e4;
    --warn: #9a3412;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
    background:
      radial-gradient(circle at top left, #dceeea 0%, transparent 40%),
      linear-gradient(180deg, #f6f3ee, #efe8df);
    color: var(--ink);
    line-height: 1.45;
  }
  main { max-width: 960px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
  h1 { font-size: clamp(1.8rem, 4vw, 2.4rem); margin: 0 0 0.35rem; letter-spacing: -0.02em; }
  h2 { font-size: 1.15rem; margin: 1.4rem 0 0.6rem; color: var(--accent); }
  .sub { color: var(--muted); margin-bottom: 1.25rem; }
  a { color: var(--accent); }
  a.player {
    font-weight: 700;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  a.player:hover { color: #115e59; }
  a.team {
    font-weight: 600;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  a.team:hover { color: #115e59; }
  .meta { color: var(--muted); font-size: 0.92em; }
  .nav { margin-bottom: 1.25rem; font-family: ui-sans-serif, system-ui, sans-serif; font-size: 0.9rem; }
  .nav a { margin-right: 1rem; }
  .badge {
    display: inline-block;
    font-family: ui-sans-serif, system-ui, sans-serif;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    background: #ccfbf1;
    color: #115e59;
    padding: 0.15rem 0.4rem;
    margin-right: 0.35rem;
  }
"""


def _esc(value):
    return html.escape(str(value) if value is not None else '')


def _player_anchor(name, player_id, extra_class='player'):
    """Klikljivo ime → KZS profil."""
    if not player_id:
        return f'<strong>{_esc(name)}</strong>'
    href = f"{CONFIG['base_url']}/igralec/{_esc(player_id)}"
    cls = f' class="{extra_class}"' if extra_class else ''
    return f'<a{cls} href="{href}" target="_blank" rel="noopener">{_esc(name)}</a>'


def _team_anchor(name, link=None, team_id=None, competition_id=None):
    """Klikljivo ime ekipe → KZS stran ekipe."""
    href = link
    if not href and team_id:
        href = f"{CONFIG['base_url']}/ekipa/{team_id}"
        if competition_id:
            href += f'?tekmovanje={competition_id}'
    if not href:
        return _esc(name)
    return (
        f'<a class="team" href="{_esc(href)}" target="_blank" rel="noopener" '
        f'onclick="event.stopPropagation()">{_esc(name)}</a>'
    )


def _team_links_map(data):
    """{ime_ekipe: link} in {ime|liga: link} za lookup v poročilih."""
    by_name = {}
    by_name_league = {}
    for league, teams in (data or {}).items():
        for team in teams:
            name = team.get('name') or ''
            link = team.get('link') or ''
            if not link and team.get('team_id'):
                link = f"{CONFIG['base_url']}/ekipa/{team['team_id']}"
                if team.get('competition_id'):
                    link += f"?tekmovanje={team['competition_id']}"
            if name and link:
                by_name[name] = link
                by_name_league[f'{name}|{league}'] = link
    return by_name, by_name_league


def _resolve_team_link(name, team_links=None, team_links_league=None, competition=None):
    if not name:
        return None
    if competition and team_links_league:
        hit = team_links_league.get(f'{name}|{competition}')
        if hit:
            return hit
    if team_links:
        return team_links.get(name)
    return None


def _league_label(slug):
    return LEAGUE_LABELS.get(slug, slug)


def _league_url(slug):
    """KZS URL strani lige."""
    if not slug:
        return CONFIG['base_url']
    return CONFIG['url_template'].format(slug)


def _league_anchor(slug, label=None):
    """Klikljivo ime lige → KZS."""
    label = label or _league_label(slug)
    href = _league_url(slug)
    return (
        f'<a class="league-link" href="{_esc(href)}" target="_blank" rel="noopener" '
        f'onclick="event.stopPropagation()">{_esc(label)}</a>'
    )


def _change_html(change, team_links=None, team_links_league=None):
    t = change.get('type')
    label = TYPE_LABELS.get(t, t)
    name_link = _player_anchor(change.get('player_name'), change.get('player_id'))

    def team_a(name, competition=None):
        return _team_anchor(
            name,
            link=_resolve_team_link(
                name, team_links, team_links_league, competition
            ),
        )

    if t == 'nov_igralec':
        body = (
            f"{name_link} → {team_a(change.get('team'), change.get('competition'))} "
            f"<span class='meta'>({_esc(_league_label(change.get('competition')))})</span>"
        )
    elif t == 'prestop':
        old_parts = [team_a(n) for n in (change.get('old_teams') or [])]
        body = (
            f"{name_link}: {' / '.join(old_parts)} → "
            f"{team_a(change.get('new_team'))}"
        )
    elif t == 'dodatna_registracija':
        existing = ' / '.join(
            team_a(n) for n in (change.get('existing_teams') or [])
        )
        body = (
            f"{name_link}: + {team_a(change.get('new_team'))} "
            f"(poleg {existing})"
        )
    elif t == 'nov_igralec_dvojna':
        teams = ' / '.join(team_a(n) for n in (change.get('teams') or []))
        body = f"{name_link}: {teams}"
    elif t == 'igralec_odsel':
        olds = ' / '.join(team_a(n) for n in (change.get('old_teams') or []))
        body = f"{name_link} (prej: {olds})"
    elif t == 'sprememba_trener':
        body = (
            f"{team_a(change.get('team'), change.get('competition'))}: "
            f"{_esc(change.get('old_coach'))} → {_esc(change.get('new_coach'))}"
        )
    elif t in ('nov_trener_v_ekipo', 'trener_odsel_iz_ekipe'):
        body = (
            f"<strong>{_esc(change.get('coach_name'))}</strong> – "
            f"{team_a(change.get('team'), change.get('competition'))} "
            f"<span class='meta'>({_esc(_league_label(change.get('competition')))})</span>"
        )
    else:
        body = _esc(change)

    return f"<li><span class='badge'>{_esc(label)}</span> {body}</li>"


def _format_ts_short(iso_ts):
    """2026-09-22T08:09:05 → 22.09. 08:09"""
    if not iso_ts:
        return ''
    try:
        dt = datetime.fromisoformat(str(iso_ts).replace('Z', '+00:00'))
        return dt.strftime('%d.%m. %H:%M')
    except ValueError:
        return str(iso_ts)[:16]


def _fan_change_line(change, ts, team_links=None, team_links_league=None):
    """Ena vrstica za ljubitelje: kdo → klub (liga)."""
    t = change.get('type')
    if t not in FAN_TYPES:
        return ''
    label = TYPE_LABELS.get(t, t)
    # Reuse _change_html body (strip outer <li>…</li>)
    full = _change_html(change, team_links, team_links_league)
    # full = <li><span class='badge'>…</span> BODY</li>
    if full.startswith('<li>') and full.endswith('</li>'):
        inner = full[4:-5]
    else:
        inner = full
    when = _format_ts_short(ts)
    return (
        f"<li class='feed-item' data-filter='{_esc(t)}'>"
        f"{inner}"
        f"<span class='when'>{_esc(when)}</span>"
        f"</li>"
    )


def _recent_fan_feed(history_entries, team_links=None, team_links_league=None, limit=80):
    """Zadnji registracije/prestopi iz JSONL (najnovejši najprej)."""
    rows = []
    for entry in reversed(history_entries or []):
        ts = entry.get('ts')
        for change in entry.get('changes') or []:
            line = _fan_change_line(change, ts, team_links, team_links_league)
            if line:
                rows.append(line)
            if len(rows) >= limit:
                return rows
    return rows


def _dual_registrations(data):
    """Igralci na več ekipah: [{id, name, teams:[{name,link,league,league_label}]}]"""
    by_id = {}
    for league, teams in (data or {}).items():
        for team in teams:
            team_info = {
                'name': team.get('name') or '',
                'link': team.get('link') or '',
                'team_id': team.get('team_id') or '',
                'competition_id': team.get('competition_id') or '',
                'league': league,
                'league_label': _league_label(league),
            }
            if not team_info['link'] and team_info['team_id']:
                team_info['link'] = f"{CONFIG['base_url']}/ekipa/{team_info['team_id']}"
                if team_info['competition_id']:
                    team_info['link'] += f"?tekmovanje={team_info['competition_id']}"

            for player in team.get('players') or []:
                pid = str(player.get('player_id') or '')
                if not pid:
                    continue
                if pid not in by_id:
                    by_id[pid] = {
                        'id': pid,
                        'name': player.get('name') or '',
                        'teams': [],
                    }
                if not any(t['team_id'] == team_info['team_id'] for t in by_id[pid]['teams']):
                    by_id[pid]['teams'].append(team_info)

    dual = [p for p in by_id.values() if len(p['teams']) > 1]
    for p in dual:
        p['teams'].sort(
            key=lambda t: (
                LEAGUE_ORDER.get(t.get('league'), 99),
                (t.get('name') or '').lower(),
            )
        )
    dual.sort(key=lambda p: (p['name'] or '').lower())
    return dual


def _dual_grouped_by_club(dual):
    """
    Razvrsti dvojne registracije po klubih (primarna = najvišja liga).
    Znotraj kluba: najprej po sekundarni ekipi, nato po imenu igralca.
    """
    groups = {}
    for player in dual:
        teams = player.get('teams') or []
        if len(teams) < 2:
            continue
        primary = teams[0]
        key = primary.get('team_id') or primary.get('name')
        if key not in groups:
            groups[key] = {'club': primary, 'players': []}
        others = [t for t in teams if t.get('team_id') != primary.get('team_id')]
        groups[key]['players'].append({
            'id': player['id'],
            'name': player['name'],
            'others': others,
        })

    ordered = sorted(
        groups.values(),
        key=lambda g: (
            LEAGUE_ORDER.get(g['club'].get('league'), 99),
            (g['club'].get('name') or '').lower(),
        ),
    )
    for g in ordered:
        g['players'].sort(
            key=lambda p: (
                ','.join((t.get('name') or '').lower() for t in p['others']),
                (p['name'] or '').lower(),
            )
        )
    return ordered


def _other_teams_by_player(dual):
    """
    {player_id: [team_info, ...]} – vse ekipe igralca z dvojno registracijo.
    Za prikaz '(druga ekipa)' v pregledu ekip.
    """
    mapping = {}
    for player in dual:
        mapping[player['id']] = player.get('teams') or []
    return mapping


def _flatten_players(data):
    """Seznam igralcev za iskanje / JSON."""
    rows = []
    seen = set()
    for league, teams in (data or {}).items():
        league_label = _league_label(league)
        for team in teams:
            team_name = team.get('name') or ''
            team_id = team.get('team_id') or ''
            team_link = team.get('link') or ''
            if not team_link and team_id:
                team_link = f"{CONFIG['base_url']}/ekipa/{team_id}"
                if team.get('competition_id'):
                    team_link += f"?tekmovanje={team['competition_id']}"
            for player in team.get('players') or []:
                pid = str(player.get('player_id') or '')
                name = player.get('name') or ''
                link = player.get('link') or (
                    f"{CONFIG['base_url']}/igralec/{pid}" if pid else ''
                )
                key = (pid, team_id)
                if key in seen:
                    continue
                seen.add(key)
                parts = name.split()
                rows.append({
                    'id': pid,
                    'name': name,
                    'first': parts[0] if parts else '',
                    'last': parts[-1] if len(parts) > 1 else '',
                    'team': team_name,
                    'team_id': team_id,
                    'team_link': team_link,
                    'league': league,
                    'league_label': league_label,
                    'link': link,
                })
    return rows


def generate_html_report(
    changes,
    total_teams=0,
    total_players=0,
    elapsed_time=0,
    scrape_failures=None,
    dry_run=False,
    roster_data=None,
):
    """Ustvari HTML poročilo o spremembah. Vrne pot ali None."""
    scrape_failures = scrape_failures or []
    changes = changes or []

    if not CONFIG.get('generate_html', True):
        return None

    if not changes and not scrape_failures:
        logger.info('Ni vsebine za HTML poročilo sprememb')
        return None

    team_links, team_links_league = _team_links_map(roster_data)

    path = Path(html_filename())
    if dry_run:
        path = path.with_name(path.stem + '_dryrun' + path.suffix)

    now = datetime.now().strftime('%d.%m.%Y %H:%M')
    grouped = {}
    for change in changes:
        grouped.setdefault(change.get('type'), []).append(change)

    sections = []
    for type_key, items in grouped.items():
        label = TYPE_LABELS.get(type_key, type_key)
        lis = '\n'.join(
            _change_html(c, team_links, team_links_league) for c in items
        )
        sections.append(
            f"<section class='change-block' data-filter='{_esc(type_key)}'>"
            f"<h2>{_esc(label)} ({len(items)})</h2><ul>{lis}</ul></section>"
        )

    filter_btns = [
        '<button type="button" class="filter-btn active" data-filter="all">Vse</button>',
        '<button type="button" class="filter-btn" data-filter="prestop">Prestopi</button>',
        '<button type="button" class="filter-btn" data-filter="nov_igralec,nov_igralec_dvojna,dodatna_registracija">Novi / reg.</button>',
        '<button type="button" class="filter-btn" data-filter="igralec_odsel">Odhodi</button>',
        '<button type="button" class="filter-btn" data-filter="sprememba_trener,nov_trener_v_ekipo,trener_odsel_iz_ekipe">Trenerji</button>',
    ]

    failures_html = ''
    if scrape_failures:
        flis = []
        for f in scrape_failures:
            team_name = f.get('team')
            flis.append(
                f"<li>{_team_anchor(team_name, _resolve_team_link(team_name, team_links, team_links_league, f.get('competition')))} "
                f"({_esc(_league_label(f.get('competition')))}): {_esc(f.get('reason'))} "
                f"[prej {f.get('old_player_count', 0)} igralcev]</li>"
            )
        failures_html = (
            f"<section class='warn'><h2>Tehnične napake ({len(scrape_failures)})</h2>"
            f"<p>Za te ekipe so obdržani stari podatki.</p><ul>{''.join(flis)}</ul></section>"
        )

    dry_banner = (
        '<p class="dry">DRY-RUN – podatki niso shranjeni</p>' if dry_run else ''
    )

    content = f"""<!DOCTYPE html>
<html lang="sl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KZS prestopi – {now}</title>
<style>
{COMMON_CSS}
  .stats {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 0.75rem;
    margin: 1.25rem 0 2rem;
  }}
  .stat {{
    background: var(--card);
    border: 1px solid var(--line);
    padding: 0.9rem 1rem;
  }}
  .stat b {{ display: block; font-size: 1.35rem; color: var(--accent); }}
  section {{
    background: var(--card);
    border: 1px solid var(--line);
    padding: 1rem 1.1rem 0.4rem;
    margin-bottom: 1rem;
  }}
  section.warn {{ border-color: #fdba74; }}
  .filters {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 1rem; }}
  .filters button {{
    font-family: ui-sans-serif, system-ui, sans-serif;
    font-size: 0.82rem;
    padding: 0.35rem 0.65rem;
    border: 1px solid var(--line);
    background: var(--card);
    cursor: pointer;
  }}
  .filters button.active {{ background: #ccfbf1; border-color: var(--accent); }}
  ul {{ padding-left: 1.1rem; margin: 0 0 1rem; }}
  li {{ margin: 0.45rem 0; }}
  .dry {{
    background: #fff7ed;
    border: 1px solid #fed7aa;
    padding: 0.6rem 0.8rem;
    color: var(--warn);
  }}
  footer {{ margin-top: 2rem; color: var(--muted); font-size: 0.9rem; }}
</style>
</head>
<body>
<main>
  <nav class="nav">
    <a href="index.html">Domov</a>
    <a href="spremembe.html">Spremembe</a>
    <a href="iskanje.html">Iskanje</a>
  </nav>
  <h1>KZS – spremembe</h1>
  <p class="sub">Generirano {_esc(now)}</p>
  {dry_banner}
  <div class="stats">
    <div class="stat"><span>Ekipe</span><b>{total_teams}</b></div>
    <div class="stat"><span>Igralci</span><b>{total_players}</b></div>
    <div class="stat"><span>Spremembe</span><b>{len(changes)}</b></div>
    <div class="stat"><span>Scrape napake</span><b>{len(scrape_failures)}</b></div>
    <div class="stat"><span>Čas</span><b>{elapsed_time:.0f}s</b></div>
  </div>
  <div class="filters" id="change-filters">
    {''.join(filter_btns)}
  </div>
  {failures_html}
  <div id="change-blocks">
  {''.join(sections) if sections else '<p>Ni zaznanih pravih sprememb.</p>'}
  </div>
  <footer>
    <a href="spremembe.html">← Spremembe</a> · <a href="iskanje.html">Iskanje</a>
  </footer>
</main>
<script>
(function() {{
  const btns = document.querySelectorAll('#change-filters .filter-btn');
  const blocks = document.querySelectorAll('.change-block');
  btns.forEach(btn => btn.addEventListener('click', () => {{
    btns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const keys = (btn.getAttribute('data-filter') || 'all').split(',');
    blocks.forEach(block => {{
      const t = block.getAttribute('data-filter');
      block.style.display = (keys[0] === 'all' || keys.includes(t)) ? '' : 'none';
    }});
  }}));
}})();
</script>
</body>
</html>
"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    logger.info(f'HTML poročilo ustvarjeno: {path}')
    print(f'🌐 HTML POROČILO: {path}')
    return str(path)


def generate_roster_html(data, scrape_meta=None):
    """Javna stran: domov + iskanje + spremembe."""
    from html_site import write_public_pages
    return write_public_pages(roster_data=data, scrape_meta=scrape_meta)


def update_html_index(history_entries=None, roster_data=None):
    """Osveži javno stran (feed + iskanje + domov)."""
    from html_site import write_public_pages
    from storage import read_from_disc

    if roster_data is None:
        try:
            roster_data, _ = read_from_disc()
        except Exception:
            roster_data = None
    return write_public_pages(
        roster_data=roster_data,
        history_entries=history_entries,
    )
