import io
import logging
import re
from datetime import datetime
from typing import Optional, List

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Pydantic models (Local copies for internal use)
# ──────────────────────────────────────────────

class MessageItem:
    def __init__(self, role: str, content: str, timestamp: Optional[int] = None):
        self.role = role
        self.content = content
        self.timestamp = timestamp

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

_ROLE_RU = {
    'user': 'Пользователь',
    'assistant': 'Ассистент',
    'system': 'Система',
}


def _role_label(role: str) -> str:
    return _ROLE_RU.get(role, role.capitalize())


def _safe_filename(name: str) -> str:
    """Remove characters unsafe for filenames."""
    return re.sub(r'[^\w\s\-.]', '', name).strip() or 'document'


def _parse_markdown_tables(text: str) -> List[List[List[str]]]:
    """
    Extract all markdown tables from *text*.
    Returns a list of tables; each table is a list of rows;
    each row is a list of cell strings.
    """
    tables: List[List[List[str]]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Detect pipe-separated header row
        if '|' in line and i + 1 < len(lines):
            sep_line = lines[i + 1].strip()
            if re.match(r'^[\|\-:\s]+$', sep_line) and '|' in sep_line:
                # Found a table header + separator
                table: List[List[str]] = []
                # Header
                cells = [c.strip() for c in line.strip('|').split('|')]
                table.append(cells)
                i += 2  # skip header + separator
                # Data rows
                while i < len(lines):
                    row_line = lines[i].strip()
                    if '|' not in row_line:
                        break
                    row_cells = [c.strip() for c in row_line.strip('|').split('|')]
                    table.append(row_cells)
                    i += 1
                tables.append(table)
                continue
        i += 1
    return tables


def _messages_to_plain(messages: List[MessageItem]) -> str:
    parts = []
    for msg in messages:
        parts.append(f'{_role_label(msg.role).upper()}:\n{msg.content}')
    return '\n\n---\n\n'.join(parts)


def safe_fpdf_text(text: str) -> str:
    """Best-effort Cyrillic → latin-1 for core fonts (transliteration fallback)."""
    try:
        return text.encode('latin-1').decode('latin-1')
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Transliterate Cyrillic
        cyr_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        }
        result = []
        for ch in text:
            lo = ch.lower()
            if lo in cyr_map:
                rep = cyr_map[lo]
                result.append(rep.upper() if ch.isupper() else rep)
            else:
                try:
                    ch.encode('latin-1')
                    result.append(ch)
                except (UnicodeEncodeError, UnicodeDecodeError):
                    result.append('?')
        return ''.join(result)


# ──────────────────────────────────────────────
# Core Generation Functions
# ──────────────────────────────────────────────

def generate_txt(title: str, messages: List[MessageItem]) -> bytes:
    header = f'{title}\nЭкспорт: {datetime.now().strftime("%d.%m.%Y %H:%M")}\n{"=" * 60}\n\n'
    body = _messages_to_plain(messages)
    return (header + body).encode('utf-8')


def generate_md(title: str, messages: List[MessageItem]) -> bytes:
    lines = [
        f'# {title}',
        '',
        f'> Дата экспорта: {datetime.now().strftime("%d.%m.%Y %H:%M")}',
        '',
        '---',
        '',
    ]
    for msg in messages:
        lines.append(f'### {_role_label(msg.role).upper()}')
        lines.append('')
        lines.append(msg.content)
        lines.append('')
        lines.append('---')
        lines.append('')

    return '\n'.join(lines).encode('utf-8')


def generate_pdf(title: str, messages: List[MessageItem]) -> bytes:
    try:
        from fpdf import FPDF

        class ChatPDF(FPDF):
            def header(self):
                self.set_font('Helvetica', 'B', 10)
                self.set_text_color(120, 120, 120)
                self.cell(0, 8, title or 'Экспорт чата', align='C', new_x='LMARGIN', new_y='NEXT')
                self.set_draw_color(220, 220, 220)
                self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
                self.ln(4)

            def footer(self):
                self.set_y(-15)
                self.set_font('Helvetica', 'I', 8)
                self.set_text_color(150, 150, 150)
                self.cell(0, 10, f'Стр. {self.page_no()}', align='C')

        pdf = ChatPDF(orientation='P', unit='mm', format='A4')
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        pdf.set_font('Helvetica', 'B', 16)
        pdf.set_text_color(30, 30, 30)
        pdf.multi_cell(0, 10, safe_fpdf_text(title or 'Экспорт чата'), align='C')
        pdf.ln(2)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(
            0, 6,
            safe_fpdf_text(f'Дата экспорта: {datetime.now().strftime("%d.%m.%Y %H:%M")}'),
            align='C', new_x='LMARGIN', new_y='NEXT',
        )
        pdf.ln(6)

        role_colors = {
            'user': (26, 115, 232),
            'assistant': (13, 150, 74),
            'system': (136, 68, 0),
        }

        for i, msg in enumerate(messages):
            role = msg.role
            color = role_colors.get(role, (80, 80, 80))

            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(*color)
            pdf.cell(0, 6, safe_fpdf_text(_role_label(role).upper()), new_x='LMARGIN', new_y='NEXT')

            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 5, safe_fpdf_text(msg.content), new_x='LMARGIN', new_y='NEXT')
            pdf.ln(3)

            if i < len(messages) - 1:
                pdf.set_draw_color(220, 220, 220)
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
                pdf.ln(4)

        return pdf.output()
    except Exception as e:
        log.exception(f'Error generating PDF: {e}')
        raise


def generate_docx(title: str, messages: List[MessageItem], include_chat_metadata: bool = True) -> bytes:
    try:
        from docx import Document
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()
        for section in doc.sections:
            section.top_margin = Pt(50)
            section.bottom_margin = Pt(50)
            section.left_margin = Pt(60)
            section.right_margin = Pt(60)

        style = doc.styles['Normal']
        style.font.name = 'Calibri'
        style.font.size = Pt(11)

        title_para = doc.add_heading(title or 'Экспорт чата', level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        date_para = doc.add_paragraph(f'Дата экспорта: {datetime.now().strftime("%d.%m.%Y %H:%M")}')
        date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in date_para.runs:
            run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
            run.font.size = Pt(10)
        doc.add_paragraph()

        if include_chat_metadata:
            _ROLE_COLOR = {
                'user': RGBColor(0x1A, 0x73, 0xE8),
                'assistant': RGBColor(0x0D, 0x96, 0x4A),
                'system': RGBColor(0x88, 0x44, 0x00),
            }

            for i, msg in enumerate(messages):
                role_para = doc.add_paragraph()
                role_para.paragraph_format.space_after = Pt(2)
                role_run = role_para.add_run(_role_label(msg.role).upper())
                role_run.bold = True
                role_run.font.size = Pt(10)
                role_run.font.color.rgb = _ROLE_COLOR.get(msg.role, RGBColor(0x55, 0x55, 0x55))

                for line in msg.content.split('\n'):
                    p = doc.add_paragraph(line)
                    p.paragraph_format.space_before = Pt(0)
                    p.paragraph_format.space_after = Pt(1)

                if i < len(messages) - 1:
                    sep = doc.add_paragraph()
                    sep.paragraph_format.space_before = Pt(4)
                    sep.paragraph_format.space_after = Pt(4)
                    pPr = sep._p.get_or_add_pPr()
                    pBdr = OxmlElement('w:pBdr')
                    bottom = OxmlElement('w:bottom')
                    bottom.set(qn('w:val'), 'single')
                    bottom.set(qn('w:sz'), '6')
                    bottom.set(qn('w:space'), '1')
                    bottom.set(qn('w:color'), 'E0E0E0')
                    pBdr.append(bottom)
                    pPr.append(pBdr)
        else:
            plain_content = '\n\n'.join(msg.content for msg in messages if msg.content)
            for line in plain_content.split('\n'):
                p = doc.add_paragraph(line)
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(1)

        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()
    except Exception as e:
        log.exception(f'Error generating DOCX: {e}')
        raise


def generate_xlsx(title: str, messages: List[MessageItem], include_chat_metadata: bool = True) -> bytes:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

        wb = Workbook()
        wb.remove(wb.active)

        header_font = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
        header_fill_asst = PatternFill('solid', fgColor='0D964A')
        header_fill_chat = PatternFill('solid', fgColor='3C4043')
        data_font = Font(name='Calibri', size=10)
        alt_fill = PatternFill('solid', fgColor='F8F9FA')
        wrap_align = Alignment(wrap_text=True, vertical='top')
        thin = Side(style='thin', color='E0E0E0')
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        def auto_col_widths(ws, max_width: int = 80):
            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    try:
                        cell_len = max(len(str(line)) for line in str(cell.value or '').split('\n'))
                        max_len = max(max_len, cell_len)
                    except Exception:
                        pass
                ws.column_dimensions[col_letter].width = min(max_len + 4, max_width)

        table_idx = 0
        for msg in messages:
            if msg.role != 'assistant':
                continue
            tables = _parse_markdown_tables(msg.content)
            for table in tables:
                table_idx += 1
                sheet_name = f'Таблица {table_idx}'
                ws = wb.create_sheet(title=sheet_name)
                if not table: continue
                header_row = table[0]
                data_rows = table[1:]
                for col_idx, cell_val in enumerate(header_row, start=1):
                    cell = ws.cell(row=1, column=col_idx, value=cell_val)
                    cell.font, cell.fill = header_font, header_fill_asst
                    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                    cell.border = border
                ws.row_dimensions[1].height = 22
                for row_idx, row in enumerate(data_rows, start=2):
                    fill = alt_fill if row_idx % 2 == 0 else None
                    for col_idx, cell_val in enumerate(row, start=1):
                        cell = ws.cell(row=row_idx, column=col_idx, value=cell_val)
                        cell.font, cell.alignment, cell.border = data_font, wrap_align, border
                        if fill: cell.fill = fill
                auto_col_widths(ws)
                ws.freeze_panes = 'A2'

        if include_chat_metadata:
            ws_chat = wb.create_sheet(title='Чат', index=0)
            chat_headers = ['№', 'Роль', 'Сообщение', 'Время']
            for col_idx, hdr in enumerate(chat_headers, start=1):
                cell = ws_chat.cell(row=1, column=col_idx, value=hdr)
                cell.font, cell.fill, cell.border = header_font, header_fill_chat, border
                cell.alignment = Alignment(horizontal='center', vertical='center')
            ws_chat.row_dimensions[1].height, ws_chat.freeze_panes = 22, 'A2'

            role_fills = {
                'user': PatternFill('solid', fgColor='EAF3FF'),
                'assistant': PatternFill('solid', fgColor='EAFAF1'),
                'system': PatternFill('solid', fgColor='FFF8E1'),
            }

            for row_idx, msg in enumerate(messages, start=2):
                ts_str = datetime.fromtimestamp(msg.timestamp).strftime('%d.%m.%Y %H:%M') if msg.timestamp else ''
                row_fill = role_fills.get(msg.role)
                row_data = [row_idx - 1, _role_label(msg.role), msg.content, ts_str]
                for col_idx, value in enumerate(row_data, start=1):
                    cell = ws_chat.cell(row=row_idx, column=col_idx, value=value)
                    cell.font, cell.border = data_font, border
                    cell.alignment = wrap_align if col_idx == 3 else Alignment(vertical='top')
                    if row_fill:
                        cell.fill = row_fill

            ws_chat.column_dimensions['A'].width = 6
            ws_chat.column_dimensions['B'].width = 16
            ws_chat.column_dimensions['C'].width = 80
            ws_chat.column_dimensions['D'].width = 18
            for row_idx in range(2, len(messages) + 2):
                ws_chat.row_dimensions[row_idx].height = 40

        if table_idx == 0 and not include_chat_metadata:
            ws = wb.create_sheet(title='Документ')
            ws['A1'] = title or 'Документ'
            ws['A1'].font = Font(name='Calibri', bold=True, size=12)
            ws['A3'] = '\n\n'.join(msg.content for msg in messages if msg.content)
            ws['A3'].alignment = wrap_align
            ws.column_dimensions['A'].width = 120

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
    except Exception as e:
        log.exception(f'Error generating XLSX: {e}')
        raise


def generate_document_by_format(
    fmt: str,
    title: str,
    messages: List[MessageItem],
    include_chat_metadata: bool = True,
) -> bytes:
    """Entry point for all generation logic."""
    fmt = fmt.lower().strip('.')
    if fmt == 'txt':
        return generate_txt(title, messages)
    elif fmt == 'md':
        return generate_md(title, messages)
    elif fmt == 'pdf':
        return generate_pdf(title, messages)
    elif fmt == 'docx':
        return generate_docx(title, messages, include_chat_metadata=include_chat_metadata)
    elif fmt == 'xlsx':
        return generate_xlsx(title, messages, include_chat_metadata=include_chat_metadata)
    else:
        raise ValueError(f'Unsupported format: {fmt}')
