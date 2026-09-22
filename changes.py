"""Zaznavanje in izpis sprememb med starim in novim stanjem."""

import logging

from config import CONFIG

logger = logging.getLogger('kzs')


def get_all_players_with_teams(data):
    """Vrne slovar {player_id: [(team_name, team_id, competition)]} za vse igralce."""
    player_teams = {}
    for part, teams in data.items():
        for team in teams:
            for player in team.get('players') or []:
                player_id = player['player_id']
                if player_id not in player_teams:
                    player_teams[player_id] = []
                player_teams[player_id].append({
                    'team_name': team['name'],
                    'team_id': team['team_id'],
                    'competition': part,
                    'player_name': player['name'],
                })
    return player_teams


def get_all_coaches_with_teams(data):
    """Pridobi vse trenerje z njihovimi ekipami."""
    all_coaches = {}

    for competition, teams in data.items():
        for team in teams:
            coach = team.get('coach')
            if coach and coach.get('name'):
                coach_key = f"{coach['name']}#{team['team_id']}"
                all_coaches[coach_key] = {
                    'coach_name': coach['name'],
                    'team_name': team['name'],
                    'team_id': team['team_id'],
                    'competition': competition,
                    'position': coach.get('position', 'Glavni trener'),
                }

    return all_coaches


def detect_changes(old_data, new_data, scrape_failures=None):
    """
    Zaznaj spremembe. Ekipe z neuspešnim scrape-om so že obdržale stare podatke,
    zato ne generirajo lažnih 'igralec odšel' dogodkov.
    """
    scrape_failures = scrape_failures or []
    failed_team_ids = {f['team_id'] for f in scrape_failures}

    old_players = get_all_players_with_teams(old_data)
    new_players = get_all_players_with_teams(new_data)

    changes = []

    for player_id, new_teams in new_players.items():
        player_name = new_teams[0]['player_name']

        if player_id not in old_players:
            if len(new_teams) == 1:
                changes.append({
                    'type': 'nov_igralec',
                    'player_name': player_name,
                    'player_id': player_id,
                    'team': new_teams[0]['team_name'],
                    'competition': new_teams[0]['competition'],
                })
            else:
                changes.append({
                    'type': 'nov_igralec_dvojna',
                    'player_name': player_name,
                    'player_id': player_id,
                    'teams': [team['team_name'] for team in new_teams],
                    'competitions': [team['competition'] for team in new_teams],
                })
        else:
            old_teams = old_players[player_id]
            old_team_ids = {team['team_id'] for team in old_teams}
            new_team_ids = {team['team_id'] for team in new_teams}

            if old_team_ids != new_team_ids:
                added_teams = [t for t in new_teams if t['team_id'] not in old_team_ids]
                removed_teams = [t for t in old_teams if t['team_id'] not in new_team_ids]

                # Ne štej "odhod" z ekipe, ki je imela scrape failure
                removed_teams = [t for t in removed_teams if t['team_id'] not in failed_team_ids]

                if added_teams and not removed_teams:
                    for added_team in added_teams:
                        changes.append({
                            'type': 'dodatna_registracija',
                            'player_name': player_name,
                            'player_id': player_id,
                            'new_team': added_team['team_name'],
                            'existing_teams': [team['team_name'] for team in old_teams],
                        })
                elif removed_teams and added_teams:
                    for added_team in added_teams:
                        changes.append({
                            'type': 'prestop',
                            'player_name': player_name,
                            'player_id': player_id,
                            'old_teams': [team['team_name'] for team in removed_teams],
                            'new_team': added_team['team_name'],
                        })

    for player_id, old_teams in old_players.items():
        if player_id not in new_players:
            # Če so vse stare ekipe imele scrape failure, ne prijavljaj odhoda
            if all(t['team_id'] in failed_team_ids for t in old_teams):
                continue
            # Če vsaj ena ekipa ni failed, a igralec manjka – preveri ali manjkajoče
            # ekipe so failed (obdržale stare) → potem bi bil še v new_players.
            # Sem pridemo le, če ga res ni v new_data.
            player_name = old_teams[0]['player_name']
            changes.append({
                'type': 'igralec_odsel',
                'player_name': player_name,
                'player_id': player_id,
                'old_teams': [team['team_name'] for team in old_teams],
                'competitions': [team['competition'] for team in old_teams],
            })

    for competition, teams in new_data.items():
        for team in teams:
            # Preskoči trenerske spremembe za ekipe z obdržanimi starimi podatki
            if team.get('scrape_kept_old') or team['team_id'] in failed_team_ids:
                continue

            team_id = team['team_id']
            team_name = team['name']
            new_coach = team.get('coach')

            old_team = None
            for old_t in old_data.get(competition, []):
                if old_t['team_id'] == team_id:
                    old_team = old_t
                    break

            if old_team:
                old_coach = old_team.get('coach')
                if old_coach and new_coach:
                    if old_coach.get('name') != new_coach.get('name'):
                        changes.append({
                            'type': 'sprememba_trener',
                            'team': team_name,
                            'competition': competition,
                            'old_coach': old_coach.get('name'),
                            'new_coach': new_coach.get('name'),
                            'position': new_coach.get('position', 'Glavni trener'),
                        })
                elif old_coach and not new_coach:
                    changes.append({
                        'type': 'trener_odsel_iz_ekipe',
                        'team': team_name,
                        'competition': competition,
                        'coach_name': old_coach.get('name'),
                        'position': old_coach.get('position', 'Glavni trener'),
                    })
                elif not old_coach and new_coach:
                    changes.append({
                        'type': 'nov_trener_v_ekipo',
                        'team': team_name,
                        'competition': competition,
                        'coach_name': new_coach.get('name'),
                        'position': new_coach.get('position', 'Glavni trener'),
                    })
            else:
                if new_coach:
                    changes.append({
                        'type': 'nov_trener_v_ekipo',
                        'team': team_name,
                        'competition': competition,
                        'coach_name': new_coach.get('name'),
                        'position': new_coach.get('position', 'Glavni trener'),
                    })

    for competition, teams in old_data.items():
        for team in teams:
            team_id = team['team_id']
            if team_id in failed_team_ids:
                continue

            old_coach = team.get('coach')
            team_exists = any(
                new_t['team_id'] == team_id for new_t in new_data.get(competition, [])
            )

            if not team_exists and old_coach:
                changes.append({
                    'type': 'trener_odsel_iz_ekipe',
                    'team': team['name'],
                    'competition': competition,
                    'coach_name': old_coach.get('name'),
                    'position': old_coach.get('position', 'Glavni trener'),
                })

    return changes


def print_changes(changes):
    """Izpiše zaznane spremembe."""
    if not changes:
        logger.info('Ni zaznanih sprememb')
        return

    logger.info(f'Zaznanih {len(changes)} sprememb')
    print('\n=== ZAZNANE SPREMEMBE ===')

    for change in changes:
        if change['type'] == 'nov_igralec':
            message = (
                f"\nKlub {change['team']} ima novega igralca.\n"
                f"Ime: {change['player_name']}\n"
                f"Link: {CONFIG['base_url']}/igralec/{change['player_id']}\n"
                f'Igralec se prvič pojavi v članski košarki.'
            )
            print(message)
            logger.info(f"Nov igralec: {change['player_name']} v {change['team']}")

        elif change['type'] == 'nov_igralec_dvojna':
            message = (
                f"\nNov igralec z dvojno registracijo:\n"
                f"Ime: {change['player_name']}\n"
                f"Link: {CONFIG['base_url']}/igralec/{change['player_id']}\n"
                f"Registriran v ekipah: {', '.join(change['teams'])}"
            )
            print(message)
            logger.info(
                f"Nov igralec z dvojno registracijo: {change['player_name']} "
                f"v {', '.join(change['teams'])}"
            )

        elif change['type'] == 'prestop':
            message = (
                f"\nPrestop igralca:\n"
                f"Ime: {change['player_name']}\n"
                f"Link: {CONFIG['base_url']}/igralec/{change['player_id']}\n"
                f"Iz: {', '.join(change['old_teams'])}\n"
                f"V: {change['new_team']}"
            )
            print(message)
            logger.info(
                f"Prestop: {change['player_name']} iz {', '.join(change['old_teams'])} "
                f"v {change['new_team']}"
            )

        elif change['type'] == 'dodatna_registracija':
            message = (
                f"\nDodatna registracija:\n"
                f"Ime: {change['player_name']}\n"
                f"Link: {CONFIG['base_url']}/igralec/{change['player_id']}\n"
                f"Nova ekipa: {change['new_team']}\n"
                f"Poleg že obstoječih: {', '.join(change['existing_teams'])}"
            )
            print(message)
            logger.info(f"Dodatna registracija: {change['player_name']} v {change['new_team']}")

        elif change['type'] == 'igralec_odsel':
            message = (
                f"\nIgralec odšel iz lige:\n"
                f"Liga: {', '.join(change['competitions'])}\n"
                f"Ime: {change['player_name']}\n"
                f"Prejšnje ekipe: {', '.join(change['old_teams'])}\n"
                f"Link: {CONFIG['base_url']}/igralec/{change['player_id']}"
            )
            print(message)
            logger.info(
                f"Igralec odšel: {change['player_name']} iz {', '.join(change['old_teams'])}"
            )

        elif change['type'] == 'sprememba_trener':
            message = (
                f"\nSprememba trenerja:\n"
                f"Ekipa: {change['team']} ({change['competition']})\n"
                f"Stari trener: {change['old_coach']}\n"
                f"Novi trener: {change['new_coach']}\n"
                f"Pozicija: {change['position']}"
            )
            print(message)
            logger.info(
                f"Sprememba trenerja v {change['team']}: "
                f"{change['old_coach']} → {change['new_coach']}"
            )

        elif change['type'] == 'trener_odsel_iz_ekipe':
            message = (
                f"\nTrener odšel iz ekipe:\n"
                f"Ekipa: {change['team']} ({change['competition']})\n"
                f"Trener: {change['coach_name']}\n"
                f"Pozicija: {change['position']}"
            )
            print(message)
            logger.info(f"Trener {change['coach_name']} odšel iz {change['team']}")

        elif change['type'] == 'nov_trener_v_ekipo':
            message = (
                f"\nNovi trener v ekipo:\n"
                f"Ekipa: {change['team']} ({change['competition']})\n"
                f"Trener: {change['coach_name']}\n"
                f"Pozicija: {change['position']}"
            )
            print(message)
            logger.info(f"Novi trener {change['coach_name']} v {change['team']}")

    print('\n=== KONEC SPREMEMB ===\n')


def print_scrape_failures(scrape_failures):
    """Izpiši tehnične napake scrapinga (ločeno od pravih sprememb)."""
    if not scrape_failures:
        return

    print(f'\n=== TEHNIČNE NAPAKE SCRAPINGA ({len(scrape_failures)}) ===')
    for failure in scrape_failures:
        print(
            f"• {failure['team']} ({failure.get('competition', '?')}): "
            f"{failure['reason']} [prej {failure.get('old_player_count', 0)} igralcev]"
        )
        logger.warning(
            f"Scrape failure: {failure['team']} / {failure.get('competition')} / "
            f"{failure['reason']}"
        )
    print('=== KONEC TEHNIČNIH NAPAK ===\n')
