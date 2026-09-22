"""PDF poročila."""

import logging
import os
import platform
from datetime import datetime

from config import CONFIG, IS_LINUX, IS_MAC, IS_WINDOWS, pdf_filename

logger = logging.getLogger('kzs')

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print('OPOZORILO: Za PDF poročila namestite: pip install reportlab')


def generate_pdf_report(changes, total_teams=0, total_players=0, elapsed_time=0, scrape_failures=None):
    """Ustvari PDF poročilo o spremembah."""
    scrape_failures = scrape_failures or []

    if not PDF_AVAILABLE:
        logger.warning('PDF poročilo ni možno ustvariti - reportlab ni nameščen')
        print('PDF poročilo ni možno ustvariti. Namestite reportlab: pip install reportlab')
        return None

    if not CONFIG['generate_pdf']:
        logger.info('PDF generiranje je onemogočeno v konfiguraciji')
        return None

    try:
        try:
            font_path = None
            if platform.system() == 'Darwin':
                font_path = '/System/Library/Fonts/Helvetica.ttc'
            elif platform.system() == 'Windows':
                font_path = 'C:/Windows/Fonts/arial.ttf'

            if font_path and os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('UnicodeFont', font_path))
            else:
                pass
        except Exception as e:
            logger.warning(f'Napaka pri registraciji fonta: {e}')

        def fix_encoding(text):
            if isinstance(text, str):
                replacements = {
                    'ć': 'c', 'č': 'c', 'ž': 'z', 'š': 's', 'đ': 'd',
                    'Ć': 'C', 'Č': 'C', 'Ž': 'Z', 'Š': 'S', 'Đ': 'D',
                    '■': '', '�': '',
                }
                for old, new in replacements.items():
                    text = text.replace(old, new)
                return text.encode('ascii', errors='ignore').decode('ascii')
            return text

        pdf_path = pdf_filename()
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue,
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.darkgreen,
        )
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=0,
        )

        current_time = datetime.now().strftime('%d.%m.%Y %H:%M')
        story.append(Paragraph('POROCILO O SPREMEMBAH V SLOVENSKI KOSARKI', title_style))
        story.append(Paragraph(f'Generirano: {current_time}', styles['Normal']))
        story.append(Spacer(1, 20))

        story.append(Paragraph('POVZETEK ANALIZE', heading_style))
        summary_data = [
            ['Skupno stevilo ekip:', str(total_teams)],
            ['Skupno stevilo igralcev:', str(total_players)],
            ['Cas analize:', f'{elapsed_time:.1f} sekund'],
            ['Stevilo zaznanih sprememb:', str(len(changes))],
            ['Tehnicne napake scrapinga:', str(len(scrape_failures))],
        ]

        summary_table = Table(summary_data, colWidths=[3 * inch, 2 * inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 20))

        if scrape_failures:
            story.append(Paragraph(
                f'TEHNICNE NAPAKE SCRAPINGA ({len(scrape_failures)})', heading_style
            ))
            story.append(Paragraph(
                'Za te ekipe so obdrzani stari podatki (ni laznih prestopov).',
                normal_style,
            ))
            story.append(Spacer(1, 8))
            for failure in scrape_failures:
                team = fix_encoding(failure['team'])
                competition = fix_encoding(failure.get('competition') or '?')
                story.append(Paragraph(
                    f"{team} ({competition}): {failure['reason']} "
                    f"[prej {failure.get('old_player_count', 0)} igralcev]",
                    normal_style,
                ))
            story.append(Spacer(1, 12))

        if not changes:
            story.append(Paragraph('NI ZAZNANIH SPREMEMB', heading_style))
            story.append(Paragraph(
                'V tej analizi ni bilo zaznanih novih igralcev, prestopov ali dodatnih registracij.',
                normal_style,
            ))
        else:
            novi_igralci = [c for c in changes if c['type'] == 'nov_igralec']
            dvojne_reg = [c for c in changes if c['type'] == 'nov_igralec_dvojna']
            prestopi = [c for c in changes if c['type'] == 'prestop']
            dodatne_reg = [c for c in changes if c['type'] == 'dodatna_registracija']
            odsli_igralci = [c for c in changes if c['type'] == 'igralec_odsel']
            novi_trenerji = [c for c in changes if c['type'] == 'nov_trener_v_ekipo']
            odsli_trenerji = [c for c in changes if c['type'] == 'trener_odsel_iz_ekipe']
            spremembe_trenerjev = [c for c in changes if c['type'] == 'sprememba_trener']

            if novi_igralci:
                story.append(Paragraph(f'NOVI IGRALCI ({len(novi_igralci)})', heading_style))
                for change in novi_igralci:
                    story.append(Paragraph(
                        f"Liga: {fix_encoding(change['competition'])}", normal_style
                    ))
                    story.append(Spacer(1, 6))
                    story.append(Paragraph(
                        f"Ime: <b>{fix_encoding(change['player_name'])}</b>", normal_style
                    ))
                    story.append(Paragraph(
                        f"Klub: {fix_encoding(change['team'])}", normal_style
                    ))
                    story.append(Paragraph(
                        f"Profil: {CONFIG['base_url']}/igralec/{change['player_id']}",
                        normal_style,
                    ))
                    story.append(Spacer(1, 12))

            if prestopi:
                story.append(Paragraph(f'PRESTOPI IGRALCEV ({len(prestopi)})', heading_style))
                for change in prestopi:
                    story.append(Paragraph(
                        f"Igralec: <b>{fix_encoding(change['player_name'])}</b>", normal_style
                    ))
                    story.append(Paragraph(
                        f"Iz ekipe: {fix_encoding(', '.join(change['old_teams']))}",
                        styles['Normal'],
                    ))
                    story.append(Paragraph(
                        f"V ekipo: {fix_encoding(change['new_team'])}", styles['Normal']
                    ))
                    story.append(Paragraph(
                        f"Link: {CONFIG['base_url']}/igralec/{change['player_id']}",
                        styles['Normal'],
                    ))
                    story.append(Spacer(1, 12))

            if dodatne_reg:
                story.append(Paragraph(
                    f'DODATNE REGISTRACIJE ({len(dodatne_reg)})', heading_style
                ))
                for change in dodatne_reg:
                    story.append(Paragraph(
                        f"<b>{fix_encoding(change['player_name'])}</b>", normal_style
                    ))
                    story.append(Paragraph(
                        f"Nova ekipa: {fix_encoding(change['new_team'])}", normal_style
                    ))
                    story.append(Paragraph(
                        f"Ostale ekipe: {fix_encoding(', '.join(change['existing_teams']))}",
                        normal_style,
                    ))
                    story.append(Paragraph(
                        f"Profil: {CONFIG['base_url']}/igralec/{change['player_id']}",
                        styles['Normal'],
                    ))
                    story.append(Spacer(1, 8))

            if dvojne_reg:
                story.append(Paragraph(
                    f'NOVI IGRALCI Z DVOJNO REGISTRACIJO ({len(dvojne_reg)})', heading_style
                ))
                for change in dvojne_reg:
                    story.append(Paragraph(
                        f"<b>{fix_encoding(change['player_name'])}</b>", normal_style
                    ))
                    story.append(Paragraph(
                        f"Ekipe: {fix_encoding(', '.join(change['teams']))}", normal_style
                    ))
                    story.append(Paragraph(
                        f"Lige: {fix_encoding(', '.join(change['competitions']))}",
                        normal_style,
                    ))
                    story.append(Paragraph(
                        f"Profil: {CONFIG['base_url']}/igralec/{change['player_id']}",
                        styles['Normal'],
                    ))
                    story.append(Spacer(1, 8))

            if odsli_igralci:
                story.append(Paragraph(
                    f'IGRALCI, KI SO ODSLI IZ LIGE ({len(odsli_igralci)})', heading_style
                ))
                for change in odsli_igralci:
                    story.append(Paragraph(
                        f"Liga: {fix_encoding(', '.join(change['competitions']))}",
                        normal_style,
                    ))
                    story.append(Spacer(1, 6))
                    story.append(Paragraph(
                        f"Ime: <b>{fix_encoding(change['player_name'])}</b>", normal_style
                    ))
                    story.append(Paragraph(
                        f"Prejsnje ekipe: {fix_encoding(', '.join(change['old_teams']))}",
                        normal_style,
                    ))
                    story.append(Paragraph(
                        f"Link: {CONFIG['base_url']}/igralec/{change['player_id']}",
                        normal_style,
                    ))
                    story.append(Spacer(1, 12))

            if novi_trenerji or odsli_trenerji or spremembe_trenerjev:
                story.append(Paragraph('=== SPREMEMBE TRENERJEV ===', heading_style))

            if novi_trenerji:
                story.append(Paragraph(
                    f'NOVI TRENERJI V EKIPE ({len(novi_trenerji)})', heading_style
                ))
                for change in novi_trenerji:
                    story.append(Paragraph(
                        f"Trener: <b>{fix_encoding(change['coach_name'])}</b>", normal_style
                    ))
                    story.append(Paragraph(
                        f"Nova ekipa: {fix_encoding(change['team'])} "
                        f"({fix_encoding(change['competition'])})",
                        normal_style,
                    ))
                    story.append(Paragraph(
                        f"Pozicija: {fix_encoding(change['position'])}", normal_style
                    ))
                    story.append(Spacer(1, 12))

            if spremembe_trenerjev:
                story.append(Paragraph(
                    f'SPREMEMBE TRENERJEV ({len(spremembe_trenerjev)})', heading_style
                ))
                for change in spremembe_trenerjev:
                    story.append(Paragraph(
                        f"Ekipa: <b>{fix_encoding(change['team'])}</b> "
                        f"({fix_encoding(change['competition'])})",
                        normal_style,
                    ))
                    story.append(Paragraph(
                        f"Stari trener: {fix_encoding(change['old_coach'])}", normal_style
                    ))
                    story.append(Paragraph(
                        f"Novi trener: {fix_encoding(change['new_coach'])}", normal_style
                    ))
                    story.append(Paragraph(
                        f"Pozicija: {fix_encoding(change['position'])}", normal_style
                    ))
                    story.append(Spacer(1, 12))

            if odsli_trenerji:
                story.append(Paragraph(
                    f'TRENERJI, KI SO ODSLI IZ EKIP ({len(odsli_trenerji)})', heading_style
                ))
                for change in odsli_trenerji:
                    story.append(Paragraph(
                        f"Trener: <b>{fix_encoding(change['coach_name'])}</b>", normal_style
                    ))
                    story.append(Paragraph(
                        f"Odshel iz: {fix_encoding(change['team'])} "
                        f"({fix_encoding(change['competition'])})",
                        normal_style,
                    ))
                    story.append(Paragraph(
                        f"Pozicija: {fix_encoding(change['position'])}", normal_style
                    ))
                    story.append(Spacer(1, 12))

        doc.build(story)
        logger.info(f'PDF poročilo uspešno ustvarjeno: {pdf_path}')
        print(f'\n📄 PDF POROČILO USTVARJENO: {pdf_path}')

        if not CONFIG['headless']:
            try:
                if IS_WINDOWS:
                    os.startfile(pdf_path)
                elif IS_MAC:
                    os.system(f"open '{pdf_path}'")
                elif IS_LINUX:
                    os.system(f"xdg-open '{pdf_path}'")
            except Exception:
                pass

        return pdf_path

    except Exception as e:
        logger.error(f'Napaka pri ustvarjanju PDF poročila: {e}')
        print(f'Napaka pri ustvarjanju PDF poročila: {e}')
        return None
