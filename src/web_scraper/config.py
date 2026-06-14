# -*- coding: utf-8 -*-
"""
web_scraper/config.py 鈥?鍏ㄥ眬閰嶇疆 v3.0

鍥涚骇绠＄嚎 + 涓夊ぇ CloakBrowser 娴忚鍣ㄦ睜 + 涓夌粍浠ｇ悊姹?绠＄嚎閫夋嫨鐢辩敤鎴锋樉寮忔帶鍒讹紝涓嶈嚜鍔ㄩ檷绾с€?"""

import os
import sys
import logging
from pathlib import Path

WORKSPACE_ROOT = Path(
    os.environ.get(
        "WEB_SCRAPER_WORKSPACE_ROOT",
        str(Path(__file__).resolve().parents[3]),
    )
)

# ============================================================
# 鏃ュ織
# ============================================================

LOG_FORMAT = "[%(asctime)s] %(levelname)s [%(name)s] %(message)s"
LOG_LEVEL = getattr(logging, os.environ.get("WEB_SCRAPER_LOG_LEVEL", "INFO"))

logger = logging.getLogger("web_scraper")
logger.setLevel(LOG_LEVEL)

if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt="%H:%M:%S"))
    logger.addHandler(handler)

# ============================================================
# BPC 鎵╁睍 (Bypass Paywalls Clean)
# ============================================================

BPC_EXTENSION_PATH = Path(
    os.environ.get(
        "BPC_EXTENSION_PATH",
        str(WORKSPACE_ROOT / "bypass_paywalls_chrome"),
    )
)

BPC_UPDATE_URL = os.environ.get(
    "BPC_UPDATE_URL",
    "https://gitflic.ru/project/magnolia1234/bpc_uploads",
)

BPC_CHROME_ZIP_URL = os.environ.get(
    "BPC_CHROME_ZIP_URL",
    "https://gitflic.ru/project/magnolia1234/bpc_uploads/blob/raw?file=bypass-paywalls-chrome-clean-master.zip",
)
BPC_FIREFOX_EXTENSION_PATH = Path(
    os.environ.get(
        "BPC_FIREFOX_EXTENSION_PATH",
        str(WORKSPACE_ROOT / "bypass_paywalls_firefox"),
    )
)
BPC_FIREFOX_ZIP_URL = os.environ.get(
    "BPC_FIREFOX_ZIP_URL",
    "https://gitflic.ru/project/magnolia1234/bpc_uploads/blob/raw?file=bypass-paywalls-firefox-clean-master.zip",
)
BPC_UPDATE_INTERVAL_SEC = int(os.environ.get("BPC_UPDATE_INTERVAL_SEC", "86400"))
BPC_SITES_JS = BPC_EXTENSION_PATH / "sites.js"

# ============================================================
# CloakBrowser 浜岃繘鍒惰矾寰?# ============================================================

CLOAKBROWSER_BINARY = os.environ.get("CLOAKBROWSER_BINARY", None)

# ============================================================
# 娴忚鍣ㄩ€氱敤閰嶇疆
# ============================================================

HEADLESS_DEFAULT = os.environ.get("WEB_SCRAPER_HEADLESS") in ("1", "true", "yes")

VIEWPORT = {
    "width": int(os.environ.get("WEB_SCRAPER_VP_WIDTH", "1280")),
    "height": int(os.environ.get("WEB_SCRAPER_VP_HEIGHT", "900")),
}

USER_AGENT = os.environ.get(
    "WEB_SCRAPER_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
)

PAGE_GOTO_TIMEOUT = int(os.environ.get("WEB_SCRAPER_GOTO_TIMEOUT", "60000"))
PAGE_WAIT_RENDER_MS = int(os.environ.get("WEB_SCRAPER_WAIT_RENDER", "5000"))

# ============================================================
# 姹?A 閰嶇疆锛堢绾?2锛氬熀纭€娓叉煋锛?# ============================================================

POOL_A_SIZE = int(os.environ.get("POOL_A_SIZE", "2"))
POOL_A_MAX_PAGES = int(os.environ.get("POOL_A_MAX_PAGES", "20"))
POOL_A_IDLE_TIMEOUT_SEC = int(os.environ.get("POOL_A_IDLE_SEC", "120"))
POOL_A_PRELOAD = os.environ.get("POOL_A_PRELOAD", "1") in ("1", "true", "yes")

# ============================================================
# 姹?B 閰嶇疆锛堢绾?3锛氶珮闃叉姢涓诲姏锛?# ============================================================

POOL_B_SIZE = int(os.environ.get("POOL_B_SIZE", "2"))
POOL_B_MAX_PAGES = int(os.environ.get("POOL_B_MAX_PAGES", "50"))
POOL_B_IDLE_TIMEOUT_SEC = int(os.environ.get("POOL_B_IDLE_SEC", "600"))
POOL_B_PRELOAD = os.environ.get("POOL_B_PRELOAD", "1") in ("1", "true", "yes")
POOL_B_REBUILD_DAYS = int(os.environ.get("POOL_B_REBUILD_DAYS", "14"))

# Profile 鎸佷箙鍖栨牴鐩綍
POOL_B_PROFILE_ROOT = Path(
    os.environ.get(
        "POOL_B_PROFILE_ROOT",
        str(Path(os.environ.get("WEB_SCRAPER_PROFILE_ROOT", "./browser_profile/pool_b"))),
    )
)

# Cookie 姣忔棩澶囦唤鐩綍
POOL_B_COOKIE_BACKUP_DIR = Path(
    os.environ.get(
        "POOL_B_COOKIE_BACKUP_DIR",
        str(Path(os.environ.get("WEB_SCRAPER_COOKIE_BACKUP", "./browser_profile/pool_b_cookie_backups"))),
    )
)

# ============================================================
# 姹?C 閰嶇疆锛堢绾?4锛氫粯璐瑰涓撻」锛?# ============================================================

POOL_C_SIZE = int(os.environ.get("POOL_C_SIZE", "1"))
POOL_C_MAX_PAGES = int(os.environ.get("POOL_C_MAX_PAGES", "1"))  # 鍗曟鍗虫瘉
POOL_C_IDLE_TIMEOUT_SEC = int(os.environ.get("POOL_C_IDLE_SEC", "60"))
POOL_C_PRELOAD = os.environ.get("POOL_C_PRELOAD", "0") in ("1", "true", "yes")

# ============================================================
# 浠ｇ悊閰嶇疆锛堜笁缁勭嫭绔嬶級
# ============================================================

# 缁?1锛堢绾?1锛夛細鏁版嵁涓績浠ｇ悊
PROXY_GROUP_1 = [
    p.strip() for p in os.environ.get("PROXY_GROUP_1", "").split(",") if p.strip()
]

# 缁?2锛堟睜 A / 绠＄嚎 2锛夛細鐭晥浣忓畢浠ｇ悊
PROXY_GROUP_2 = [
    p.strip() for p in os.environ.get("PROXY_GROUP_2", "").split(",") if p.strip()
]

# 缁?3a锛堟睜 B / 绠＄嚎 3锛夛細闈欐€佺嫭浜綇瀹?IP锛圛P:绔彛 鏍煎紡锛屼笌涓婁笅鏂囩粦瀹氾級
PROXY_GROUP_3A = [
    p.strip() for p in os.environ.get("PROXY_GROUP_3A", "").split(",") if p.strip()
]

# 缁?3b锛堟睜 C / 绠＄嚎 4锛夛細浠樿垂澧欎笓鐢ㄧ嫭浜綇瀹?IP
PROXY_GROUP_3B = [
    p.strip() for p in os.environ.get("PROXY_GROUP_3B", "").split(",") if p.strip()
]

# 鍚戝悗鍏煎锛氬崟涓€ PROXY 鐜鍙橀噺鏄犲皠鍒版墍鏈夌粍
_SINGLE_PROXY = os.environ.get("WEB_SCRAPER_PROXY", "")
if _SINGLE_PROXY and not any([PROXY_GROUP_1, PROXY_GROUP_2, PROXY_GROUP_3A, PROXY_GROUP_3B]):
    PROXY_GROUP_1 = [_SINGLE_PROXY]
    PROXY_GROUP_2 = [_SINGLE_PROXY]
    PROXY_GROUP_3A = [_SINGLE_PROXY]
    PROXY_GROUP_3B = [_SINGLE_PROXY]

PROXY = _SINGLE_PROXY or None  # 鍚戝悗鍏煎

# ============================================================
# 浠ｇ悊鍋ュ悍妫€鏌?# ============================================================

PROXY_HEALTH_CHECK_INTERVAL_SEC = int(os.environ.get("PROXY_HEALTH_INTERVAL", "300"))
PROXY_IP_CHECK_URL = os.environ.get("PROXY_IP_CHECK_URL", "https://api.ipify.org?format=json")
PROXY_BLACKLIST_TTL_SEC = int(os.environ.get("PROXY_BLACKLIST_TTL", "3600"))

# ============================================================
# 鍐呭鎻愬彇绛栫暐
# ============================================================

class ExtractStrategy:
    """Content extraction strategies."""

    TRAFILATURA = "trafilatura"


DEFAULT_EXTRACT_STRATEGY = os.environ.get("WEB_SCRAPER_EXTRACT_STRATEGY", ExtractStrategy.TRAFILATURA)
MIN_CONTENT_LENGTH = int(os.environ.get("WEB_SCRAPER_MIN_CONTENT", "200"))
USE_TRAFILATURA = os.environ.get("WEB_SCRAPER_USE_TRAFILATURA", "1") in ("1", "true", "yes")
# ============================================================
# 绠＄嚎澶辫触鍒ゅ畾淇″彿
# ============================================================

PIPELINE_FAILURE_SIGNALS = [
    "403", "captcha", "challenge", "verify", "blocked",
    "access denied", "forbidden", "cf-chl", "dd-",
    "just a moment", "checking your browser",
    "attention required", "ray blocked",
]

# ============================================================
# 浠樿垂澧欐娴嬩俊鍙?# ============================================================

PAYWALL_DETECT_SIGNALS = [
    "subscribe", "paywall", "subscription", "member only",
    "premium content", "already a subscriber", "log in to continue",
    "create an account", "start your free trial",
    "piano.io", "tinypass.com", "evolok", "poool",
]

# ============================================================
# paywall 鎷︽埅瑙勫垯锛堝弻淇濋櫓锛?# ============================================================

PAYWALL_BLOCKLIST = [
    "/api/paywall", "/meter", "/api/subscription",
    "piano.io", "tinypass.com", "evolok.net", "pelcro.com",
    "newsmemory.com", "poool.fr", "sophi.io", "zephr.com",
    "qiota.com", "steadyhq.com", "fewcents.co", "memberstack.com",
    "onecount.net", "wallkit.net", "matheranalytics.com",
    "axate.io", "blueconic.net", "cxense.com", "omeda.com",
    "pico.tools", "flip-pay.com", "hadrianpaywall.com",
]

# ============================================================
# 鍋ュ悍妫€鏌?& 璧勬簮娓呯悊
# ============================================================

HEALTH_CHECK_INTERVAL_SEC = int(os.environ.get("WEB_SCRAPER_HEALTH_SEC", "60"))
PRELOAD_BROWSERS = os.environ.get("WEB_SCRAPER_PRELOAD", "0") in ("1", "true", "yes")
KEEP_ALIVE = os.environ.get("WEB_SCRAPER_KEEP_ALIVE", "0") in ("1", "true", "yes")

# ============================================================
# 鍚戝悗鍏煎鍒悕
# ============================================================

BROWSER_POOL_SIZE = POOL_A_SIZE + POOL_B_SIZE + POOL_C_SIZE
BROWSER_ENGINE = "cloakbrowser"
CLOAKBROWSER_HUMANIZE = False  # 鐢卞悇姹犵嫭绔嬫帶鍒?CLOAKBROWSER_HUMAN_PRESET = "default"
CLOAKBROWSER_STEALTH = False  # 鍏ㄥ眬绂佺敤锛岀敱 CloakBrowser 鍐呮牳鎵挎媴

logger.info(
    "Config loaded: pool_a=%d pool_b=%d pool_c=%d "
    "proxy_g1=%d g2=%d g3a=%d g3b=%d headless=%s strategy=%s",
    POOL_A_SIZE, POOL_B_SIZE, POOL_C_SIZE,
    len(PROXY_GROUP_1), len(PROXY_GROUP_2),
    len(PROXY_GROUP_3A), len(PROXY_GROUP_3B),
    HEADLESS_DEFAULT, DEFAULT_EXTRACT_STRATEGY,
)
