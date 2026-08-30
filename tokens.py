"""Token manager: stores and auto-refreshes Meta + TikTok tokens.

Tokens live in data/tokens.json (kept out of .env so the agent can rewrite them).
.env still holds the app credentials used to perform refreshes:

    META_APP_ID / META_APP_SECRET          -> refreshes the Meta long-lived token
    TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET -> refreshes the TikTok token pair

Every CLI command calls ensure_fresh() on startup, so as long as the daily
report runs, tokens never expire:
  - Meta long-lived token (60d): refreshed once it's >40 days old
  - TikTok access token (24h): refreshed once it's >20 hours old
    (refresh token lasts 365d and is rotated on every refresh)

Initial setup:
  python agent.py auth tiktok    guided OAuth login for TikTok
  python agent.py auth meta      store your Meta long-lived token
  python agent.py auth status    see token ages and health
"""
import json
import os
import time
import urllib.parse

import requests

import config

TOKENS_FILE = config.DATA_DIR / "tokens.json"

META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
TIKTOK_REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI", "")

TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
GRAPH = "https://graph.facebook.com/v21.0"

META_REFRESH_AFTER = 40 * 24 * 3600   # refresh 60d token after 40d
TIKTOK_REFRESH_AFTER = 20 * 3600      # refresh 24h token after 20h


# ---------- store ----------

def _load() -> dict:
    if TOKENS_FILE.exists():
        try:
            return json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save(store: dict):
    TOKENS_FILE.write_text(json.dumps(store, indent=2), encoding="utf-8")


def get_meta_token() -> str:
    """Stored token wins; falls back to .env values."""
    tok = _load().get("meta", {}).get("access_token", "")
    return tok or config.META_ACCESS_TOKEN or config.IG_ACCESS_TOKEN


def get_tiktok_token() -> str:
    tok = _load().get("tiktok", {}).get("access_token", "")
    return tok or os.getenv("TIKTOK_ACCESS_TOKEN", "")


# ---------- refresh ----------

def ensure_fresh(verbose: bool = False):
    """Refresh anything close to expiry. Safe to call on every run; silent no-op
    when nothing is stored or nothing needs refreshing."""
    store = _load()
    now = time.time()

    meta = store.get("meta")
    if meta and META_APP_ID and META_APP_SECRET:
        if now - meta.get("obtained_at", 0) > META_REFRESH_AFTER:
            try:
                _refresh_meta(store)
                if verbose:
                    print("[tokens] Meta token refreshed")
            except requests.RequestException as e:
                print(f"[tokens] WARNING: Meta refresh failed: {e} — "
                      "re-run `python agent.py auth meta` before it expires")

    tt = store.get("tiktok")
    if tt and TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET:
        if now - tt.get("obtained_at", 0) > TIKTOK_REFRESH_AFTER:
            try:
                _refresh_tiktok(store)
                if verbose:
                    print("[tokens] TikTok token refreshed")
            except requests.RequestException as e:
                print(f"[tokens] WARNING: TikTok refresh failed: {e} — "
                      "re-run `python agent.py auth tiktok` if pulls stop working")


def _refresh_meta(store: dict):
    r = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": META_APP_ID,
            "client_secret": META_APP_SECRET,
            "fb_exchange_token": store["meta"]["access_token"],
        },
        timeout=30,
    )
    r.raise_for_status()
    store["meta"] = {"access_token": r.json()["access_token"], "obtained_at": time.time()}
    _save(store)


def _refresh_tiktok(store: dict):
    r = requests.post(
        TIKTOK_TOKEN_URL,
        data={
            "client_key": TIKTOK_CLIENT_KEY,
            "client_secret": TIKTOK_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": store["tiktok"]["refresh_token"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    if "access_token" not in d:
        raise requests.RequestException(f"TikTok refresh error: {d}")
    store["tiktok"] = {
        "access_token": d["access_token"],
        "refresh_token": d.get("refresh_token", store["tiktok"]["refresh_token"]),
        "obtained_at": time.time(),
    }
    _save(store)


# ---------- initial auth flows ----------

def token_doctor() -> str:
    """Diagnose why Meta/TikTok tokens may be missing or stale."""
    lines = ["TOKEN DIAGNOSTICS", "=" * 46]
    lines.append(f"tokens file: {TOKENS_FILE}")
    lines.append(f"  exists: {TOKENS_FILE.exists()}")
    if TOKENS_FILE.exists():
        try:
            raw = TOKENS_FILE.read_text(encoding="utf-8")
            store = json.loads(raw)
            lines.append(f"  size: {len(raw)} bytes, keys: {list(store.keys()) or 'none'}")
        except Exception as e:  # noqa: BLE001
            store = {}
            lines.append(f"  UNREADABLE: {e}")
    else:
        store = {}
        lines.append("  -> No token file. Nothing was ever stored here, OR it was")
        lines.append("     removed (fresh unzip / different folder / sync cleanup).")

    meta = store.get("meta", {})
    if meta.get("access_token"):
        age_days = (time.time() - meta.get("obtained_at", 0)) / 86400
        lines.append("")
        lines.append(f"Meta token: present, ~{age_days:.1f} days old")
        if age_days > 60:
            lines.append("  EXPIRED (>60d). Re-run: python agent.py auth meta")
        elif age_days > 40:
            lines.append("  Due for refresh; runs automatically next command.")
    else:
        lines.append("")
        lines.append("Meta token: NOT SET -> run: python agent.py auth meta")

    lines.append("")
    lines.append("Refresh credentials in .env:")
    lines.append(f"  META_APP_ID:     {'set' if META_APP_ID else 'MISSING'}")
    lines.append(f"  META_APP_SECRET: {'set' if META_APP_SECRET else 'MISSING'}")
    if not (META_APP_ID and META_APP_SECRET):
        lines.append("  -> Without both, a stored token can't auto-refresh and dies at 60d.")

    # writability check
    lines.append("")
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        probe = config.DATA_DIR / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        lines.append(f"data folder writable: YES ({config.DATA_DIR})")
    except Exception as e:  # noqa: BLE001
        lines.append(f"data folder writable: NO -> {e}")
        lines.append("  This is likely why the token won't stick.")

    # OneDrive / sync heuristic
    p = str(config.DATA_DIR).lower()
    if "onedrive" in p or "dropbox" in p:
        lines.append("")
        lines.append("NOTE: this folder is inside a cloud-sync path (OneDrive/Dropbox).")
        lines.append("  Sync can lock or roll back tokens.json. If drops keep happening,")
        lines.append("  move the agent to a plain local folder like C:\\cb-agent.")
    return "\n".join(lines)


def auth_meta():
    """Store the Meta long-lived token (pasted from Graph API Explorer)."""
    print("Paste your Meta LONG-LIVED user access token")
    print("(Graph API Explorer -> generate token -> Debug -> Extend Access Token):")
    token = input("token> ").strip()
    if not token:
        print("Nothing entered.")
        return
    # Verify it works before storing
    r = requests.get(f"{GRAPH}/me", params={"access_token": token}, timeout=30)
    if not r.ok:
        print(f"Token check failed: {r.text[:300]}")
        return
    store = _load()
    store["meta"] = {"access_token": token, "obtained_at": time.time()}
    _save(store)
    # Verify the write actually landed — catch silent persistence failures.
    check = _load().get("meta", {}).get("access_token", "")
    name = r.json().get("name", "?")
    if check == token:
        print(f"Stored OK. Authenticated as: {name}")
        print(f"Token saved to: {TOKENS_FILE}")
    else:
        print("!! WARNING: token did NOT persist to disk.")
        print(f"   Tried to write: {TOKENS_FILE}")
        print("   Check that folder is writable and not blocked by OneDrive sync.")
    if not (META_APP_ID and META_APP_SECRET):
        print("NOTE: add META_APP_ID and META_APP_SECRET to .env to enable auto-refresh,")
        print("      or this token expires in ~60 days with no renewal.")


def auth_tiktok():
    """Guided TikTok OAuth: prints the login URL, exchanges the returned code."""
    if not (TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET and TIKTOK_REDIRECT_URI):
        print("Add TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, and TIKTOK_REDIRECT_URI "
              "to .env first (from your app at developers.tiktok.com — the redirect "
              "URI must exactly match one registered on the app).")
        return
    params = {
        "client_key": TIKTOK_CLIENT_KEY,
        "scope": "user.info.basic,video.list",
        "response_type": "code",
        "redirect_uri": TIKTOK_REDIRECT_URI,
        "state": "cb-agent",
    }
    url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)
    print("1. Open this URL in your browser and log in with the @cb-agent.st account:\n")
    print(url)
    print("\n2. After approving, you'll land on your redirect URI with ?code=... in "
          "the address bar (the page itself may 404 — that's fine).")
    print("3. Paste the FULL redirected URL here:")
    redirected = input("url> ").strip()
    try:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(redirected).query)
        code = qs["code"][0]
    except (KeyError, IndexError):
        print("Couldn't find ?code= in that URL.")
        return
    r = requests.post(
        TIKTOK_TOKEN_URL,
        data={
            "client_key": TIKTOK_CLIENT_KEY,
            "client_secret": TIKTOK_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": TIKTOK_REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    d = r.json()
    if "access_token" not in d:
        print(f"Exchange failed: {d}")
        return
    store = _load()
    store["tiktok"] = {
        "access_token": d["access_token"],
        "refresh_token": d["refresh_token"],
        "obtained_at": time.time(),
    }
    _save(store)
    print("TikTok connected. Tokens stored and will auto-refresh on every run.")


def auth_status():
    store = _load()
    now = time.time()
    print("TOKEN STATUS")
    meta = store.get("meta")
    if meta:
        age_d = (now - meta.get("obtained_at", 0)) / 86400
        print(f"  Meta: stored, {age_d:.1f} days old "
              f"(auto-refresh at 40d{'' if META_APP_ID and META_APP_SECRET else ' — NEEDS META_APP_ID/SECRET in .env'})")
    else:
        print(f"  Meta: {'using .env token (no auto-refresh — run auth meta)' if get_meta_token() else 'not set'}")
    tt = store.get("tiktok")
    if tt:
        age_h = (now - tt.get("obtained_at", 0)) / 3600
        print(f"  TikTok: stored, {age_h:.1f} hours old (auto-refresh at 20h)")
    else:
        print(f"  TikTok: {'using .env token (no auto-refresh — run auth tiktok)' if get_tiktok_token() else 'not set'}")
