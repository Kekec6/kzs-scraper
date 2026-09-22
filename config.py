"""Konfiguracija KZS scraperja."""

import os
import platform
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
PDF_DIR = BASE_DIR / 'output' / 'pdf'
HTML_DIR = BASE_DIR / 'output' / 'html'
LOG_DIR = BASE_DIR / 'logs'

for _dir in (DATA_DIR, PDF_DIR, HTML_DIR, LOG_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

OS_TYPE = platform.system().lower()
IS_WINDOWS = OS_TYPE == 'windows'
IS_MAC = OS_TYPE == 'darwin'
IS_LINUX = OS_TYPE == 'linux'

CONFIG = {
    'json_file': str(DATA_DIR / 'teams_and_players.json'),
    'lock_file': str(DATA_DIR / 'scraper.lock'),
    'changes_history_dir': str(DATA_DIR),
    'pdf_dir': str(PDF_DIR),
    'html_dir': str(HTML_DIR),
    'log_file': str(LOG_DIR / 'scraper.log'),
    'base_url': 'https://www.kzs.si',
    'url_template': 'https://www.kzs.si/tekmovanja/ligaska-tekmovanja/{}?tab=ekipe',
    'leagues': [
        'liga-otp-banka',
        '2-skl-za-moske',
        '3-skl-za-moske',
        '4-skl-za-moske',
        '1-skl-za-zenske',
    ],
    'timeout': 15,
    'retry_attempts': 3,
    'retry_delay': 2,
    'page_load_delay': 2 if IS_WINDOWS else 1,
    'navigation_delay': 1 if IS_WINDOWS else 0.5,
    'headless': True,
    'window_size': '1400,900' if IS_WINDOWS else '1200,800',
    'os_type': OS_TYPE,
    'generate_pdf': True,
    'generate_html': True,
    'pdf_filename_template': 'prestopi_kosarka_{timestamp}.pdf',
    'html_filename_template': 'prestopi_kosarka_{timestamp}.html',
    'pdf_retention_days': 14,
    'html_retention_days': 90,
    'last_scrape_file': str(DATA_DIR / 'last_scrape.json'),

    # Javni URL/pot do HTML (za email). Primeri:
    # 'https://Kekec6.github.io/kzs-scraper'
    # 'http://intranet/kzs/html'
    'html_public_base': 'https://Kekec6.github.io/kzs-scraper',

    # Smoke test pred celim scrapom
    'smoke_test_enabled': True,
    'smoke_test_league': None,  # None = prva liga v seznamu
    'smoke_test_min_players': 1,

    # Zaščita pred lažnimi "igralec odšel" alarmi
    'empty_scrape_min_old_players': 3,
    'health_check_failure_threshold': 3,
    'send_health_check_email': True,

    # Email
    'send_email': True,
    'email_smtp_server': 'relay.unior.com',
    'email_smtp_port': 25,
    'email_use_auth': False,
    'email_username': '',
    'email_password': '',
    'email_from': 'kzs-scraper@unior.com',
    'email_recipients': ['tomaz.jereb@unior.com'],
    'email_subject': 'KZS Košarka - Poročilo o spremembah',
    'send_only_with_changes': True,

    '_dry_run': False,
}

SELECTORS = {
    'team_grid': [
        '.grid.grid-cols-2.gap-2.xs\\:gap-3.sm\\:grid-cols-3.md\\:grid-cols-4.lg\\:grid-cols-5.lg\\:gap-5 a',
        '.team-grid a',
        '.teams-container a',
        '[href*="/ekipa/"]',
    ],
    'player_elements': [
        '.cursor-pointer.rounded-md.border.border-gray-200',
        '[data-player-id]',
        '.player-card',
        '.roster-player',
        '[id*="player-name-"]',
    ],
    'player_id_element': [
        '[id^="player-name-"]',
        '[data-player-id]',
        '.player-id',
    ],
    'coach_section': [
        'div[data-v-40d8c143][class*="text-color"][class*="font-condensed"]',
        '.coach-section',
        '[class*="trenerski"]',
    ],
    'coach_name': [
        '.text-blue.font-condensed.text-md.font-medium',
        '.coach-name',
        'span.text-blue',
    ],
    'page_loaded': [
        '.grid',
        '.teams-container',
        '.main-content',
    ],
}


def _timestamp():
    return datetime.now().strftime('%Y%m%d_%H%M')


def pdf_filename():
    """Vrni pot do novega PDF poročila."""
    name = CONFIG['pdf_filename_template'].format(timestamp=_timestamp())
    return str(PDF_DIR / name)


def html_filename():
    """Vrni pot do novega HTML poročila."""
    name = CONFIG['html_filename_template'].format(timestamp=_timestamp())
    return str(HTML_DIR / name)


def html_public_url(filename='index.html'):
    """Sestavi javni URL/pot do HTML datoteke (za email)."""
    base = (CONFIG.get('html_public_base') or '').rstrip('/')
    if not base:
        return None
    return f'{base}/{filename}'


def changes_history_path(when=None):
    """Pot do mesečne JSONL zgodovine: data/changes_YYYY-MM.jsonl"""
    when = when or datetime.now()
    return DATA_DIR / f"changes_{when.strftime('%Y-%m')}.jsonl"

