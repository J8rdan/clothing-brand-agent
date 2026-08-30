"""Central config. Loads .env, exposes credentials, detects which mode each connector runs in."""
import os
from pathlib import Path

ENV_PATH = Path(__file__).parent / ".env"
ENV_WARNING = ""

try:
    from dotenv import load_dotenv
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)
    else:
        ENV_WARNING = (
            f"No .env file found at {ENV_PATH}\n"
            "   Copy .env.example to .env and add your keys, or run "
            '"1 - SETUP (run once).bat"'
        )
except ImportError:
    ENV_WARNING = (
        "python-dotenv is not installed, so your .env file is being IGNORED.\n"
        "   Fix: pip install -r requirements.txt   (or run "
        '"1 - SETUP (run once).bat")'
    )

# --- Anthropic (required for all AI features) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

# --- Instagram Graph API (optional) ---
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")
IG_BUSINESS_ID = os.getenv("IG_BUSINESS_ID", "")  # your IG business account ID

# --- Meta Marketing API (optional) ---
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", IG_ACCESS_TOKEN)
META_AD_ACCOUNT_ID = os.getenv("META_AD_ACCOUNT_ID", "")  # act_XXXXXXXX

# --- Shopify Admin API (optional) ---
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE", "")  # e.g. your-store.myshopify.com
SHOPIFY_ADMIN_TOKEN = os.getenv("SHOPIFY_ADMIN_TOKEN", "")  # legacy apps only
# New Dev Dashboard apps: client credentials, exchanged for a token automatically
SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET", "")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-07")

# --- Brand context injected into every LLM call ---


DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# YOUR BRAND
# The agent reads your brand profile from data/brand.txt. Every AI call gets this
# text, so it knows who you are, what you sell, and how you sound. Edit that file
# (or run: python agent.py setup) — you should not need to edit this code.
# ---------------------------------------------------------------------------
BRAND_FILE = Path(__file__).parent / "data" / "brand.txt"

_BRAND_PLACEHOLDER = """
No brand profile set up yet.

Run:  python agent.py setup
...or edit data/brand.txt and describe your brand: name, website, what you sell,
your aesthetic, your hero product, which channels you use, and who you're for.
""".strip()


def _load_brand() -> str:
    """Brand profile from data/brand.txt, or BRAND_CONTEXT in .env, or a placeholder."""
    env_brand = os.getenv("BRAND_CONTEXT", "").strip()
    if env_brand:
        return env_brand
    try:
        if BRAND_FILE.exists():
            text = BRAND_FILE.read_text(encoding="utf-8").strip()
            # ignore a file that's still all comments/blank
            body = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#")).strip()
            if body:
                return body
    except OSError:
        pass
    return _BRAND_PLACEHOLDER


BRAND_CONTEXT = _load_brand()


def brand_is_configured() -> bool:
    return BRAND_CONTEXT != _BRAND_PLACEHOLDER


def connector_status() -> dict:
    """Reports what the connectors can ACTUALLY use, including tokens stored by
    `auth meta` / `auth tiktok` in data/tokens.json — not just .env variables."""
    try:
        import tokens as _tok
        meta_token = _tok.get_meta_token()
        tiktok_token = _tok.get_tiktok_token()
    except Exception:
        meta_token = META_ACCESS_TOKEN or IG_ACCESS_TOKEN
        tiktok_token = os.getenv("TIKTOK_ACCESS_TOKEN", "")
    return {
        "anthropic": bool(ANTHROPIC_API_KEY),
        "instagram": bool(meta_token and IG_BUSINESS_ID),
        "meta_ads": bool(meta_token and META_AD_ACCOUNT_ID),
        "tiktok": bool(tiktok_token),
        "klaviyo": bool(os.getenv("KLAVIYO_PRIVATE_KEY", "")),
        "shopify": bool(SHOPIFY_STORE and (SHOPIFY_ADMIN_TOKEN or (SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET))),
    }
