"""Selenium scraping KZS strani."""

import logging
import os
import time

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import CONFIG, IS_LINUX, IS_MAC, IS_WINDOWS, SELECTORS

logger = logging.getLogger('kzs')


def retry_operation(func, max_attempts=None, delay=None, *args, **kwargs):
    """Poskusi operacijo večkrat v primeru napake."""
    if max_attempts is None:
        max_attempts = CONFIG['retry_attempts']
    if delay is None:
        delay = CONFIG['retry_delay']

    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except StaleElementReferenceException as e:
            if attempt == max_attempts - 1:
                logger.error(f"StaleElement napaka po {max_attempts} poskusih: {e}")
                raise
            logger.warning(f"StaleElement napaka - poskus {attempt + 1}, ponavljam čez {delay}s...")
            time.sleep(delay)
        except (TimeoutException, NoSuchElementException) as e:
            if attempt == max_attempts - 1:
                logger.error(f"Element napaka po {max_attempts} poskusih: {e}")
                raise
            logger.warning(f"Element napaka - poskus {attempt + 1}, ponavljam čez {delay}s...")
            time.sleep(delay)
        except Exception as e:
            if attempt == max_attempts - 1:
                logger.error(f"Operacija neuspešna po {max_attempts} poskusih: {e}")
                raise
            logger.warning(f"Poskus {attempt + 1} neuspešen ({e}), ponovni poskus čez {delay}s...")
            time.sleep(delay)


def create_driver():
    """Ustvari WebDriver z optimiziranimi nastavitvami za Mac in Windows."""
    options = webdriver.ChromeOptions()

    logger.info(f"Zaganjam Chrome na {CONFIG['os_type']} sistemu")

    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)

    if CONFIG['headless']:
        options.add_argument('--headless')
        logger.info(f"Chrome se zaganja v headless načinu ({CONFIG['os_type']})")
    else:
        logger.info(f"Chrome se zaganja v običajnem načinu ({CONFIG['os_type']})")

        if IS_WINDOWS:
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--disable-features=TranslateUI')
            options.add_argument(f'--window-size={CONFIG["window_size"]}')
            options.add_argument('--window-position=50,50')
            logger.info('Uporabljam Windows specifične nastavitve')
        elif IS_MAC:
            options.add_argument('--remote-debugging-port=9222')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-features=VizDisplayCompositor')
            options.add_argument(f'--window-size={CONFIG["window_size"]}')
            options.add_argument('--window-position=100,100')
            logger.info('Uporabljam Mac specifične nastavitve')
        elif IS_LINUX:
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')
            options.add_argument(f'--window-size={CONFIG["window_size"]}')
            logger.info('Uporabljam Linux specifične nastavitve')

    if IS_WINDOWS:
        options.add_argument('--disable-logging')
        options.add_argument('--disable-extensions')
    else:
        options.add_argument('--disable-extensions')
        if CONFIG['headless']:
            options.add_argument('--disable-images')
            options.add_argument('--disable-plugins')

    chrome_bin = os.environ.get('CHROME_BIN')
    if chrome_bin and os.path.exists(chrome_bin):
        options.binary_location = chrome_bin
        logger.info(f'CHROME_BIN: {chrome_bin}')

    try:
        from selenium.webdriver.chrome.service import Service

        chromedriver_path = os.environ.get('CHROMEDRIVER_PATH')
        if chromedriver_path and os.path.exists(chromedriver_path):
            logger.info(f'CHROMEDRIVER_PATH: {chromedriver_path}')
            driver = webdriver.Chrome(service=Service(chromedriver_path), options=options)
        elif IS_WINDOWS:
            possible_paths = [
                'chromedriver.exe',
                './chromedriver.exe',
                'C:/chromedriver/chromedriver.exe',
                os.path.join(os.path.expanduser('~'), 'Downloads', 'chromedriver.exe'),
            ]

            driver_path = None
            for path_check in possible_paths:
                if os.path.exists(path_check):
                    driver_path = path_check
                    logger.info(f'Najden ChromeDriver: {driver_path}')
                    break

            if driver_path:
                driver = webdriver.Chrome(service=Service(driver_path), options=options)
            else:
                logger.info('Poskušam z avtomatično detekcijo ChromeDriver-ja')
                driver = webdriver.Chrome(options=options)
        else:
            driver = webdriver.Chrome(options=options)

        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        logger.info(f'WebDriver uspešno ustvarjen na {CONFIG["os_type"]} sistemu')
        return driver

    except Exception as e:
        logger.error(f'Napaka pri ustvarjanju WebDriver-ja na {CONFIG["os_type"]}: {e}')
        if IS_WINDOWS:
            logger.error('Windows pomoč: Prenesite ChromeDriver iz https://chromedriver.chromium.org/')
            logger.error('Postavite chromedriver.exe v isto mapo kot skripta ali v PATH')
        elif IS_MAC:
            logger.error("Mac pomoč: Namestite ChromeDriver z 'brew install chromedriver'")
        else:
            logger.error('Linux pomoč: Namestite ChromeDriver iz repozitorija ali prenesite ročno')
        raise


def find_element_with_selectors(driver, selectors_list, timeout=None):
    """Poskusi najti element z več CSS selektorji."""
    if timeout is None:
        timeout = CONFIG['timeout']

    for selector in selectors_list:
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            logger.debug(f'Element najden s selektorjem: {selector}')
            return element
        except TimeoutException:
            logger.debug(f'Selector {selector} ni našel elementa')
            continue

    raise TimeoutException(f'Noben selector ni našel elementa: {selectors_list}')


def find_elements_with_selectors(driver, selectors_list):
    """Poskusi najti elemente z več CSS selektorji."""
    for selector in selectors_list:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                logger.debug(f'Elementi najdeni s selektorjem: {selector} (št: {len(elements)})')
                return elements
        except Exception as e:
            logger.debug(f'Napaka pri selektorju {selector}: {e}')
            continue

    logger.warning(f'Nobeni elementi niso bili najdeni z nobenim selektorjem: {selectors_list}')
    return []


def get_team_details(driver, team_url):
    """Pridobi igralce in trenerja. Vedno vrne dict z success=True/False."""
    try:
        logger.info(f'Obdelujem URL za ekipo: {team_url}')
        driver.get(team_url)
        time.sleep(CONFIG['page_load_delay'])

        try:
            find_element_with_selectors(driver, SELECTORS['player_elements'])
        except TimeoutException:
            logger.warning('Seznam igralcev ni bil najden ali se ni naložil v pričakovanem času!')
            return {
                'players': [],
                'coach': None,
                'success': False,
                'error': 'timeout_players',
            }

        player_elements = find_elements_with_selectors(driver, SELECTORS['player_elements'])
        if not player_elements:
            logger.warning('Seznam igralcev ni bil najden!')
            return {
                'players': [],
                'coach': None,
                'success': False,
                'error': 'no_player_elements',
            }

        logger.info(f'Najdenih {len(player_elements)} igralcev')
        players_data = []

        for i, player in enumerate(player_elements):
            try:
                player_name = player.text.strip()
                if not player_name:
                    logger.debug(f'Igralec {i + 1} nima imena, preskačemo')
                    continue

                player_id = None
                for selector in SELECTORS['player_id_element']:
                    try:
                        player_id_element = player.find_element(By.CSS_SELECTOR, selector)
                        player_id = player_id_element.get_attribute('id').split('-')[-1]
                        break
                    except NoSuchElementException:
                        continue

                if not player_id:
                    for attr in ['data-player-id', 'id', 'data-id']:
                        attr_value = player.get_attribute(attr)
                        if attr_value:
                            player_id = (
                                attr_value.split('-')[-1] if '-' in attr_value else attr_value
                            )
                            break

                if not player_id:
                    logger.warning(f'Ne morem najti ID-ja za igralca: {player_name}')
                    continue

                players_data.append({
                    'name': player_name,
                    'player_id': player_id,
                    'link': f"{CONFIG['base_url']}/igralec/{player_id}",
                })
            except NoSuchElementException:
                continue
            except Exception as e:
                logger.debug(f'Napaka pri pridobivanju podatkov za igralca: {e}')
                continue

        logger.info(f'Uspešno pridobljenih {len(players_data)} igralcev')

        coach_data = None
        try:
            coach_elements = driver.find_elements(
                By.CSS_SELECTOR, 'span.text-blue.font-condensed.text-md.font-medium'
            )
            if coach_elements:
                coach_name = coach_elements[0].text.strip()
                if coach_name:
                    coach_data = {'name': coach_name, 'position': 'Glavni trener'}
                    logger.info(f'Najden trener: {coach_name}')
                else:
                    logger.warning('Ime trenerja je prazno')
            else:
                logger.warning('Trener ni bil najden')
        except Exception as e:
            logger.warning(f'Napaka pri pridobivanju trenerja: {e}')

        return {
            'players': players_data,
            'coach': coach_data,
            'success': True,
            'error': None,
        }

    except WebDriverException as e:
        logger.error(f'WebDriver napaka pri nalaganju {team_url}: {e}')
        return {'players': [], 'coach': None, 'success': False, 'error': f'webdriver: {e}'}
    except Exception as e:
        logger.error(f'Splošna napaka pri pridobivanju podatkov ekipe: {e}')
        return {'players': [], 'coach': None, 'success': False, 'error': str(e)}


def load_browser(driver, url_link):
    """Naloži URL z robustnim pristopom in več poskusi."""

    def _load_page():
        logger.info(f'Nalagam URL: {url_link}')
        driver.get(url_link)
        find_element_with_selectors(driver, SELECTORS['page_loaded'])
        time.sleep(CONFIG['page_load_delay'])
        logger.info('Stran uspešno naložena')

    try:
        retry_operation(_load_page)
    except TimeoutException:
        logger.error(f'Stran se ni naložila v pričakovanem času: {url_link}')
        raise
    except Exception as e:
        logger.error(f'Napaka pri nalaganju strani: {e}')
        raise


def is_suspicious_empty_scrape(players, old_team):
    """True, če je prazen scrape sumljiv glede na stare podatke."""
    min_old = CONFIG.get('empty_scrape_min_old_players', 3)
    if players:
        return False
    if not old_team:
        return False
    old_count = len(old_team.get('players') or [])
    return old_count >= min_old


def resolve_team_data(team_basic, team_details, old_team):
    """
    Odloči, ali sprejmemo nove podatke ali obdržimo stare.
    Vrne (team_data, failure_info|None).

    Če je scrape spodletel, starih igralcev pa je bilo 0, to NI tehnična napaka
    (ekipa je bila že prazna / še nima seznama).
    """
    players = team_details.get('players') or []
    coach = team_details.get('coach')
    success = team_details.get('success', False)
    error = team_details.get('error')
    old_count = len(old_team.get('players') or []) if old_team else 0

    def _team_payload(players_data, coach_data, kept_old=False):
        return {
            'name': team_basic['name'],
            'link': team_basic['link'],
            'team_id': team_basic['team_id'],
            'competition_id': team_basic['competition_id'],
            'players': players_data,
            'coach': coach_data,
            'scrape_kept_old': kept_old,
        }

    # Timeout / neuspeh, a ekipa je imela že 0 igralcev → ni alarm
    if not success and old_count == 0:
        logger.info(
            f"Scrape neuspešen za {team_basic['name']} ({error or 'scrape_failed'}), "
            f'prej 0 igralcev – ni tehnična napaka'
        )
        if old_team:
            return _team_payload(
                old_team.get('players') or [],
                old_team.get('coach'),
                kept_old=False,
            ), None
        return _team_payload([], None, kept_old=False), None

    keep_old = False
    reason = None

    if not success:
        keep_old = True
        reason = error or 'scrape_failed'
    elif is_suspicious_empty_scrape(players, old_team):
        keep_old = True
        reason = 'suspicious_empty'
        logger.warning(
            f"Sumljiv prazen scrape za {team_basic['name']}: "
            f'0 igralcev (prej {old_count}) – obdržim stare podatke'
        )

    if keep_old and old_team:
        logger.warning(
            f"Scrape neuspešen za {team_basic['name']} ({reason}) – "
            f'obdržim {old_count} starih igralcev'
        )
        return _team_payload(
            old_team.get('players') or [],
            old_team.get('coach'),
            kept_old=True,
        ), {
            'team': team_basic['name'],
            'team_id': team_basic['team_id'],
            'competition': None,  # dopolni klicatelj
            'reason': reason,
            'old_player_count': old_count,
        }

    if keep_old and not old_team:
        # Brez starih podatkov – ni česa izgubiti, brez alarma
        logger.info(
            f"Scrape neuspešen za {team_basic['name']} ({reason}) – "
            'ni starih podatkov, shranjujem prazno (brez alarma)'
        )
        return _team_payload([], None, kept_old=False), None

    return _team_payload(players, coach, kept_old=False), None


def run_smoke_test(driver):
    """
    Hitri preveri: 1 liga + 1 ekipa mora vrniti ekipe in igralce.
    Raise RuntimeError ob neuspehu.
    """
    league = CONFIG.get('smoke_test_league') or CONFIG['leagues'][0]
    min_players = CONFIG.get('smoke_test_min_players', 1)
    url = CONFIG['url_template'].format(league)

    logger.info(f'Smoke test: liga={league}')
    print(f'🔬 Smoke test: {league} …')

    load_browser(driver, url)
    team_elements = find_elements_with_selectors(driver, SELECTORS['team_grid'])
    if not team_elements:
        raise RuntimeError(f'Smoke test FAIL: ni ekip na {url}')

    first = team_elements[0]
    team_name = (first.text or '').strip() or 'unknown'
    team_href = first.get_attribute('href')
    if not team_href:
        raise RuntimeError('Smoke test FAIL: prva ekipa nima href')

    players_url = f'{team_href}&tab=seznam'
    details = get_team_details(driver, players_url)
    players = details.get('players') or []

    if not details.get('success'):
        raise RuntimeError(
            f'Smoke test FAIL: scrape ekipe {team_name} neuspešen '
            f'({details.get("error")})'
        )
    if len(players) < min_players:
        raise RuntimeError(
            f'Smoke test FAIL: {team_name} ima {len(players)} igralcev '
            f'(pričakovano ≥ {min_players}) – selektorji?'
        )

    logger.info(
        f'Smoke test OK: {team_name} → {len(players)} igralcev'
    )
    print(f'✅ Smoke test OK: {team_name} ({len(players)} igralcev)')
    return True
