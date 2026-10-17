"""Companion settings: a config file written by `setup`, overridden by environment variables.

Precedence, lowest first: config file, GNOMECASTER_* environment variables, command-line
flags. GNOMECASTER_CONFIG names another config file (the tests use it). The file's
"web_search" (or GNOMECASTER_WEB_SEARCH=0/1) turns OpenRouter's web search off or on; it is
on by default through OpenRouter and never offered elsewhere.
"""
from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import sys
import urllib.parse

PRESETS = {
    "openrouter": {"label": "OpenRouter: one key, hundreds of models (recommended)", "name": "OpenRouter",
                   "base_url": "https://openrouter.ai/api/v1", "model": "openai/gpt-6-luna", "key": True,
                   "key_url": "https://openrouter.ai/keys", "key_hint": "create one at https://openrouter.ai/keys"},
    "openai": {"label": "OpenAI", "name": "OpenAI", "base_url": "https://api.openai.com/v1", "model": "gpt-6-luna",
               "key": True, "key_url": "https://platform.openai.com/api-keys",
               "key_hint": "create one at https://platform.openai.com/api-keys"},
    # Ollama listens on 127.0.0.1 only; Windows tries "localhost" as ::1 first, and each refused
    # IPv6 connection there costs about 2 s before IPv4 is tried
    "ollama": {"label": "Ollama: a free local model on this PC (needs a strong graphics card)",
               "name": "Ollama (a model on this PC)", "base_url": "http://127.0.0.1:11434/v1", "model": "llama3.1",
               "key": False, "key_hint": ""},
    "custom": {"label": "Another OpenAI-compatible endpoint", "base_url": "", "model": "", "key": True,
               "key_hint": ""},
}
OLD_OLLAMA_URL = "http://localhost:11434/v1"         # 1.0.0's preset; settings files still hold it

# The models the desktop app offers per provider, best first. The OpenRouter ones scored 20 of
# 20 in tools/eval_models.py (README, "Choosing a model"); the others are the presets' defaults.
MODELS = {
    "openrouter": [
        {"id": "openai/gpt-6-luna", "name": "GPT-6 Luna", "detail": "Quick answers, very low cost.", "recommended": True},
        {"id": "anthropic/claude-haiku-5.5", "name": "Claude Haiku 5.5", "detail": "Quickest answers, low cost."},
        {"id": "google/gemini-3.8-flash", "name": "Gemini 3.8 Flash", "detail": "Quick answers, several times the cost."},
        {"id": "deepseek/deepseek-v4.1-flash", "name": "DeepSeek V4.1 Flash",
         "detail": "Lowest cost; some answers are slow."},
    ],
}


def models_for(provider: str) -> list[dict]:
    if provider in MODELS:
        return MODELS[provider]
    default = PRESETS.get(provider, {}).get("model")
    return [{"id": default, "name": default, "detail": "This provider's default model.", "recommended": True}] if default else []


class ConfigError(Exception):
    pass


ENV = {"base_url": "GNOMECASTER_BASE_URL", "api_key": "GNOMECASTER_API_KEY",
       "model": "GNOMECASTER_MODEL", "wow": "GNOMECASTER_WOW"}
WEB_SEARCH_ENV = "GNOMECASTER_WEB_SEARCH"           # 0 or 1; the settings file key is web_search
SEARCH_HOSTS = ("openrouter.ai",)                   # the web search tool is OpenRouter's


def web_search(base_url: str, setting=None) -> bool:
    """Whether the model may search the web: only through OpenRouter, on unless turned off."""
    host = (urllib.parse.urlsplit(base_url or "").hostname or "").lower()
    return host in SEARCH_HOSTS and _flag(setting) is not False


def _flag(value) -> bool | None:
    """True or False from a settings file or environment value; None when unset or unreadable."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("0", "1", "false", "true", "off", "on"):
        return value.strip().lower() in ("1", "true", "on")
    return None


def config_path() -> pathlib.Path:
    if os.environ.get("GNOMECASTER_CONFIG"):
        return pathlib.Path(os.environ["GNOMECASTER_CONFIG"])
    if sys.platform == "win32":
        base = pathlib.Path(os.environ.get("APPDATA") or pathlib.Path.home() / "AppData" / "Roaming") / "Gnomecaster"
    elif sys.platform == "darwin":
        base = pathlib.Path.home() / "Library" / "Application Support" / "Gnomecaster"
    else:
        base = pathlib.Path(os.environ.get("XDG_CONFIG_HOME") or pathlib.Path.home() / ".config") / "gnomecaster"
    return base / "config.json"


@dataclasses.dataclass
class Settings:
    provider: str = ""
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    wow: str = ""
    extra: dict = dataclasses.field(default_factory=dict)
    search: bool | None = None          # None: the default, on for OpenRouter

    @property
    def has_model(self) -> bool:
        return bool(self.base_url and self.model)

    @property
    def web_search(self) -> bool:
        return web_search(self.base_url, self.search)


def load_file(path: pathlib.Path | None = None) -> dict:
    path = path or config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ConfigError(f"Can't read the settings file {path} ({e}). Run setup again or delete the file.") from None
    if not isinstance(data, dict):
        raise ConfigError(f"The settings file {path} is not a JSON object. Run setup again.")
    if data.get("provider") == "ollama" and data.get("base_url") == OLD_OLLAMA_URL:     # saved by 1.0.0
        data["base_url"] = PRESETS["ollama"]["base_url"]
    return data


def save_file(data: dict, path: pathlib.Path | None = None) -> pathlib.Path:
    """Writes the settings readable by the owner only: the file holds the API key."""
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def resolve(wow: str | None = None) -> Settings:
    data = load_file()
    s = Settings(provider=str(data.get("provider") or ""), base_url=str(data.get("base_url") or ""),
                 model=str(data.get("model") or ""), api_key=str(data.get("api_key") or ""),
                 wow=str(data.get("wow") or ""), extra=data.get("extra") if isinstance(data.get("extra"), dict) else {},
                 search=_flag(data.get("web_search")))
    for field, var in ENV.items():
        if os.environ.get(var):
            setattr(s, field, os.environ[var])
    if _flag(os.environ.get(WEB_SEARCH_ENV)) is not None:
        s.search = _flag(os.environ[WEB_SEARCH_ENV])
    if wow:
        s.wow = wow
    return s
