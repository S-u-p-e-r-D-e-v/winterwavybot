import asyncio
import os
from datetime import datetime, timezone
from typing import Optional, Any, Dict

from utils import update_live_stats

# TikTokLive imports guarded to allow code import without the package installed
try:
    from TikTokLive import TikTokLiveClient
    from TikTokLive.types.events import (
        ConnectEvent,
        CommentEvent,
        GiftEvent,
        LikeEvent,
        ViewerCountUpdateEvent,
        DisconnectEvent,
    )
except Exception:  # pragma: no cover - during development when deps not installed
    TikTokLiveClient = None  # type: ignore
    ConnectEvent = CommentEvent = GiftEvent = LikeEvent = ViewerCountUpdateEvent = DisconnectEvent = object  # type: ignore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_tiktok_listener(stop_event: Optional[asyncio.Event] = None) -> None:
    """
    Start TikTokLive client and continually update live_stats.json with:
    - connected, viewers, likes, last_comment, last_gift, updated_at

    This coroutine reconnects on errors until stop_event is set.
    """
    username = os.getenv("TIKTOK_USERNAME", "")
    if not username:
        # No username configured; keep stats marked disconnected and exit
        update_live_stats({
            "connected": False,
            "updated_at": _now_iso(),
            "tiktok_username": ""
        })
        return

    if TikTokLiveClient is None:
        # Library not installed
        update_live_stats({
            "connected": False,
            "updated_at": _now_iso(),
            "tiktok_username": username
        })
        return

    # Inner runner with reconnect loop
    while True:
        if stop_event and stop_event.is_set():
            return

        client = TikTokLiveClient(unique_id=username, enable_extended_gift_info=True)

        # We keep local derived like counter only if event does not provide totals
        like_counter: Optional[int] = None

        @client.on("connect")
        async def on_connect(_: ConnectEvent):
            update_live_stats({
                "connected": True,
                "updated_at": _now_iso(),
                "tiktok_username": username
            })

        @client.on("disconnect")
        async def on_disconnect(_: DisconnectEvent):
            update_live_stats({
                "connected": False,
                "updated_at": _now_iso(),
            })

        @client.on("viewer_count")
        async def on_viewer_count(event: ViewerCountUpdateEvent):
            try:
                viewers = getattr(event, "viewerCount", None)
                if viewers is None:
                    viewers = getattr(event, "viewers", None)
                if isinstance(viewers, int):
                    update_live_stats({
                        "viewers": viewers,
                        "updated_at": _now_iso(),
                    })
            except Exception:
                pass

        @client.on("like")
        async def on_like(event: LikeEvent):
            nonlocal like_counter
            try:
                total_likes = getattr(event, "totalLikes", None)
                if isinstance(total_likes, int):
                    like_counter = total_likes
                else:
                    increment = getattr(event, "likeCount", None)
                    if not isinstance(increment, int):
                        increment = getattr(event, "count", 1) or 1
                    if like_counter is None:
                        like_counter = 0
                    like_counter += int(increment)
                update_live_stats({
                    "likes": int(like_counter or 0),
                    "updated_at": _now_iso(),
                })
            except Exception:
                pass

        @client.on("comment")
        async def on_comment(event: CommentEvent):
            try:
                user = None
                if hasattr(event, "user") and event.user is not None:
                    user = getattr(event.user, "uniqueId", None) or getattr(event.user, "nickname", None)
                data: Dict[str, Any] = {
                    "user": user,
                    "comment": getattr(event, "comment", None)
                }
                update_live_stats({
                    "last_comment": data,
                    "updated_at": _now_iso(),
                })
            except Exception:
                pass

        @client.on("gift")
        async def on_gift(event: GiftEvent):
            try:
                gift = getattr(event, "gift", None)
                gift_name = getattr(gift, "name", None) if gift else None
                repeat_count = getattr(event, "repeatCount", None)
                if repeat_count is None:
                    repeat_count = getattr(event, "count", None)
                user = None
                if hasattr(event, "user") and event.user is not None:
                    user = getattr(event.user, "uniqueId", None) or getattr(event.user, "nickname", None)
                data: Dict[str, Any] = {
                    "user": user,
                    "gift": gift_name,
                    "repeat_count": repeat_count,
                }
                update_live_stats({
                    "last_gift": data,
                    "updated_at": _now_iso(),
                })
            except Exception:
                pass

        try:
            await client.start()
        except Exception:
            update_live_stats({
                "connected": False,
                "updated_at": _now_iso(),
            })
            # Backoff before reconnect
            try:
                await asyncio.wait_for(asyncio.sleep(5), timeout=5)
            except asyncio.CancelledError:
                return
            continue
        finally:
            # Ensure we mark disconnected when the client loop ends
            update_live_stats({
                "connected": False,
                "updated_at": _now_iso(),
            })

        # Normal exit
        return
