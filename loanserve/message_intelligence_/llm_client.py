from pathlib import Path
import hashlib
import json
import os
import re

from config.constants import LLM_CACHE_PATH, LLM_REQUIRED_KEYS
from loanserve.core.exceptions import LoanServeError


class LanguageModelError(LoanServeError):
    """Raised when language model settings are invalid or an LLM call fails."""


PROMPT_TEMPLATE = (
    "Please analyze and summarize the following customer conversation summary:\n\n"
    "{summary}\n\n"
    "Respond ONLY with a valid JSON object containing exactly these keys:\n"
    '- "summary": An abstractive summary of the customer issue\n'
    '- "sentiment": One of "neutral", "angry", "worried", "happy"\n'
    '- "action": The recommended next action or resolution'
)

REMINDER = (
    "\n\nReminder: Your previous reply was invalid. Respond ONLY with valid JSON "
    'containing the exact keys "summary", "sentiment", and "action".'
)


def load_settings():
    """Loads Gemini API settings from environment or .env file."""
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip()
                if key not in os.environ:
                    os.environ[key] = val

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    model_name = os.environ.get("GEMINI_MODEL", "").strip()

    if not api_key or not model_name:
        raise LanguageModelError("GEMINI_API_KEY and GEMINI_MODEL must be configured.")

    return api_key, model_name


def cache_key(model_name, prompt):
    """Computes unique SHA-256 hash identifying model and exact prompt."""
    return hashlib.sha256(f"{model_name}:{prompt}".encode("utf-8")).hexdigest()


def read_answer(raw_reply, required_keys=LLM_REQUIRED_KEYS):
    """Parses LLM response, stripping markdown formatting, and validates required keys."""
    if not isinstance(raw_reply, str):
        raise ValueError("Raw reply must be a string.")

    text = raw_reply.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object.")

    for k in required_keys:
        if k not in data:
            raise ValueError(f"Missing required key: '{k}'")

    return data


def load_cache(cache_path=LLM_CACHE_PATH):
    """Loads cache file from disk."""
    p = Path(cache_path)
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache_data, cache_path=LLM_CACHE_PATH):
    """Saves cache file to disk."""
    p = Path(cache_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2)


if __name__ == "__main__":
    prompt = PROMPT_TEMPLATE.format(summary="my emi bounced this month")
    print("Prompt template check passed:")
    print(prompt[:100] + "...")
