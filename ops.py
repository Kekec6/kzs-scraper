"""Operativa: lock file, CLI argumenti, exit code-i."""

import argparse
import atexit
import logging
import os
from pathlib import Path

from config import CONFIG

logger = logging.getLogger('kzs')

# Exit codes
EXIT_OK = 0
EXIT_CRITICAL = 1
EXIT_SCRAPE_ISSUES = 2
EXIT_LOCKED = 3


def parse_args(argv=None):
    """CLI: --dry-run, --no-email, --no-pdf, ..."""
    parser = argparse.ArgumentParser(
        description='KZS scraper – spremljanje prestopov v slovenski košarki.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Scrape + primerjava brez shranjevanja JSON, emaila in zgodovine',
    )
    parser.add_argument(
        '--no-email',
        action='store_true',
        help='Ne pošiljaj emailov (tudi ne health-check)',
    )
    parser.add_argument(
        '--no-lock',
        action='store_true',
        help='Preskoči lock file (samo za ročno debugiranje)',
    )
    parser.add_argument(
        '--new-season',
        action='store_true',
        help='Nova sezona: backup stare baze, brez primerjave (ni lažnih novih igralcev)',
    )
    parser.add_argument(
        '--skip-smoke',
        action='store_true',
        help='Preskoči smoke test pred scrapom',
    )
    return parser.parse_args(argv)


class ProcessLock:
    """Prepreči sočasni zagon (npr. prekrivajoči se cron jobi)."""

    def __init__(self, lock_path=None):
        self.lock_path = Path(lock_path or CONFIG['lock_file'])
        self._held = False

    def acquire(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        if self.lock_path.exists():
            try:
                old_pid = int(self.lock_path.read_text(encoding='utf-8').strip())
            except (ValueError, OSError):
                old_pid = None

            if old_pid and _pid_alive(old_pid):
                logger.error(
                    f'Drug zagon že teče (PID {old_pid}). Lock: {self.lock_path}'
                )
                return False

            logger.warning(
                f'Najden zastarel lock (PID {old_pid}) – prevzemam'
            )
            try:
                self.lock_path.unlink()
            except OSError:
                pass

        self.lock_path.write_text(str(os.getpid()), encoding='utf-8')
        self._held = True
        atexit.register(self.release)
        logger.info(f'Lock pridobljen: {self.lock_path} (PID {os.getpid()})')
        return True

    def release(self):
        if not self._held:
            return
        try:
            if self.lock_path.exists():
                current = self.lock_path.read_text(encoding='utf-8').strip()
                if current == str(os.getpid()):
                    self.lock_path.unlink()
                    logger.info('Lock sproščen')
        except OSError as e:
            logger.warning(f'Napaka pri sproščanju locka: {e}')
        finally:
            self._held = False


def _pid_alive(pid):
    """Preveri, ali proces s podanim PID še obstaja."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def exit_code_for_run(critical=False, scrape_failures=None, locked=False):
    """
    0 = OK
    1 = kritična napaka
    2 = tek zaključen, ampak so bile scrape napake
    3 = drug zagon že teče (lock)
    """
    if locked:
        return EXIT_LOCKED
    if critical:
        return EXIT_CRITICAL
    if scrape_failures:
        return EXIT_SCRAPE_ISSUES
    return EXIT_OK


def apply_runtime_flags(args):
    """Privzeto CLI zastavice v CONFIG za ta zagon."""
    CONFIG['_dry_run'] = bool(args.dry_run)
    if args.dry_run:
        logger.info('DRY-RUN: JSON, email in zgodovina se NE pišejo')
        print('🔸 DRY-RUN način – brez shranjevanja / emaila / zgodovine')
    if args.no_email:
        CONFIG['send_email'] = False
        CONFIG['send_health_check_email'] = False
        logger.info('Email onemogočen (--no-email)')
