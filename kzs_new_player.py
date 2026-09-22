"""
KZS scraper – spremljanje prestopov v slovenski košarki.

Zagon:
  python kzs_new_player.py
  python kzs_new_player.py --dry-run
  python kzs_new_player.py --no-email
  python kzs_new_player.py --new-season
  python kzs_new_player.py --skip-smoke

Exit code:
  0 = OK
  1 = kritična napaka
  2 = zaključeno z scrape napakami
  3 = drug zagon že teče (lock)
"""

import json
import time

from changes import detect_changes, print_changes, print_scrape_failures
from config import CONFIG, SELECTORS
from html_report import generate_html_report, generate_roster_html, update_html_index
from logging_setup import setup_logging
from mail import send_email_report, send_health_check_email
from ops import (
    EXIT_CRITICAL,
    EXIT_LOCKED,
    ProcessLock,
    apply_runtime_flags,
    exit_code_for_run,
    parse_args,
)
from report import generate_pdf_report
from scraper import (
    create_driver,
    find_elements_with_selectors,
    get_team_details,
    load_browser,
    resolve_team_data,
    retry_operation,
    run_smoke_test,
)
from storage import (
    append_change_history,
    backup_for_new_season,
    cleanup_old_reports,
    find_old_team,
    read_from_disc,
    read_last_scrape,
    save_last_scrape,
    save_to_disc,
)

logger = setup_logging()


def strip_internal_flags(data):
    """Odstrani interna polja pred shranjevanjem/primerjavo."""
    cleaned = {}
    for league, teams in data.items():
        cleaned[league] = []
        for team in teams:
            team_copy = {k: v for k, v in team.items() if k != 'scrape_kept_old'}
            cleaned[league].append(team_copy)
    return cleaned


def main(args=None):
    """Glavna funkcija. Vrne exit code."""
    if args is None:
        args = parse_args()
    apply_runtime_flags(args)

    dry_run = bool(args.dry_run)
    new_season = bool(getattr(args, 'new_season', False))
    skip_smoke = bool(getattr(args, 'skip_smoke', False))
    lock = None
    driver = None
    start_time = time.time()
    scrape_failures = []
    teams_and_players = {}
    critical = False

    if not args.no_lock:
        lock = ProcessLock()
        if not lock.acquire():
            print('❌ Drug zagon scraperja že teče – prekinjam.')
            return EXIT_LOCKED

    try:
        cleanup_old_reports()

        if new_season and not dry_run:
            backup_for_new_season()
            print('🆕 Nova sezona: primerjava s starimi podatki je IZKLOPLJENA')

        logger.info('Začenjam s pridobivanjem podatkov')
        logger.info(f"Operacijski sistem: {CONFIG['os_type']}")
        logger.info(
            f"Nastavitve: timeout={CONFIG['timeout']}s, headless={CONFIG['headless']}, "
            f"dry_run={dry_run}, new_season={new_season}"
        )

        driver = retry_operation(create_driver)
        logger.info(f"Brskalnik uspešno inicializiran na {CONFIG['os_type']} sistemu")

        if CONFIG.get('smoke_test_enabled', True) and not skip_smoke:
            try:
                run_smoke_test(driver)
            except Exception as e:
                logger.critical(f'Smoke test neuspešen: {e}')
                print(f'❌ Smoke test neuspešen: {e}')
                return EXIT_CRITICAL

        teams_and_players, old_teams_and_players = read_from_disc()
        if new_season:
            old_teams_and_players = {}
            logger.info('Nova sezona: old_data = {{}} (brez detect_changes lažnih alarmov)')

        for i, league in enumerate(CONFIG['leagues']):
            logger.info(f"Obdelavam ligo {i + 1}/{len(CONFIG['leagues'])}: {league}")
            url = CONFIG['url_template'].format(league)

            try:
                retry_operation(load_browser, driver=driver, url_link=url)
                team_elements = find_elements_with_selectors(driver, SELECTORS['team_grid'])

                if not team_elements:
                    logger.warning(f'Niso bile najdene nobene ekipe za {url}')
                    continue

                logger.info(f'Najdenih {len(team_elements)} ekip')
                team_links_data = []

                for j, _team_element in enumerate(team_elements):
                    try:
                        if j > 0:
                            time.sleep(CONFIG['navigation_delay'])

                        def get_team_basic_data(idx=j):
                            current_team_elements = find_elements_with_selectors(
                                driver, SELECTORS['team_grid']
                            )
                            if idx >= len(current_team_elements):
                                raise IndexError(f'Element {idx} ni več dostopen')
                            current_team = current_team_elements[idx]
                            return current_team.text.strip(), current_team.get_attribute('href')

                        team_name, team_href = retry_operation(get_team_basic_data)

                        if not team_name or not team_href:
                            logger.warning(f'Manjkajo podatki za ekipo {j + 1}')
                            continue

                        try:
                            team_id = team_href.split('/ekipa/')[1].split('?')[0]
                            competition_id = team_href.split('tekmovanje=')[1]
                        except IndexError:
                            logger.warning(f'Ne morem ekstraktirati ID-jev iz URL: {team_href}')
                            continue

                        team_links_data.append({
                            'name': team_name,
                            'link': team_href,
                            'team_id': team_id,
                            'competition_id': competition_id,
                        })
                    except Exception as e:
                        logger.error(f'Napaka pri zbiranju podatkov za ekipo {j + 1}: {e}')
                        continue

                logger.info(f'Pridobivam igralce za {len(team_links_data)} ekip')
                teams_data = []

                for k, team_basic in enumerate(team_links_data):
                    try:
                        if k > 0:
                            time.sleep(CONFIG['navigation_delay'])

                        players_url = f"{team_basic['link']}&tab=seznam"
                        old_team = find_old_team(
                            old_teams_and_players, league, team_basic['team_id']
                        )

                        try:
                            team_details = retry_operation(
                                get_team_details,
                                max_attempts=2,
                                driver=driver,
                                team_url=players_url,
                            )
                        except Exception as e:
                            logger.error(
                                f"Napaka pri scrape ekipe {team_basic['name']}: {e}"
                            )
                            team_details = {
                                'players': [],
                                'coach': None,
                                'success': False,
                                'error': str(e),
                            }

                        team_data, failure = resolve_team_data(
                            team_basic, team_details, old_team
                        )
                        if failure:
                            failure['competition'] = league
                            scrape_failures.append(failure)

                        teams_data.append(team_data)

                        if team_data.get('scrape_kept_old'):
                            logger.info(
                                f"Za ekipo {team_basic['name']} obdržani stari podatki "
                                f"({len(team_data['players'])} igralcev)"
                            )
                        elif team_data['players']:
                            logger.info(
                                f"Za ekipo {team_basic['name']} pridobljenih "
                                f"{len(team_data['players'])} igralcev"
                            )
                        else:
                            logger.warning(
                                f"Za ekipo {team_basic['name']} ni bilo pridobljenih igralcev"
                            )

                    except Exception as e:
                        logger.error(
                            f"Napaka pri pridobivanju igralcev za {team_basic['name']}: {e}"
                        )
                        old_team = find_old_team(
                            old_teams_and_players, league, team_basic['team_id']
                        )
                        team_details = {
                            'players': [],
                            'coach': None,
                            'success': False,
                            'error': str(e),
                        }
                        team_data, failure = resolve_team_data(
                            team_basic, team_details, old_team
                        )
                        if failure:
                            failure['competition'] = league
                            scrape_failures.append(failure)
                        teams_data.append(team_data)

                teams_and_players[league] = teams_data
                logger.info(f'Liga {league} uspešno obdelana')

            except Exception as e:
                logger.error(f'Napaka pri obdelavi lige {league}: {e}')
                continue

        print_scrape_failures(scrape_failures)

        cleaned_new = strip_internal_flags(teams_and_players)
        changes = []
        data_changed = False

        if old_teams_and_players:
            logger.info('Analiziram spremembe...')
            changes = detect_changes(
                old_teams_and_players, cleaned_new, scrape_failures=scrape_failures
            )
            print_changes(changes)

            old_json = json.dumps(old_teams_and_players, sort_keys=True, ensure_ascii=False)
            new_json = json.dumps(cleaned_new, sort_keys=True, ensure_ascii=False)
            data_changed = old_json != new_json
        else:
            logger.info('Prvi zagon - ni starih podatkov za primerjavo')
            data_changed = True

        if data_changed:
            if dry_run:
                logger.info('DRY-RUN: preskakujem shranjevanje JSON')
                print('🔸 DRY-RUN: JSON ni shranjen')
            else:
                save_to_disc(cleaned_new)
        else:
            logger.info('Podatki se niso spremenili - preskačem shranjevanje')

        total_teams = sum(len(teams) for teams in cleaned_new.values())
        total_players = sum(
            len(team['players']) for teams in cleaned_new.values() for team in teams
        )
        elapsed_time = time.time() - start_time
        stats = {
            'teams': total_teams,
            'players': total_players,
            'elapsed': round(elapsed_time, 1),
        }

        logger.info(f'Proces uspešno zaključen v {elapsed_time:.2f}s')
        print(
            f'\nPROCES ZAKLJUČEN: {total_teams} ekip, {total_players} igralcev '
            f'v {elapsed_time:.1f}s'
        )
        if scrape_failures:
            print(
                f'⚠️  Tehnične napake scrapinga: {len(scrape_failures)} '
                f'(stari podatki obdržani)'
            )

        # Zgodovina (preživi brisanje PDF/HTML)
        hist_path = append_change_history(
            changes,
            scrape_failures=scrape_failures,
            stats=stats,
            dry_run=dry_run,
        )
        if hist_path:
            print(f'🗂  Zgodovina: {hist_path}')

        if not dry_run:
            save_last_scrape(stats)

        pdf_path = None
        html_path = None
        scrape_meta = read_last_scrape() or {
            'iso': None,
            'stats': stats,
        }
        if not scrape_meta.get('iso'):
            from datetime import datetime as _dt
            scrape_meta = {'iso': _dt.now().isoformat(timespec='seconds'), 'stats': stats}

        # Vedno osveži pregled lig/ekip/igralcev + iskanje
        if CONFIG.get('generate_html', True):
            generate_roster_html(cleaned_new, scrape_meta=scrape_meta)

        if changes or scrape_failures:
            if CONFIG.get('generate_html', True):
                html_path = generate_html_report(
                    changes,
                    total_teams,
                    total_players,
                    elapsed_time,
                    scrape_failures=scrape_failures,
                    dry_run=dry_run,
                    roster_data=cleaned_new,
                )

            if changes and CONFIG['generate_pdf'] and not dry_run:
                logger.info('Ustvarjam PDF poročilo...')
                pdf_path = generate_pdf_report(
                    changes,
                    total_teams,
                    total_players,
                    elapsed_time,
                    scrape_failures=scrape_failures,
                )
                if pdf_path:
                    print(f'📋 PDF: {pdf_path}')

            if changes and CONFIG['send_email'] and not dry_run:
                logger.info('Pošiljam email poročilo...')
                if not send_email_report(
                    pdf_path,
                    changes,
                    total_teams,
                    total_players,
                    scrape_failures=scrape_failures,
                    html_path=html_path,
                ):
                    print('⚠️  Email ni bil poslan - preverite nastavitve')
            elif dry_run and changes:
                print('🔸 DRY-RUN: email ni poslan')
        else:
            logger.info('Ni sprememb/napak – poročilo sprememb se ne generira')

        update_html_index(roster_data=None)
        if not dry_run:
            send_health_check_email(scrape_failures, total_teams, elapsed_time)

        print('👉 Odpri pregled: output/html/index.html')
        if html_path:
            print(f'👉 Poročilo sprememb: {html_path}')

        return exit_code_for_run(scrape_failures=scrape_failures)

    except KeyboardInterrupt:
        logger.warning('Proces prekinjen s strani uporabnika')
        print('\nProces prekinjen s strani uporabnika')
        critical = True
        return EXIT_CRITICAL
    except Exception as e:
        logger.error(f'Napaka v glavnem procesu: {e}', exc_info=True)
        print(f'Napaka v glavnem procesu: {e}')
        critical = True
        return EXIT_CRITICAL
    finally:
        if driver:
            logger.info('Zapiranje brskalnika...')
            try:
                driver.quit()
            except Exception as e:
                logger.error(f'Napaka pri zapiranju brskalnika: {e}')
        if lock:
            lock.release()
        if critical:
            pass


if __name__ == '__main__':
    try:
        code = main()
    except Exception as e:
        logger.critical(f'Kritična napaka: {e}', exc_info=True)
        print(f'Kritična napaka: {e}')
        code = EXIT_CRITICAL
    raise SystemExit(code)
