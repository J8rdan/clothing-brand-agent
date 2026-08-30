"""Meta Marketing API connector. Pulls campaign insights to ground recommendations."""
import requests

import config
import tokens

GRAPH = "https://graph.facebook.com/v21.0"


def available() -> bool:
    return bool(tokens.get_meta_token() and config.META_AD_ACCOUNT_ID)


def campaign_insights(days: int = 30) -> list[dict]:
    if not available():
        return []
    r = requests.get(
        f"{GRAPH}/{config.META_AD_ACCOUNT_ID}/insights",
        params={
            "level": "campaign",
            "date_preset": "last_30d" if days == 30 else "last_7d",
            "fields": "campaign_name,spend,impressions,clicks,cpc,cpm,actions,objective",
            "access_token": tokens.get_meta_token(),
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("data", [])


def ad_insights(days: int = 7) -> list[dict]:
    """Per-ad performance for the window."""
    if not available():
        return []
    r = requests.get(
        f"{GRAPH}/{config.META_AD_ACCOUNT_ID}/insights",
        params={
            "level": "ad",
            "date_preset": "last_7d" if days <= 7 else "last_30d",
            "fields": "ad_id,ad_name,adset_name,campaign_name,objective,spend,"
                      "impressions,clicks,ctr,cpc,cpm,frequency,actions",
            "limit": 100,
            "access_token": tokens.get_meta_token(),
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("data", [])


def ad_cta_types() -> dict:
    """Map of ad_id -> CTA button type (SHOP_NOW, SIGN_UP, ...). Best effort."""
    if not available():
        return {}
    try:
        r = requests.get(
            f"{GRAPH}/{config.META_AD_ACCOUNT_ID}/ads",
            params={
                "fields": "id,creative{call_to_action_type}",
                "limit": 200,
                "access_token": tokens.get_meta_token(),
            },
            timeout=30,
        )
        r.raise_for_status()
        return {
            a["id"]: (a.get("creative") or {}).get("call_to_action_type", "?")
            for a in r.json().get("data", [])
        }
    except requests.RequestException:
        return {}
