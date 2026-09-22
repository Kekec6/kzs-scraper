"""Branje/shranjevanje JSON baze, zgodovina sprememb, čiščenje starih poročil."""

import json
import logging
import shutil
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from config import CONFIG, HTML_DIR, changes_history_path

logger = logging.getLogger('kzs')


def save_last_scrape(stats=None):
    """Shrani čas zadnjega uspešnega scrapa."""
    path = Path(CONFIG['last_scrape_file'])
    payload = {
        'iso': datetime.now().isoformat(timespec='seconds'),
        'stats': stats or {},
    }
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        logger.info(f'Zadnji scrape zapisan: {payload["iso"]}')
    except OSError as e:
        logger.warning(f'Ne morem zapisati last_scrape: {e}')


def read_last_scrape():
    """Preberi meta zadnjega scrapa ali None."""
    path = Path(CONFIG['last_scrape_file'])
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None


def backup_for_new_season():
    """Varnostna kopija pred resetom sezone. Vrne pot ali None."""
    json_file = Path(CONFIG['json_file'])
    if not json_file.exists():
        return None
    stamp = datetime.now().strftime('%Y%m%d_%H%M')
    dest = json_file.with_name(f'teams_and_players.season_{stamp}.json')
    shutil.copy2(json_file, dest)
    logger.info(f'Nova sezona: backup → {dest}')
    print(f'🗂  Season backup: {dest}')
    return str(dest)


def save_to_disc(dictionaries):
    """Shrani podatke v JSON datoteko z varnostnim kopiranjem."""
    json_file = CONFIG['json_file']
    try:
        if Path(json_file).exists():
            backup_file = f"{json_file}.backup"
            shutil.copy2(json_file, backup_file)
            logger.info(f"Ustvarjena varnostna kopija: {backup_file}")

        with open(json_file, 'w', encoding='utf-8') as handle:
            json.dump(dictionaries, handle, ensure_ascii=False, indent=4)

        logger.info(f"Podatki uspešno shranjeni v {json_file}")
    except Exception as e:
        logger.error(f"Napaka pri shranjevanju podatkov: {e}")
        raise


def read_from_disc():
    """Preberi podatke iz JSON datoteke. Vrne (current, old_copy)."""
    json_file = CONFIG['json_file']
    try:
        if Path(json_file).exists():
            with open(json_file, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            logger.info(f"Prebrani stari podatki iz {json_file}")
            return data, deepcopy(data)

        logger.info("Ni shranjenih podatkov, začenjam z novo bazo")
        return {}, {}

    except json.JSONDecodeError as e:
        logger.error(f"Napaka pri branju JSON datoteke: {e}")
        logger.info("Uporabljam varnostno kopijo...")
        backup_file = f"{json_file}.backup"

        if Path(backup_file).exists():
            try:
                with open(backup_file, 'r', encoding='utf-8') as handle:
                    data = json.load(handle)
                logger.info("Uspešno obnovljeno iz varnostne kopije")
                return data, deepcopy(data)
            except Exception:
                logger.error("Varnostna kopija tudi ni veljavna, začenjam z novo bazo")

        return {}, {}

    except Exception as e:
        logger.error(f"Nepričakovana napaka pri branju podatkov: {e}")
        return {}, {}


def find_old_team(old_data, competition, team_id):
    """Poišči staro ekipo po team_id znotraj lige."""
    for team in old_data.get(competition, []):
        if team.get('team_id') == team_id:
            return team
    return None


def append_change_history(changes, scrape_failures=None, stats=None, dry_run=False):
    """
    Doda en vnos v data/changes_YYYY-MM.jsonl.
    V dry-run načinu ne piše.
    """
    if dry_run or CONFIG.get('_dry_run'):
        logger.info('DRY-RUN: zgodovina sprememb ni zapisana')
        return None

    if not changes and not scrape_failures:
        return None

    path = changes_history_path()
    entry = {
        'ts': datetime.now().isoformat(timespec='seconds'),
        'changes': changes or [],
        'scrape_failures': scrape_failures or [],
        'stats': stats or {},
    }

    try:
        with open(path, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
        logger.info(
            f"Zgodovina: +{len(entry['changes'])} sprememb, "
            f"+{len(entry['scrape_failures'])} scrape napak → {path}"
        )
        return str(path)
    except Exception as e:
        logger.error(f'Napaka pri pisanju zgodovine: {e}')
        return None


def read_change_history(months_back=2):
    """Preberi JSONL vnose za tekoči mesec in N-1 prejšnjih."""
    entries = []
    now = datetime.now()
    year, month = now.year, now.month

    for _ in range(max(1, months_back)):
        path = changes_history_path(datetime(year, month, 1))
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            except OSError as e:
                logger.warning(f'Ne morem brati {path}: {e}')

        month -= 1
        if month == 0:
            month = 12
            year -= 1

    return entries


def _cleanup_glob(directory, pattern, retention_days, label):
    if retention_days <= 0:
        return 0
    directory = Path(directory)
    if not directory.exists():
        return 0

    cutoff = time.time() - (retention_days * 24 * 60 * 60)
    removed = 0
    for file_path in directory.glob(pattern):
        if file_path.name == 'index.html':
            continue
        try:
            if file_path.stat().st_mtime < cutoff:
                file_path.unlink()
                removed += 1
                logger.info(f'Izbrisan star {label}: {file_path.name}')
        except OSError as e:
            logger.warning(f'Ni mogoče izbrisati {file_path}: {e}')

    if removed:
        logger.info(f'Počiščeno {removed} starih {label} (>{retention_days} dni)')
    return removed


def cleanup_old_reports():
    """Izbriši stare PDF/HTML poročila glede na retention."""
    pdf_n = _cleanup_glob(
        CONFIG['pdf_dir'],
        'prestopi_kosarka_*.pdf',
        CONFIG.get('pdf_retention_days', 14),
        'PDF',
    )
    html_n = _cleanup_glob(
        HTML_DIR,
        'prestopi_kosarka_*.html',
        CONFIG.get('html_retention_days', 90),
        'HTML',
    )
    return pdf_n + html_n


# Nazaj združljivost
def cleanup_old_pdfs():
    return cleanup_old_reports()
