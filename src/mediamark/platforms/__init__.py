from mediamark.models import Platform
from mediamark.platforms.base import ExpansionContext, PlatformAdapter
from mediamark.platforms.bilibili import BilibiliAdapter
from mediamark.platforms.douyin import DouyinAdapter
from mediamark.platforms.xiaohongshu import XiaohongshuAdapter


_ADAPTERS: tuple[PlatformAdapter, ...] = (
    BilibiliAdapter(),
    DouyinAdapter(),
    XiaohongshuAdapter(),
)


def adapter_for_input(input_value: str) -> PlatformAdapter | None:
    for adapter in _ADAPTERS:
        if adapter.matches(input_value):
            return adapter
    return None


def adapter_for_platform(platform: Platform) -> PlatformAdapter:
    for adapter in _ADAPTERS:
        if adapter.platform == platform:
            return adapter
    raise ValueError(f"Unsupported platform: {platform}")


__all__ = [
    "ExpansionContext",
    "PlatformAdapter",
    "adapter_for_input",
    "adapter_for_platform",
]
