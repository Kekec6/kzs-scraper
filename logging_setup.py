"""Nastavitev logginga."""

import logging
from logging.handlers import RotatingFileHandler

from config import CONFIG


def setup_logging():
    """Inicializira rotating file + console logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler(
                CONFIG['log_file'],
                maxBytes=2 * 1024 * 1024,
                backupCount=5,
                encoding='utf-8',
            ),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger('kzs')
