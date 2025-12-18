import os
import sys
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Ensure PocketOptionAPI repo is importable when running locally
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
PO_API_REPO = os.path.join(ROOT_DIR, "PocketOptionAPI")
if os.path.isdir(PO_API_REPO) and PO_API_REPO not in sys.path:
    sys.path.append(PO_API_REPO)

load_dotenv()

@dataclass
class Settings:
    telegram_token: str
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek/deepseek-chat")
    pocket_option_ssid: Optional[str] = None
    is_demo: bool = True
    log_file: str = os.getenv("LOG_FILE", "bot.log")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    rate_limit_ai_qps: float = float(os.getenv("AI_QPS", "0.33"))  # ~1 call per 3s


def load_settings() -> Settings:
    # Prefer env var; fallback to ssid.txt first non-empty line
    ssid = os.getenv("POCKET_OPTION_SSID")
    if not ssid:
        ssid_file = os.path.join(ROOT_DIR, "ssid.txt")
        if os.path.exists(ssid_file):
            with open(ssid_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        ssid = line
                        break

    token = os.getenv("TELEGRAM_TOKEN", "")
    openrouter_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or ""
    base_url = os.getenv("OPENROUTER_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL") or "https://openrouter.ai/api/v1"

    is_demo_env = os.getenv("PO_IS_DEMO", "true").lower()
    is_demo = is_demo_env in ("1", "true", "yes")

    return Settings(
        telegram_token=token,
        openrouter_api_key=openrouter_key,
        openrouter_base_url=base_url,
        pocket_option_ssid=ssid,
        is_demo=is_demo,
    )