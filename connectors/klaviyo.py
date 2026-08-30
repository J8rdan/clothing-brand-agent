"""Klaviyo connector: tracks email/SMS list growth.

Needs a PRIVATE API key (Klaviyo -> Settings -> API keys -> create, read-only
scope for Lists + Profiles is enough). The public site key (used in signup
forms) cannot read data.

.env:
    KLAVIYO_PRIVATE_KEY=pk_...
    KLAVIYO_LIST_ID=xxxxxx      (your main list; find the ID in its Klaviyo URL)

Each run snapshots counts to data/klaviyo_history.json so weekly reports can
show week-over-week growth even where the API filter misses backfilled joins.
"""
import datetime
import json
import os

import requests

import config

KLAVIYO_PRIVATE_KEY = os.getenv("KLAVIYO_PRIVATE_KEY", "")
KLAVIYO_LIST_ID = os.getenv("KLAVIYO_LIST_ID", "")

BASE = "https://a.klaviyo.com/api"
REVISION = "2024-10-15"
HISTORY_FILE = config.DATA_DIR / "klaviyo_history.json"


def available() -> bool:
    return bool(KLAVIYO_PRIVATE_KEY)


def _headers() -> dict:
    return {
        "Authorization": f"Klaviyo-API-Key {KLAVIYO_PRIVATE_KEY}",
        "revision": REVISION,
        "accept": "application/json",
    }


def total_count() -> int:
    r = requests.get(
        f"{BASE}/lists/{KLAVIYO_LIST_ID}",
        params={"additional-fields[list]": "profile_count"},
        headers=_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["data"]["attributes"].get("profile_count", 0)


def joined_since(days: int = 7) -> dict:
    """Profiles that joined the list in the window, split email vs SMS."""
    since = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{BASE}/lists/{KLAVIYO_LIST_ID}/profiles"
    params = {
        "filter": f"greater-than(joined_group_at,{since})",
        "page[size]": 100,
        "fields[profile]": "email,phone_number",
    }
    new_total, with_email, with_sms = 0, 0, 0
    while url:
        r = requests.get(url, params=params, headers=_headers(), timeout=30)
        r.raise_for_status()
        d = r.json()
        for p in d.get("data", []):
            attrs = p.get("attributes", {})
            new_total += 1
            if attrs.get("email"):
                with_email += 1
            if attrs.get("phone_number"):
                with_sms += 1
        url = (d.get("links") or {}).get("next")
        params = None  # next link carries its own params
    return {"new": new_total, "email": with_email, "sms": with_sms, "since_days": days}


def _history() -> list[dict]:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def snapshot() -> dict:
    """Record today's total; return today's entry. Called by reports."""
    total = total_count()
    today = datetime.date.today().isoformat()
    hist = _history()
    hist = [h for h in hist if h["date"] != today]
    hist.append({"date": today, "total": total})
    hist = hist[-120:]  # keep ~4 months
    HISTORY_FILE.write_text(json.dumps(hist, indent=2), encoding="utf-8")
    return {"date": today, "total": total}


def stats(days: int = 7) -> dict:
    """Full growth picture: current total, joins in window, and history-based delta."""
    out = {"list_id": KLAVIYO_LIST_ID}
    out.update(joined_since(days))
    snap = snapshot()
    out["total"] = snap["total"]

    hist = _history()
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    older = [h for h in hist if h["date"] <= cutoff]
    if older:
        out["total_delta_vs_history"] = snap["total"] - older[-1]["total"]
    return out
