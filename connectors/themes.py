"""Shopify theme connector: safe theme editing with drafts, backups, and publish.

Safety model:
  - Prefers editing an UNPUBLISHED draft theme (create one in Shopify admin:
    Online Store -> Themes -> ... -> Duplicate, rename to include "draft" or "agent").
  - If no draft exists, falls back to the live theme WITH a warning.
  - Every asset is backed up to data/site_backups/ before any write; rollback restores.
  - Publishing the draft to live always requires explicit confirmation.

Custom app token needs scopes: read_themes, write_themes (add in the same
custom app used for products/orders).
"""
import datetime
import json

import requests

import config
from connectors.shopify import _token as _shop_token

BACKUPS_DIR = config.DATA_DIR / "site_backups"


def available() -> bool:
    from connectors import shopify as _shop
    return _shop.available()


def _req(method: str, path: str, **kwargs):
    r = requests.request(
        method,
        f"https://{config.SHOPIFY_STORE}/admin/api/{config.SHOPIFY_API_VERSION}/{path}",
        headers={
            "X-Shopify-Access-Token": _shop_token(),
            "Content-Type": "application/json",
        },
        timeout=45,
        **kwargs,
    )
    if r.status_code in (401, 403):
        raise PermissionError(
            "Shopify denied access to themes (HTTP %d). Your app's token is missing the "
            "read_themes / write_themes scopes, so site editing can't run yet.\n\n"
            "Everything else (orders, products, the debrief) still works — only the "
            "site-editing commands need these scopes.\n\n"
            "To enable them you'll add the scopes via the Shopify CLI (Node.js + "
            "`shopify app deploy`) and reinstall the app. This is optional and safe to "
            "skip until after a drop." % r.status_code
        )
    r.raise_for_status()
    return r.json() if r.text else {}


def themes() -> list[dict]:
    return _req("GET", "themes.json").get("themes", [])


def live_theme() -> dict | None:
    return next((t for t in themes() if t.get("role") == "main"), None)


def draft_theme() -> dict | None:
    """An unpublished theme whose name suggests it's the working draft."""
    candidates = [t for t in themes() if t.get("role") == "unpublished"]
    for t in candidates:
        if any(w in (t.get("name") or "").lower() for w in ("draft", "agent", "dev")):
            return t
    return candidates[0] if candidates else None


def working_theme() -> tuple[dict, bool]:
    """Returns (theme, is_draft). Falls back to live if no draft exists."""
    d = draft_theme()
    if d:
        return d, True
    return live_theme(), False


def list_assets(theme_id: int) -> list[str]:
    assets = _req("GET", f"themes/{theme_id}/assets.json").get("assets", [])
    return [a["key"] for a in assets]


def read_asset(theme_id: int, key: str) -> str:
    a = _req("GET", f"themes/{theme_id}/assets.json", params={"asset[key]": key}).get("asset", {})
    return a.get("value") or ""


def _backup(theme_id: int, key: str, content: str):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = key.replace("/", "__")
    d = BACKUPS_DIR / str(theme_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{stamp}__{safe}").write_text(content, encoding="utf-8")


def write_asset(theme_id: int, key: str, value: str) -> None:
    """Backs up the current version, then writes the new one."""
    try:
        current = read_asset(theme_id, key)
        if current:
            _backup(theme_id, key, current)
    except requests.RequestException:
        pass  # new file — nothing to back up
    _req("PUT", f"themes/{theme_id}/assets.json", json={"asset": {"key": key, "value": value}})


def rollback(theme_id: int, key: str) -> str:
    """Restore the most recent backup of an asset."""
    safe = key.replace("/", "__")
    d = BACKUPS_DIR / str(theme_id)
    if not d.exists():
        return f"No backups for theme {theme_id}."
    matches = sorted(d.glob(f"*__{safe}"))
    if not matches:
        return f"No backups found for {key}."
    content = matches[-1].read_text(encoding="utf-8")
    _req("PUT", f"themes/{theme_id}/assets.json", json={"asset": {"key": key, "value": content}})
    return f"Restored {key} from backup {matches[-1].name.split('__')[0]}."


def preview_url(theme_id: int) -> str:
    domain = config.SHOPIFY_STORE  # myshopify domain always works
    return f"https://{domain}/?preview_theme_id={theme_id}"


def publish(theme_id: int) -> str:
    _req("PUT", f"themes/{theme_id}.json", json={"theme": {"id": theme_id, "role": "main"}})
    return f"Theme {theme_id} is now LIVE."
