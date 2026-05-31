from pathlib import Path

import pytest

from mediamark.input_batch import parse_input_file


def test_parse_text_file_keeps_existing_line_format(tmp_path):
    path = tmp_path / "links.txt"
    path.write_text("BV1xx411c7mD\n\nmid:123\n", encoding="utf-8")

    rows = parse_input_file(path)

    assert [row.url for row in rows] == ["BV1xx411c7mD", "mid:123"]
    assert [row.platform for row in rows] == ["bilibili", "bilibili"]


def test_parse_csv_file_reads_metadata(tmp_path):
    path = tmp_path / "links.csv"
    path.write_text(
        "url,platform,tags,collection,allow_getnote\n"
        'https://www.bilibili.com/video/BV1xx411c7mD,bilibili,"ai,course",ml,no\n',
        encoding="utf-8",
    )

    rows = parse_input_file(path)

    assert rows[0].url == "https://www.bilibili.com/video/BV1xx411c7mD"
    assert rows[0].tags == ["ai", "course"]
    assert rows[0].collection == "ml"
    assert rows[0].allow_getnote is False


def test_parse_jsonl_file_reads_metadata(tmp_path):
    path = tmp_path / "links.jsonl"
    path.write_text(
        '{"url":"BV1xx411c7mD","tags":["ml"],"allow_getnote":true}\n',
        encoding="utf-8",
    )

    rows = parse_input_file(path)

    assert rows[0].url == "BV1xx411c7mD"
    assert rows[0].tags == ["ml"]
    assert rows[0].allow_getnote is True


def test_parse_csv_requires_url_column(tmp_path):
    path = tmp_path / "links.csv"
    path.write_text("title\nmissing url\n", encoding="utf-8")

    with pytest.raises(ValueError, match="url"):
        parse_input_file(path)
