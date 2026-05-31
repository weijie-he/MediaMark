from mediamark.bilibili.urls import InputKind, classify_input
from mediamark.models import Platform, VideoItem
from mediamark.platforms.base import ExpansionContext


def filter_selected_part(
    videos: list[VideoItem],
    part_index: int | None,
    input_value: str,
) -> list[VideoItem]:
    if part_index is None:
        return videos
    selected = [video for video in videos if video.part_index == part_index]
    if not selected:
        raise ValueError(f"Could not find part p={part_index} for input: {input_value}")
    return selected


class BilibiliAdapter:
    platform: Platform = "bilibili"

    def matches(self, input_value: str) -> bool:
        return classify_input(input_value).kind != InputKind.FILE

    async def expand(
        self,
        input_value: str,
        context: ExpansionContext,
    ) -> list[VideoItem]:
        classified = classify_input(input_value)

        if classified.kind == InputKind.VIDEO:
            videos = await context.bilibili_client.get_video_by_bvid(classified.value)
            if context.part_selection == "selected":
                return filter_selected_part(videos, classified.part_index, input_value)
            return videos
        if classified.kind == InputKind.UPLOADER:
            return await context.bilibili_client.get_uploader_videos(classified.value)
        if classified.kind == InputKind.COLLECTION:
            return await context.bilibili_client.get_collection_videos(classified.value)
        raise ValueError(f"Unsupported Bilibili input: {input_value}")
