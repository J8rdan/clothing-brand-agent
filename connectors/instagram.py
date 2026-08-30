"""Instagram Graph API connector with CSV fallback.

API mode: pulls your own media + insights via the IG Graph API.
Manual mode: reads data/my_posts.csv with columns:
    caption,media_type,likes,comments,saves,shares,reach,views,posted_at,url
Any missing numeric column is treated as 0.
"""
import csv

import requests

import config
import tokens

GRAPH = "https://graph.facebook.com/v21.0"
MY_POSTS_CSV = config.DATA_DIR / "my_posts.csv"


def _token() -> str:
    return tokens.get_meta_token()


def available() -> bool:
    return bool(_token() and config.IG_BUSINESS_ID)


def fetch_my_posts(limit: int = 30) -> list[dict]:
    """Return recent posts as normalized dicts. Uses API if configured, else CSV."""
    if available():
        return _fetch_api(limit)
    return _fetch_csv()


def _fetch_api(limit: int) -> list[dict]:
    fields = (
        "id,caption,media_type,media_product_type,permalink,timestamp,"
        "like_count,comments_count"
    )
    r = requests.get(
        f"{GRAPH}/{config.IG_BUSINESS_ID}/media",
        params={"fields": fields, "limit": limit, "access_token": _token()},
        timeout=30,
    )
    r.raise_for_status()
    posts = []
    for m in r.json().get("data", []):
        post = {
            "caption": m.get("caption", ""),
            "media_type": m.get("media_product_type") or m.get("media_type", ""),
            "likes": m.get("like_count", 0),
            "comments": m.get("comments_count", 0),
            "saves": 0,
            "shares": 0,
            "reach": 0,
            "views": 0,
            "posted_at": m.get("timestamp", ""),
            "url": m.get("permalink", ""),
        }
        # Per-media insights (best effort; metric names vary by media type)
        try:
            ir = requests.get(
                f"{GRAPH}/{m['id']}/insights",
                params={
                    "metric": "reach,saved,shares,views",
                    "access_token": _token(),
                },
                timeout=30,
            )
            if ir.ok:
                for metric in ir.json().get("data", []):
                    val = (metric.get("values") or [{}])[0].get("value", 0)
                    name = metric.get("name")
                    if name == "reach":
                        post["reach"] = val
                    elif name == "saved":
                        post["saves"] = val
                    elif name == "shares":
                        post["shares"] = val
                    elif name == "views":
                        post["views"] = val
        except requests.RequestException:
            pass
        posts.append(post)
    return posts


def _fetch_csv() -> list[dict]:
    if not MY_POSTS_CSV.exists():
        return []
    posts = []
    with open(MY_POSTS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            posts.append(
                {
                    "caption": row.get("caption", ""),
                    "media_type": row.get("media_type", "REELS"),
                    "likes": _num(row.get("likes")),
                    "comments": _num(row.get("comments")),
                    "saves": _num(row.get("saves")),
                    "shares": _num(row.get("shares")),
                    "reach": _num(row.get("reach")),
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
