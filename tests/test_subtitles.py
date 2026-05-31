from mediamark.bilibili.subtitles import parse_subtitle_json


def test_parse_subtitle_json_to_transcript_lines():
    payload = {
        "body": [
            {"from": 1.23, "to": 3.45, "content": "第一句"},
            {"from": 3.45, "to": 5.00, "content": "第二句"},
        ]
    }

    transcript = parse_subtitle_json(payload)

    assert transcript.source == "bilibili_subtitle"
    assert transcript.lines[0].start_seconds == 1.23
    assert transcript.lines[0].end_seconds == 3.45
    assert transcript.lines[0].text == "第一句"
    assert transcript.lines[1].text == "第二句"


def test_parse_subtitle_json_returns_no_lines_for_empty_body():
    transcript = parse_subtitle_json({"body": []})

    assert transcript.source == "bilibili_subtitle"
    assert transcript.lines == []


def test_parse_subtitle_json_returns_no_lines_for_none_body():
    transcript = parse_subtitle_json({"body": None})

    assert transcript.source == "bilibili_subtitle"
    assert transcript.lines == []


def test_parse_subtitle_json_returns_no_lines_for_non_list_body():
    transcript = parse_subtitle_json({"body": {"from": 1.0, "to": 2.0, "content": "字幕"}})

    assert transcript.source == "bilibili_subtitle"
    assert transcript.lines == []


def test_parse_subtitle_json_skips_blank_content():
    payload = {
        "body": [
            {"from": 1.0, "to": 2.0, "content": "  "},
            {"from": 2.0, "to": 3.0, "content": "\n\t"},
        ]
    }

    transcript = parse_subtitle_json(payload)

    assert transcript.lines == []


def test_parse_subtitle_json_skips_invalid_items_and_keeps_valid_lines():
    payload = {
        "body": [
            "not a subtitle item",
            {"from": 1.0, "to": 2.0, "content": "  "},
            {"to": 2.0, "content": "missing start"},
            {"from": "soon", "to": 2.0, "content": "bad start"},
            {"from": 3.0, "to": 4.0, "content": "有效字幕"},
        ]
    }

    transcript = parse_subtitle_json(payload)

    assert len(transcript.lines) == 1
    assert transcript.lines[0].start_seconds == 3.0
    assert transcript.lines[0].end_seconds == 4.0
    assert transcript.lines[0].text == "有效字幕"
