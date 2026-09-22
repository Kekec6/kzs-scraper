"""Email poročila in health-check."""

import logging
import os
import smtplib
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import CONFIG, html_public_url

logger = logging.getLogger('kzs')

EMAIL_AVAILABLE = True


def _smtp_send(msg):
    """Pošlji že sestavljen MIME message."""
    logger.info(f"Povezujem se na {CONFIG['email_smtp_server']}:{CONFIG['email_smtp_port']}")
    server = smtplib.SMTP(CONFIG['email_smtp_server'], CONFIG['email_smtp_port'])

    if CONFIG['email_smtp_port'] == 587:
        server.starttls()

    if CONFIG.get('email_use_auth', True):
        logger.info('Uporabljam SMTP avtentikacijo')
        server.login(CONFIG['email_username'], CONFIG['email_password'])
    else:
        logger.info('Uporabljam SMTP brez avtentikacije')

    from_addr = (
        CONFIG['email_username']
        if CONFIG.get('email_use_auth', True)
        else CONFIG.get('email_from', 'kzs-scraper@localhost')
    )
    server.sendmail(from_addr, CONFIG['email_recipients'], msg.as_string())
    server.quit()
    return True


def _can_send():
    if not EMAIL_AVAILABLE:
        logger.warning('Email funkcionalnost ni na voljo')
        return False

    if not CONFIG['send_email']:
        logger.info('Pošiljanje emaila je onemogočeno')
        return False

    if CONFIG.get('email_use_auth', True):
        if not CONFIG['email_username'] or not CONFIG['email_password']:
            logger.warning('Email avtentikacijske nastavitve niso konfigurirane')
            print('⚠️  Email avtentikacijske nastavitve niso konfigurirane')
            return False

    if not CONFIG['email_recipients']:
        logger.warning('Ni določenih prejemnikov emaila')
        print("⚠️  Ni določenih prejemnikov. Nastavi CONFIG['email_recipients']")
        return False

    return True


def send_email_report(
    pdf_path=None,
    changes=None,
    total_teams=0,
    total_players=0,
    scrape_failures=None,
    html_path=None,
):
    """Pošlje poročilo o pravih spremembah po emailu."""
    scrape_failures = scrape_failures or []
    changes = changes or []

    if not _can_send():
        return False

    if not changes and CONFIG.get('send_only_with_changes', False):
        logger.info('Ni sprememb in pošiljanje je omejeno samo na spremembe')
        return False

    try:
        msg = MIMEMultipart()

        if CONFIG.get('email_use_auth', True):
            msg['From'] = CONFIG['email_username']
        else:
            msg['From'] = CONFIG.get('email_from', 'kzs-scraper@localhost')

        msg['To'] = ', '.join(CONFIG['email_recipients'])

        subject = CONFIG['email_subject']
        if changes:
            subject += f' ({len(changes)} sprememb)'
        else:
            subject += ' (ni sprememb)'
        if scrape_failures:
            subject += f' [{len(scrape_failures)} scrape napak]'
        msg['Subject'] = subject

        current_time = datetime.now().strftime('%d.%m.%Y ob %H:%M')

        if changes:
            novi_igralci = [c for c in changes if c['type'] == 'nov_igralec']
            prestopi = [c for c in changes if c['type'] == 'prestop']
            dodatne_reg = [c for c in changes if c['type'] == 'dodatna_registracija']
            dvojne_reg = [c for c in changes if c['type'] == 'nov_igralec_dvojna']
            odsli_igralci = [c for c in changes if c['type'] == 'igralec_odsel']

            body = f"""Pozdrav!

V analizi slovenske košarke dne {current_time} so bile zaznane naslednje spremembe:

📊 POVZETEK:
• Skupno ekip: {total_teams}
• Skupno igralcev: {total_players}
• Zaznanih sprememb: {len(changes)}
• Tehnične napake scrapinga: {len(scrape_failures)}

"""
            if novi_igralci:
                body += f'\n🆕 NOVI IGRALCI ({len(novi_igralci)}):'
                for c in novi_igralci:
                    body += f"\n• {c['player_name']} - {c['team']} ({c['competition']})"

            if prestopi:
                body += f'\n\n🔄 PRESTOPI ({len(prestopi)}):'
                for c in prestopi:
                    body += f"\n• {c['player_name']}: {', '.join(c['old_teams'])} → {c['new_team']}"

            if dodatne_reg:
                body += f'\n\n➕ DODATNE REGISTRACIJE ({len(dodatne_reg)}):'
                for c in dodatne_reg:
                    body += (
                        f"\n• {c['player_name']}: {c['new_team']} "
                        f"(poleg {', '.join(c['existing_teams'])})"
                    )

            if dvojne_reg:
                body += f'\n\n👥 DVOJNE REGISTRACIJE NOVIH ({len(dvojne_reg)}):'
                for c in dvojne_reg:
                    body += f"\n• {c['player_name']}: {', '.join(c['teams'])}"

            if odsli_igralci:
                body += f'\n\n🚪 IGRALCI, KI SO ODŠLI ({len(odsli_igralci)}):'
                for c in odsli_igralci:
                    body += f"\n• {c['player_name']} (prej: {', '.join(c['old_teams'])})"
        else:
            body = f"""Pozdrav!

Analiza slovenske košarke dne {current_time} je bila uspešno izvedena.

📊 POVZETEK:
• Skupno ekip: {total_teams}
• Skupno igralcev: {total_players}
• Zaznanih sprememb: 0
• Tehnične napake scrapinga: {len(scrape_failures)}

V tej analizi ni bilo zaznanih novih igralcev, prestopov ali registracij.
"""

        if scrape_failures:
            body += f'\n\n⚠️ TEHNIČNE NAPAKE ({len(scrape_failures)}) – obdržani stari podatki:'
            for f in scrape_failures:
                body += (
                    f"\n• {f['team']} ({f.get('competition', '?')}): "
                    f"{f['reason']} [prej {f.get('old_player_count', 0)} igralcev]"
                )

        # HTML povezave (intranet / share)
        index_url = html_public_url('index.html')
        report_url = None
        if html_path:
            report_url = html_public_url(os.path.basename(html_path))
        if index_url or report_url:
            body += '\n\n🌐 HTML PREGLED:'
            if index_url:
                body += f'\n• Domov: {index_url}'
            body += '\n• Spremembe: ' + (html_public_url('spremembe.html') or '')
            body += '\n• Iskanje: ' + (html_public_url('iskanje.html') or '')
            if report_url:
                body += f'\n• Poročilo scrapa: {report_url}'
        elif CONFIG.get('html_public_base') == '':
            body += (
                '\n\n💡 Namig: nastavi CONFIG[\'html_public_base\'] '
                '(npr. http://intranet/kzs/html) za povezave do HTML v emailu.'
            )

        body += f"\n\n---\nPoročilo avtomatsko generirano s KZS Scraper v3\nSistem: {CONFIG['os_type'].title()}"

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        if pdf_path and os.path.exists(pdf_path):
            try:
                with open(pdf_path, 'rb') as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(pdf_path)}',
                )
                msg.attach(part)
                logger.info(f'PDF priložen: {pdf_path}')
            except Exception as e:
                logger.warning(f'Ni mogoče priložiti PDF: {e}')

        _smtp_send(msg)
        logger.info(f"Email uspešno poslan na: {', '.join(CONFIG['email_recipients'])}")
        print(f"📧 EMAIL POSLAN na: {', '.join(CONFIG['email_recipients'])}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error('Email avtentikacija neuspešna - preverite username/password')
        print('❌ Email avtentikacija neuspešna.')
        return False
    except Exception as e:
        logger.error(f'Napaka pri pošiljanju emaila: {e}')
        print(f'❌ Napaka pri pošiljanju emaila: {e}')
        return False


def send_health_check_email(scrape_failures, total_teams=0, elapsed_time=0):
    """Pošlji opozorilo, če je preveč neuspešnih scrape-ov (brez lažnih prestopov)."""
    if not scrape_failures:
        return False

    threshold = CONFIG.get('health_check_failure_threshold', 3)
    if len(scrape_failures) < threshold:
        return False

    if not CONFIG.get('send_health_check_email', True):
        logger.info('Health-check email je onemogočen')
        return False

    if not _can_send():
        return False

    try:
        msg = MIMEMultipart()
        if CONFIG.get('email_use_auth', True):
            msg['From'] = CONFIG['email_username']
        else:
            msg['From'] = CONFIG.get('email_from', 'kzs-scraper@localhost')

        msg['To'] = ', '.join(CONFIG['email_recipients'])
        msg['Subject'] = (
            f"KZS Scraper HEALTH CHECK – {len(scrape_failures)} neuspešnih scrape-ov"
        )

        current_time = datetime.now().strftime('%d.%m.%Y ob %H:%M')
        body = f"""Pozdrav!

KZS scraper dne {current_time} je zaznal {len(scrape_failures)} tehničnih napak
(prag: {threshold}). Za te ekipe so obdržani STARI podatki – lažni prestopi niso bili poslani.

📊 KONTEKST:
• Skupno ekip v teku: {total_teams}
• Čas teka: {elapsed_time:.1f}s
• Neuspešnih scrape-ov: {len(scrape_failures)}

⚠️ NEUSPEŠNE EKIPE:
"""
        for f in scrape_failures:
            body += (
                f"\n• {f['team']} ({f.get('competition', '?')}): "
                f"{f['reason']} [prej {f.get('old_player_count', 0)} igralcev]"
            )

        body += (
            f"\n\n---\nKZS Scraper v3 health check\nSistem: {CONFIG['os_type'].title()}"
        )
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        _smtp_send(msg)
        logger.info('Health-check email uspešno poslan')
        print(f'📧 HEALTH-CHECK EMAIL POSLAN ({len(scrape_failures)} napak)')
        return True

    except Exception as e:
        logger.error(f'Napaka pri pošiljanju health-check emaila: {e}')
        print(f'❌ Napaka pri health-check emailu: {e}')
        return False
