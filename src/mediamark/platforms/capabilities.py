from typing import Any


def platform_capabilities() -> list[dict[str, Any]]:
    return [
        {
            "platform": "bilibili",
            "single_video": True,
            "uploader": True,
            "collection": True,
            "native_subtitle": True,
            "getnote_fallback": True,
            "status": "stable",
        },
        {
            "platform": "douyin",
            "single_video": True,
            "uploader": False,
            "collection": False,
            "native_subtitle": False,
            "getnote_fallback": True,
            "status": "experimental",
        },
        {
            "platform": "xiaohongshu",
            "single_video": True,
            "uploader": False,
            "collection": False,
            "native_subtitle": False,
            "getnote_fallback": True,
            "status": "experimental",
        },
    ]
