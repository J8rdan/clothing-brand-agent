"""TikTok connector with CSV fallback.

API mode: pulls your own videos + stats via the TikTok Display API v2.
Requires TIKTOK_ACCESS_TOKEN in .env — a user access token with the
`video.list` scope, obtained through a TikTok developer app (OAuth).
Docs: https://developers.tiktok.com/doc/display-api-get-started

Manual mode: reads data/my_tiktoks.csv with columns:
    caption,views,likes,comments,shares,saves,posted_at,url
Any missing numeric column is treated as 0.
"""
import csv
import os

import requests

import config
import tokens as token_mgr

def _token() -> str:
    return token_mgr.get_tiktok_token()
MY_TIKTOKS_CSV = config.DATA_DIR / "my_tiktoks.csv"

VIDEO_LIST_URL = "https://open.tiktokapis.com/v2/video/list/"
VIDEO_FIELDS = (
    "id,title,video_description,create_time,share_url,"
    "view_count,like_count,comment_count,share_count"
)


def available() -> bool:
    return bool(_token())


def fetch_my_posts(limit: int = 20) -> list[dict]:
    """Return recent TikToks as normalized dicts (same shape as instagram connector)."""
    if available():
        try:
            return _fetch_api(limit)
        except requests.RequestException as e:
            print(f"[tiktok] API error, falling back to CSV: {e}")
    return _fetch_csv()


def _fetch_api(limit: int) -> list[dict]:
    posts = []
    cursor = None
    while len(posts) < limit:
        body = {"max_count": min(20, limit - len(posts))}
        if cursor:
            body["cursor"] = cursor
        r = requests.post(
            VIDEO_LIST_URL,
            params={"fields": VIDEO_FIELDS},
            headers={
                "Authorization": f"Bearer {_token()}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json().get("data", {})
        for v in data.get("videos", []):
            posts.append(
                {
                    "platform": "tiktok",
                    "caption": v.get("video_description") or v.get("title", ""),
                    "media_type": "TIKTOK_VIDEO",
                    "likes": v.get("like_count", 0),
                    "comments": v.get("comment_count", 0),
                    "saves": 0,  # not exposed by Display API
                    "shares": v.get("share_count", 0),
                    "reach": 0,
                    "views": v.get("view_count", 0),
                    "posted_at": str(v.get("create_time", "")),
                    "url": v.get("share_url", ""),
                }
            )
        if not data.get("has_more"):
            break
        cursor = data.get("cursor")
    return posts


def _fetch_csv() -> list[dict]:
    if not MY_TIKTOKS_CSV.exists():
        return []
    posts = []
    with open(MY_TIKTOKS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            posts.append(
                {
                    "platform": "tiktok",
                    "caption": row.get("caption", ""),
                    "media_type": "TIKTOK_VIDEO",
                    "likes": _num(row.get("likes")),
                    "comments": _num(row.get("comments")),
                    "saves": _num(row.get("saves")),
                    "shares": _num(row.get("shares")),
                    "reach": 0,
                    "views": _num(row.get("views")),
                    "posted_at": row.get("posted_at", ""),
                    "url": row.get("url", ""),
                }
            )
    return posts


def _num(v) -> int:
    try:
        return int(float(str(v).replace(",", "").strip() or 0))
    except (ValueError, TypeError):
        return 0
