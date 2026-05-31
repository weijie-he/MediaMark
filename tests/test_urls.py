from mediamark.bilibili.urls import InputKind, classify_input, extract_bvid


def test_extract_bvid_from_video_url():
    assert extract_bvid("https://www.bilibili.com/video/BV1xx411c7mD") == "BV1xx411c7mD"


def test_classify_video_url():
    result = classify_input("https://www.bilibili.com/video/BV1xx411c7mD")

    assert result.kind == InputKind.VIDEO
    assert result.value == "BV1xx411c7mD"
    assert result.part_index is None


def test_classify_bilibili_video_url_with_selected_part():
    result = classify_input("https://www.bilibili.com/video/BV1xx411c7mD?p=2")

    assert result.kind == InputKind.VIDEO
    assert result.value == "BV1xx411c7mD"
    assert result.part_index == 2


def test_classify_bare_bvid_as_video():
    result = classify_input("BV1xx411c7mD")

    assert result.kind == InputKind.VIDEO
    assert result.value == "BV1xx411c7mD"
    assert result.part_index is None


def test_classify_incomplete_bare_bvid_as_file():
    for value in ["BV1", "BV123"]:
        result = classify_input(value)

        assert result.kind == InputKind.FILE
        assert result.value == value


def test_classify_incomplete_video_url_bvid_as_file():
    result = classify_input("https://www.bilibili.com/video/BV1")

    assert result.kind == InputKind.FILE


def test_classify_local_path_containing_bvid_as_file():
    result = classify_input("notes/BV1xx411c7mD.txt")

    assert result.kind == InputKind.FILE
    assert result.value == "notes/BV1xx411c7mD.txt"


def test_classify_bvid_on_untrusted_url_host_as_file():
    result = classify_input("https://evilbilibili.com/video/BV1xx411c7mD")

    assert result.kind == InputKind.FILE


def test_classify_malformed_url_shaped_bvid_inputs_as_file():
    for value in [
        "https:///www.bilibili.com/video/BV1xx411c7mD",
        "https:/www.bilibili.com/video/BV1xx411c7mD",
        "http:///video/BV1xx411c7mD",
    ]:
        result = classify_input(value)

        assert result.kind == InputKind.FILE


def test_classify_space_url():
    result = classify_input("https://space.bilibili.com/123456/video")

    assert result.kind == InputKind.UPLOADER
    assert result.value == "123456"


def test_classify_mid():
    result = classify_input("mid:123456")

    assert result.kind == InputKind.UPLOADER
    assert result.value == "123456"


def test_classify_malformed_mid_as_file():
    for value in ["mid:abc", "mid:"]:
        result = classify_input(value)

        assert result.kind == InputKind.FILE
        assert result.value == value


def test_classify_space_url_with_malformed_mid_as_file():
    result = classify_input("https://space.bilibili.com/not-a-mid/video")

    assert result.kind == InputKind.FILE


def test_classify_favorites_or_series_as_collection():
    result = classify_input("https://www.bilibili.com/medialist/play/123456")

    assert result.kind == InputKind.COLLECTION


def test_classify_medialist_ml_id_as_collection():
    result = classify_input("https://www.bilibili.com/medialist/play/ml123")

    assert result.kind == InputKind.COLLECTION


def test_classify_medialist_path_without_id_as_file():
    result = classify_input("https://www.bilibili.com/medialist")

    assert result.kind == InputKind.FILE


def test_classify_medialist_play_path_without_id_as_file():
    result = classify_input("https://www.bilibili.com/medialist/play")

    assert result.kind == InputKind.FILE


def test_classify_collection_path_as_collection():
    result = classify_input("https://www.bilibili.com/collection/123")

    assert result.kind == InputKind.COLLECTION


def test_classify_www_bilibili_subdomain_collection_path_as_collection():
    result = classify_input("https://www.bilibili.com/collection/123")

    assert result.kind == InputKind.COLLECTION


def test_classify_evil_bilibili_suffix_host_as_file():
    result = classify_input("https://evilbilibili.com/index.html?list=123")

    assert result.kind == InputKind.FILE


def test_classify_non_bilibili_suffix_host_as_file():
    result = classify_input("https://notbilibili.com/collection/123")

    assert result.kind == InputKind.FILE


def test_classify_collection_path_without_id_as_file():
    result = classify_input("https://www.bilibili.com/collection")

    assert result.kind == InputKind.FILE


def test_classify_list_path_as_collection():
    result = classify_input("https://www.bilibili.com/list/123")

    assert result.kind == InputKind.COLLECTION


def test_classify_list_path_without_id_as_file():
    result = classify_input("https://www.bilibili.com/list")

    assert result.kind == InputKind.FILE


def test_classify_space_lists_path_as_collection():
    result = classify_input("https://space.bilibili.com/123456/lists/987")

    assert result.kind == InputKind.COLLECTION


def test_classify_incomplete_space_lists_path_as_file():
    result = classify_input("https://space.bilibili.com/123456/lists")

    assert result.kind == InputKind.FILE


def test_classify_space_series_path_as_collection():
    result = classify_input("https://space.bilibili.com/123456/series/987")

    assert result.kind == InputKind.COLLECTION


def test_classify_incomplete_space_series_path_as_file():
    result = classify_input("https://space.bilibili.com/123456/series")

    assert result.kind == InputKind.FILE


def test_classify_www_lists_path_as_file_without_mid():
    result = classify_input("https://www.bilibili.com/lists/987")

    assert result.kind == InputKind.FILE


def test_classify_bare_series_path_as_file():
    result = classify_input("https://www.bilibili.com/series/123")

    assert result.kind == InputKind.FILE


def test_classify_series_query_ids_as_collection():
    result = classify_input("https://www.bilibili.com/index.html?mid=456&series_id=123")

    assert result.kind == InputKind.COLLECTION


def test_classify_query_list_as_collection_without_bvid():
    result = classify_input("https://www.bilibili.com/index.html?list=123")

    assert result.kind == InputKind.COLLECTION


def test_classify_query_list_with_malformed_id_as_file():
    result = classify_input(
        "https://www.bilibili.com/index.html?list=https://www.bilibili.com/list"
    )

    assert result.kind == InputKind.FILE


def test_classify_query_media_id_with_malformed_id_as_file():
    result = classify_input("https://www.bilibili.com/index.html?media_id=abc")

    assert result.kind == InputKind.FILE


def test_classify_query_fid_with_malformed_id_as_file():
    result = classify_input("https://www.bilibili.com/index.html?fid=abc")

    assert result.kind == InputKind.FILE


def test_classify_local_path_as_file():
    result = classify_input("links.txt")

    assert result.kind == InputKind.FILE
    assert result.value == "links.txt"


def test_classify_local_lists_path_as_file():
    result = classify_input("lists/links.txt")

    assert result.kind == InputKind.FILE
    assert result.value == "lists/links.txt"


def test_classify_local_series_path_as_file():
    result = classify_input("docs/series/input.txt")

    assert result.kind == InputKind.FILE
    assert result.value == "docs/series/input.txt"


def test_classify_blacklist_query_as_file():
    result = classify_input("https://www.bilibili.com/index.html?blacklist=1")

    assert result.kind == InputKind.FILE


def test_classify_space_blacklist_query_as_uploader():
    result = classify_input("https://space.bilibili.com/123456/video?blacklist=1")

    assert result.kind == InputKind.UPLOADER
    assert result.value == "123456"
