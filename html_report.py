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
    <a href="index.html">Pregled / iskanje</a>
    <a href="zgodovina.html">Zgodovina</a>
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
    <a href="index.html">← Nazaj na pregled</a> · KZS Scraper
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
    """
    Glavni HTML: iskanje + sprehod liga → ekipa → igralci.
    Piše output/html/index.html
    """
    if not CONFIG.get('generate_html', True):
        return None

    from storage import read_last_scrape, read_change_history

    data = data or {}
    scrape_meta = scrape_meta or read_last_scrape() or {}
    scrape_iso = scrape_meta.get('iso') or datetime.now().isoformat(timespec='seconds')
    players = _flatten_players(data)
    dual = _dual_registrations(data)
    other_by_player = _other_teams_by_player(dual)
    total_teams = sum(len(teams) for teams in data.values())
    # unikatni igralci (ne vrstice ekipa×igralec)
    unique_players = len({p['id'] for p in players if p['id']})

    team_links, team_links_league = _team_links_map(data)
    fan_rows = _recent_fan_feed(
        read_change_history(months_back=3),
        team_links,
        team_links_league,
        limit=60,
    )
    fan_list = (
        ''.join(fan_rows)
        if fan_rows
        else '<li class="meta">Še ni registracij v zgodovini.</li>'
    )
    # Navigacija po ligah
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
                # Druge ekipe pri dvojni registraciji (v oklepaju)
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
    <button type="button" class="fav-btn" data-team-id="{tid_esc}" title="Dodaj med favorite" aria-label="Favorit">☆</button>
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
<details class="league dual" id="dvojne-registracije">
  <summary>
    <span class="league-link">Dvojne registracije</span>
    <span class="meta">({len(dual)} igralcev)</span>
  </summary>
  <div class="league-body">
  <p class="meta">Razvrščeno po ligah in klubih. Puščica kaže dodatne registracije.</p>
  {''.join(dual_blocks)}
  </div>
</details>
"""

    players_json = json.dumps(players, ensure_ascii=False)

    content = f"""<!DOCTYPE html>
<html lang="sl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KZS registracije</title>
<style>
{COMMON_CSS}
  .search-box {{
    position: sticky;
    top: 0;
    z-index: 5;
    background: rgba(246, 243, 238, 0.95);
    backdrop-filter: blur(6px);
    padding: 0.75rem 0 0.9rem;
    border-bottom: 1px solid var(--line);
    margin-bottom: 1.25rem;
  }}
  .search-box input {{
    width: 100%;
    font: inherit;
    font-size: 1.05rem;
    padding: 0.7rem 0.9rem;
    border: 1px solid var(--line);
    background: var(--card);
    color: var(--ink);
  }}
  .search-box input:focus {{
    outline: 2px solid #99f6e4;
    border-color: var(--accent);
  }}
  .hint {{ font-size: 0.88rem; color: var(--muted); margin: 0.4rem 0 0; }}
  #search-results {{
    display: none;
    background: var(--card);
    border: 1px solid var(--line);
    margin-bottom: 1.5rem;
    max-height: 420px;
    overflow: auto;
  }}
  #search-results.visible {{ display: block; }}
  #search-results h2 {{ margin: 0.8rem 1rem 0.4rem; }}
  #search-results ul {{ list-style: none; padding: 0; margin: 0; }}
  #search-results li {{
    border-top: 1px solid var(--line);
    padding: 0.55rem 1rem;
  }}
  #search-results li .team-line {{ display: block; font-size: 0.9rem; color: var(--muted); }}
  .league-nav {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
    margin-bottom: 1.25rem;
    font-family: ui-sans-serif, system-ui, sans-serif;
    font-size: 0.9rem;
    align-items: baseline;
  }}
  .league-nav .league-ext {{
    margin-left: -0.65rem;
    margin-right: 0.35rem;
    text-decoration: none;
    font-size: 0.85rem;
  }}
  .stats {{
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    color: var(--muted);
    margin-bottom: 1rem;
    font-size: 0.95rem;
  }}
  .toolbar {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }}
  .toolbar button, .filters button {{
    font-family: ui-sans-serif, system-ui, sans-serif;
    font-size: 0.85rem;
    padding: 0.4rem 0.75rem;
    border: 1px solid var(--line);
    background: var(--card);
    color: var(--ink);
    cursor: pointer;
  }}
  .toolbar button:hover, .filters button:hover {{ border-color: var(--accent); }}
  .filters button.active {{
    background: #ccfbf1;
    border-color: var(--accent);
    color: #115e59;
  }}
  .fav-btn {{
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: 1.1rem;
    line-height: 1;
    padding: 0 0.25rem 0 0;
    color: #a8a29e;
  }}
  .fav-btn.is-fav {{ color: #ca8a04; }}
  #scrape-warn {{
    color: var(--warn);
    background: #fff7ed;
    border: 1px solid #fed7aa;
    padding: 0.5rem 0.75rem;
  }}
  details.league {{
    background: var(--card);
    border: 1px solid var(--line);
    padding: 0.4rem 1rem 0.5rem;
    margin-bottom: 0.75rem;
  }}
  details.league > summary {{
    cursor: pointer;
    list-style: none;
    padding: 0.55rem 0;
    font-size: 1.15rem;
    color: var(--accent);
  }}
  details.league > summary::-webkit-details-marker {{ display: none; }}
  details.league > summary::before {{
    content: "▸ ";
    color: var(--accent);
    font-family: ui-sans-serif, system-ui, sans-serif;
  }}
  details.league[open] > summary::before {{ content: "▾ "; }}
  a.league-link {{
    font-weight: 700;
    text-decoration: underline;
    text-underline-offset: 2px;
    color: var(--accent);
  }}
  .league-body {{ padding-bottom: 0.4rem; }}
  details.team {{
    border-top: 1px solid var(--line);
    padding: 0.35rem 0;
  }}
  details.team:first-of-type {{ border-top: none; }}
  details.team summary {{
    cursor: pointer;
    list-style: none;
    padding: 0.35rem 0;
  }}
  details.team summary::-webkit-details-marker {{ display: none; }}
  details.team summary::before {{
    content: "▸ ";
    color: var(--accent);
    font-family: ui-sans-serif, system-ui, sans-serif;
  }}
  details.team[open] summary::before {{ content: "▾ "; }}
  ul.players {{
    columns: 2;
    column-gap: 1.5rem;
    padding-left: 1rem;
    margin: 0.4rem 0 0.6rem;
  }}
  @media (max-width: 640px) {{
    ul.players {{ columns: 1; }}
  }}
  ul.players li {{ break-inside: avoid; margin: 0.2rem 0; }}
  .dual-tag a.team {{ font-weight: 500; }}
  ul.dual-list {{ padding-left: 1.1rem; margin: 0.35rem 0 0.9rem; }}
  ul.dual-list li {{ margin: 0.4rem 0; }}
  h3.dual-league {{
    font-size: 1.08rem;
    margin: 1.35rem 0 0.5rem;
    color: var(--accent);
    border-bottom: 1px solid var(--line);
    padding-bottom: 0.25rem;
  }}
  h3.dual-league:first-child {{ margin-top: 0.5rem; }}
  .dual-club h4 {{
    font-size: 1.02rem;
    margin: 0.85rem 0 0.25rem;
    color: var(--ink);
  }}
  .dual-club:first-of-type h4 {{ margin-top: 0.35rem; }}
  .league.dual {{
    background: var(--card);
    border: 1px solid #99f6e4;
    padding: 0.75rem 1rem 1rem;
    margin-bottom: 1rem;
  }}
  #browse.hidden {{ display: none; }}
  footer {{ margin-top: 2rem; color: var(--muted); font-size: 0.9rem; }}
  section.feed {{
    background: var(--card);
    border: 1px solid var(--line);
    padding: 1rem 1.1rem 0.6rem;
    margin-bottom: 1.75rem;
  }}
  section.feed > h2 {{ margin-top: 0; }}
  ul.feed-list {{ list-style: none; padding: 0; margin: 0.5rem 0 0; }}
  li.feed-item {{
    border-top: 1px solid var(--line);
    padding: 0.65rem 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem 0.5rem;
    align-items: baseline;
  }}
  li.feed-item .when {{
    margin-left: auto;
    color: var(--muted);
    font-size: 0.88rem;
    font-family: ui-sans-serif, system-ui, sans-serif;
  }}
  .feed-filters {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.5rem 0 0.25rem; }}
</style>
</head>
<body>
<main>
  <nav class="nav">
    <a href="#zadnje">Zadnje registracije</a>
    <a href="#browse">Ekipe / iskanje</a>
    <a href="#dvojne-registracije">Dvojne registracije</a>
  </nav>
  <h1>KZS registracije</h1>
  <p class="sub">
    Kdo → kateri klub → liga · posodobljeno <strong id="scrape-when">{_esc(scrape_iso)}</strong>
    · <span id="scrape-age">računam…</span>
  </p>
  <p class="sub meta" id="scrape-warn" hidden></p>

  <section class="feed" id="zadnje">
    <h2>Zadnje registracije</h2>
    <p class="meta">Novi igralci, prestopi in dodatne registracije.</p>
    <div class="feed-filters filters" id="feed-filters">
      <button type="button" class="filter-btn active" data-filter="all">Vse</button>
      <button type="button" class="filter-btn" data-filter="nov_igralec,nov_igralec_dvojna">Novi</button>
      <button type="button" class="filter-btn" data-filter="prestop">Prestopi</button>
      <button type="button" class="filter-btn" data-filter="dodatna_registracija">Dodatne reg.</button>
    </div>
    <ul class="feed-list">
      {fan_list}
    </ul>
  </section>

  <div class="stats">
    <span>{total_teams} ekip</span>
    <span>{unique_players} igralcev</span>
    <span>{len(dual)} dvojnih registracij</span>
  </div>

  <div class="toolbar">
    <button type="button" id="btn-open-leagues">Odpri vse lige</button>
    <button type="button" id="btn-close-leagues">Zapri vse lige</button>
  </div>

  <div class="search-box">
    <input type="search" id="q" placeholder="Išči: ime, priimek, ekipa, liga…" autocomplete="off">
    <p class="hint">☆ = favorit (localStorage). Klik na igralca/ekipo/ligo → KZS.</p>
  </div>

  <div id="search-results"></div>

  <div id="browse">
    <section id="favorites" class="league dual" hidden>
      <h2>⭐ Favoriti</h2>
      <div id="favorites-body"></div>
    </section>
    <div class="league-nav">
      {''.join(league_nav)}
      <a href="#dvojne-registracije">Dvojne registracije ({len(dual)})</a>
    </div>
    {dual_section}
    {''.join(league_sections)}
  </div>

  <footer>
    Pregled ekip spodaj · podatki iz KZS scrapa
  </footer>
</main>

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

  function fold(s) {{
    return (s || '')
      .toString()
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\\u0300-\\u036f]/g, '')
      .replace(/đ/g, 'd');
  }}

  function matches(row, tokens) {{
    const hay = fold([
      row.name, row.first, row.last, row.team, row.league, row.league_label, row.id
    ].join(' '));
    return tokens.every(t => hay.includes(t));
  }}

  function escapeHtml(s) {{
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }}

  function render(list) {{
    if (!list.length) {{
      results.innerHTML = '<h2>Zadetki (0)</h2><p style="padding:0 1rem 1rem" class="meta">Ni zadetkov.</p>';
      return;
    }}
    const items = list.slice(0, 80).map(r => {{
      const href = r.link || ('{CONFIG["base_url"]}/igralec/' + r.id);
      const teamHref = r.team_link || '';
      const teamHtml = teamHref
        ? '<a class="team" href="' + teamHref + '" target="_blank" rel="noopener">' + escapeHtml(r.team) + '</a>'
        : escapeHtml(r.team);
      return '<li><a class="player" href="' + href + '" target="_blank" rel="noopener">' +
        escapeHtml(r.name) + '</a>' +
        '<span class="team-line">' + teamHtml +
        ' · ' + escapeHtml(r.league_label) + '</span></li>';
    }}).join('');
    const more = list.length > 80
      ? '<p class="meta" style="padding:0.5rem 1rem">Prikazanih 80 / ' + list.length + '</p>'
      : '';
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
    const found = data.filter(r => matches(r, tokens));
    results.classList.add('visible');
    browse.classList.add('hidden');
    render(found);
  }}

  let timer = null;
  input.addEventListener('input', () => {{
    clearTimeout(timer);
    timer = setTimeout(runSearch, 120);
  }});

  input.addEventListener('keydown', (e) => {{
    if (e.key === 'Enter') {{
      const first = results.querySelector('a.player');
      if (first) {{
        e.preventDefault();
        window.open(first.href, '_blank', 'noopener');
      }}
    }}
  }});

  // Starost podatkov
  (function updateAge() {{
    const iso = scrapeMeta.iso;
    const ageEl = document.getElementById('scrape-age');
    const warnEl = document.getElementById('scrape-warn');
    const whenEl = document.getElementById('scrape-when');
    if (!iso) return;
    const then = new Date(iso);
    if (isNaN(then)) return;
    const hours = (Date.now() - then.getTime()) / 3600000;
    let label;
    if (hours < 1) label = 'podatki stari ' + Math.round(hours * 60) + ' min';
    else if (hours < 48) label = 'podatki stari ' + hours.toFixed(1) + ' ur';
    else label = 'podatki stari ' + (hours / 24).toFixed(1) + ' dni';
    ageEl.textContent = label;
    whenEl.textContent = then.toLocaleString('sl-SI');
    if (hours >= 26) {{
      warnEl.hidden = false;
      warnEl.textContent = '⚠️ Podatki so starejši od ~1 dneva – preveri, ali cron teče.';
    }}
  }})();

  // Odpri / zapri lige
  document.getElementById('btn-open-leagues').addEventListener('click', () => {{
    document.querySelectorAll('details.league').forEach(d => {{ d.open = true; }});
  }});
  document.getElementById('btn-close-leagues').addEventListener('click', () => {{
    document.querySelectorAll('details.league').forEach(d => {{ d.open = false; }});
  }});

  // Favoriti
  function loadFavs() {{
    try {{ return JSON.parse(localStorage.getItem(FAV_KEY) || '[]'); }}
    catch (e) {{ return []; }}
  }}
  function saveFavs(ids) {{
    localStorage.setItem(FAV_KEY, JSON.stringify(ids));
  }}
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
    if (!ids.length) {{
      box.hidden = true;
      return;
    }}
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

  function openHashLeague() {{
    const id = (location.hash || '').slice(1);
    if (!id) return;
    const el = document.getElementById(id);
    if (!el) return;
    if (el.tagName === 'DETAILS') el.open = true;
    el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
  }}
  window.addEventListener('hashchange', openHashLeague);
  openHashLeague();

  // Filtri feeda registracij
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
</body>
</html>
"""

    path = HTML_DIR / 'index.html'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    logger.info(f'HTML pregled ekip/igralcev: {path}')
    print(f'🌐 HTML PREGLED: {path}')
    return str(path)


def update_html_index(history_entries=None, roster_data=None):
    """
    Ljubiteljska zgodovina = feed registracij (brez HTML poročil / scrape tabel).
    Posodobi tudi index.html, če je podan roster_data ali obstaja JSON.
    """
    from storage import read_change_history, read_from_disc, read_last_scrape

    if roster_data is not None:
        generate_roster_html(roster_data)
    else:
        # Osveži feed tudi na indexu, če imamo shranjene ekipe
        try:
            data, _ = read_from_disc()
            if data:
                generate_roster_html(data)
        except Exception:
            pass

    if history_entries is None:
        history_entries = read_change_history(months_back=3)

    team_links, team_links_league = {}, {}
    try:
        data_path = Path(CONFIG['json_file'])
        if data_path.exists():
            data = json.loads(data_path.read_text(encoding='utf-8'))
            team_links, team_links_league = _team_links_map(data)
    except Exception:
        pass

    fan_rows = _recent_fan_feed(
        history_entries, team_links, team_links_league, limit=120
    )
    scrape = read_last_scrape() or {}
    scrape_iso = scrape.get('iso') or ''

    history_path = HTML_DIR / 'zgodovina.html'
    history_path.write_text(
        f"""<!DOCTYPE html>
<html lang="sl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KZS – zadnje registracije</title>
<style>
{COMMON_CSS}
  .feed {{
    background: var(--card);
    border: 1px solid var(--line);
    padding: 1rem 1.1rem 0.6rem;
    margin-bottom: 1.5rem;
  }}
  ul.feed-list {{ list-style: none; padding: 0; margin: 0.5rem 0 0; }}
  li.feed-item {{
    border-top: 1px solid var(--line);
    padding: 0.65rem 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem 0.5rem;
    align-items: baseline;
  }}
  li.feed-item .when {{
    margin-left: auto;
    color: var(--muted);
    font-size: 0.88rem;
    font-family: ui-sans-serif, system-ui, sans-serif;
  }}
  .filters {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.6rem 0 0.4rem; }}
  .filters button {{
    font-family: ui-sans-serif, system-ui, sans-serif;
    font-size: 0.82rem;
    padding: 0.35rem 0.65rem;
    border: 1px solid var(--line);
    background: var(--card);
    cursor: pointer;
  }}
  .filters button.active {{ background: #ccfbf1; border-color: var(--accent); }}
</style>
</head>
<body>
<main>
  <nav class="nav">
    <a href="index.html">Domov</a>
    <a href="index.html#zadnje">Zadnje registracije</a>
  </nav>
  <h1>Zadnje registracije</h1>
  <p class="sub">Kdo → kateri klub → liga · posodobljeno {_esc(_format_ts_short(scrape_iso))}</p>

  <div class="filters" id="feed-filters">
    <button type="button" class="filter-btn active" data-filter="all">Vse</button>
    <button type="button" class="filter-btn" data-filter="nov_igralec,nov_igralec_dvojna">Novi</button>
    <button type="button" class="filter-btn" data-filter="prestop">Prestopi</button>
    <button type="button" class="filter-btn" data-filter="dodatna_registracija">Dodatne reg.</button>
  </div>

  <section class="feed">
    <ul class="feed-list">
      {''.join(fan_rows) if fan_rows else '<li class="meta">Ni registracij.</li>'}
    </ul>
  </section>
</main>
<script>
(function() {{
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
</body>
</html>
""",
        encoding='utf-8',
    )
    logger.info(f'HTML zgodovina (feed) posodobljena: {history_path}')
    return str(history_path)
