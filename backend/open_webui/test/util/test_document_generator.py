import io

import pytest

from open_webui.utils.document_generator import MessageItem, generate_document_by_format


def _sample_messages() -> list[MessageItem]:
    return [
        MessageItem(role='assistant', content='Report title\n\n| Name | Value |\n|---|---|\n| A | 1 |'),
    ]


def test_generate_docx_bytes():
    data = generate_document_by_format('docx', 'Test Doc', _sample_messages())

    assert isinstance(data, (bytes, bytearray))
    assert len(data) > 100
    assert bytes(data[:2]) == b'PK'


def test_generate_xlsx_bytes():
    pytest.importorskip('openpyxl')
    data = generate_document_by_format('xlsx', 'Test Sheet', _sample_messages())

    assert isinstance(data, (bytes, bytearray))
    assert len(data) > 100
    assert bytes(data[:2]) == b'PK'


def test_generate_xlsx_without_chat_metadata_sheet():
    openpyxl = pytest.importorskip('openpyxl')

    data = generate_document_by_format(
        'xlsx',
        'Test Sheet',
        _sample_messages(),
        include_chat_metadata=False,
    )

    wb = openpyxl.load_workbook(filename=io.BytesIO(data))
    assert 'Чат' not in wb.sheetnames
    assert 'Таблица 1' in wb.sheetnames


def test_generate_document_invalid_format():
    with pytest.raises(ValueError):
        generate_document_by_format('zipx', 'Nope', _sample_messages())


