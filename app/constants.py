"""Application-wide constants. No magic numbers outside this module."""
from __future__ import annotations

APP_NAME = "ParaLate"
APP_VERSION = "1.0.0"
ORG_NAME = "ParaLate"
APP_SLUG = "ParaLate"

# --- FREE / PREMIUM limits -------------------------------------------------
FREE_DAILY_TRANSLATION_LIMIT = 3
FREE_PAGE_LIMIT = 30

# --- Translation -----------------------------------------------------------
DEFAULT_TRANSLATION_PROVIDER = "google"
ALLOW_PROVIDER_FALLBACK = True
TRANSLATE_MAX_CHARS = 3500          # per-request chunk ceiling
TRANSLATE_RETRY_ATTEMPTS = 2        # retries after the first try (transient only)
TRANSLATE_RETRY_BACKOFF = 0.75      # seconds, exponential base
TRANSLATE_HTTP_TIMEOUT = 20.0       # seconds per HTTP call
PROVIDER_ORDER = ("google", "mymemory", "microsoft", "libretranslate")

# --- Network status --------------------------------------------------------
NETWORK_CHECK_TIMEOUT = 3.0
NETWORK_CACHE_TTL = 12.0

# --- PDF rendering ---------------------------------------------------------
MIN_TRANSLATED_FONT_SIZE = 6.0      # readability floor, pt
FONT_SIZE_STEP = 0.5                # shrink step, pt
DEFAULT_LINE_RATIO = 1.22           # fallback line height / font size
REDACT_PAD_POINTS = 1.5             # padding around redaction boxes
MAX_PAGE_EDGE_MARGIN = 18.0         # text never crosses this page margin

# --- Viewer ----------------------------------------------------------------
VIEWER_MIN_ZOOM = 0.25
VIEWER_MAX_ZOOM = 4.0
VIEWER_ZOOM_STEP = 1.15
VIEWER_CACHE_SPREADS = 32           # LRU page-pair pixmaps (increased for smoother scrolling)
SPREAD_GAP_PX = 14                  # gap between the two pages
SPREAD_MARGIN_PX = 18

# --- Storage ---------------------------------------------------------------
ENCRYPTION_VERSION = 1
PLT_MAGIC = b"PLT\x01"
KEYRING_SERVICE = "ParaLate"
MASTER_KEY_ENTRY = "master_key"

# --- Languages -------------------------------------------------------------
UI_LANGUAGES: list[tuple[str, str]] = [
    ("tr", "Türkçe"),
    ("en", "English"),
]

# (code, native name) offered as translation targets / sources.
LANGUAGE_CHOICES: list[tuple[str, str]] = [
    ("tr", "Türkçe"),
    ("en", "English"),
    ("de", "Deutsch"),
    ("fr", "Français"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("pt", "Português"),
    ("nl", "Nederlands"),
    ("pl", "Polski"),
    ("sv", "Svenska"),
    ("ru", "Русский"),
    ("ja", "日本語"),
    ("zh-CN", "中文"),
    ("ko", "한국어"),
    ("ar", "العربية"),
    ("hi", "हिन्दी"),
]
