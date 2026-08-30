"""Merged content fetcher: combines Instagram + TikTok posts into one list."""
from connectors import instagram, tiktok


def fetch_all(limit_per_platform: int = 30) -> list[dict]:
    posts = []
    for p in instagram.fetch_my_posts(limit_per_platform):
        p.setdefault("platform", "instagram")
        posts.append(p)
    posts.extend(tiktok.fetch_my_posts(limit_per_platform))
    return posts
