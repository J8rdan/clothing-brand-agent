"""Shopify Admin API connector. Pulls store data used by the improvement advisor."""
import time

import requests

import config

# Client Credentials Grant: Shopify's new Dev Dashboard no longer exposes a
# permanent shpat_ token in the UI. Apps exchange client_id + client_secret for
# a short-lived Admin API token instead. We cache it and refetch when it ages out.
_ccg_cache = {"token": "", "expires_at": 0.0}


def _ccg_token() -> str:
    """Fetch (or reuse) an Admin API token via client credentials."""
    if not (config.SHOPIFY_CLIENT_ID and config.SHOPIFY_CLIENT_SECRET):
        return ""
    if _ccg_cache["token"] and time.time() < _ccg_cache["expires_at"]:
        return _ccg_cache["token"]
    r = requests.post(
        f"https://{config.SHOPIFY_STORE}/admin/oauth/access_token",
        json={
            "client_id": config.SHOPIFY_CLIENT_ID,
            "client_secret": config.SHOPIFY_CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    tok = d.get("access_token", "")
    # expires_in is seconds; refresh a couple of minutes early
    _ccg_cache["token"] = tok
    _ccg_cache["expires_at"] = time.time() + max(60, int(d.get("expires_in", 3600)) - 120)
    return tok


def _token() -> str:
    """Prefer an explicit token if the store has a legacy one; else use CCG."""
    return config.SHOPIFY_ADMIN_TOKEN or _ccg_token()


def available() -> bool:
    if not config.SHOPIFY_STORE:
        return False
    return bool(config.SHOPIFY_ADMIN_TOKEN or (config.SHOPIFY_CLIENT_ID and config.SHOPIFY_CLIENT_SECRET))


def _get(path: str, params: dict | None = None):
    r = requests.get(
        f"https://{config.SHOPIFY_STORE}/admin/api/{config.SHOPIFY_API_VERSION}/{path}",
        headers={"X-Shopify-Access-Token": _token()},
        params=params or {},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def store_snapshot() -> dict:
    """Compact snapshot of products, orders, and store setup for the advisor."""
    snap: dict = {}
    try:
        products = _get("products.json", {"limit": 50}).get("products", [])
        snap["products"] = [
            {
                "title": p.get("title"),
                "status": p.get("status"),
                "tags": p.get("tags"),
                "body_html_length": len(p.get("body_html") or ""),
                "images": len(p.get("images") or []),
                "variants": len(p.get("variants") or []),
                "price": (p.get("variants") or [{}])[0].get("price"),
            }
            for p in products
        ]
    except requests.RequestException as e:
        snap["products_error"] = str(e)

    try:
        orders = _get(
            "orders.json", {"limit": 50, "status": "any", "fields": "total_price,created_at,referring_site,landing_site"}
        ).get("orders", [])
        snap["recent_orders_count"] = len(orders)
        snap["recent_orders"] = orders[:20]
    except requests.RequestException as e:
        snap["orders_error"] = str(e)

    try:
        shop = _get("shop.json").get("shop", {})
        snap["shop"] = {
            "domain": shop.get("domain"),
            "currency": shop.get("currency"),
            "checkout_api_supported": shop.get("checkout_api_supported"),
        }
    except requests.RequestException as e:
        snap["shop_error"] = str(e)

    return snap
