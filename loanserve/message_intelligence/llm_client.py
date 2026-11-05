from pathlib import Path
import hashlib
import json
import os
import re
from datetime import datetime, timezone

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


def log_gemini_request(model_name):
    """Records that a real Gemini request is about to be sent without sensitive data."""
    log_path = Path(os.environ.get("LOANSERVE_LLM_LOG_PATH", "output/logs/llm.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{timestamp} Gemini request sent model={model_name}\n")


def generate_json(prompt, required_keys, llm=None, model_name=None, cache_path=LLM_CACHE_PATH):
    """Generate and validate JSON using an injected mock or the configured Gemini model.

    ``llm`` may be a callable accepting a prompt or an object exposing ``generate_content``.
    This keeps production on Gemini while making assistant flows deterministic in tests.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise LanguageModelError("LLM prompt cannot be blank.")
    if not required_keys:
        raise LanguageModelError("At least one required response key must be supplied.")

    if llm is not None:
        raw_reply = llm(prompt) if callable(llm) else llm.generate_content(prompt).text
        return read_answer(raw_reply, required_keys)

    api_key, configured_model = load_settings()
    selected_model = model_name or configured_model
    key = cache_key(selected_model, prompt)
    cache = load_cache(cache_path)
    if key in cache:
        return read_answer(cache[key], required_keys)

    try:
        from google import genai
    except ImportError as err:
        raise LanguageModelError("google-genai is required for Gemini calls.") from err

    try:
        client = genai.Client(api_key=api_key)
        log_gemini_request(selected_model)
        response = client.models.generate_content(
            model=selected_model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        raw_reply = response.text
    except Exception as err:
        raise LanguageModelError(f"Gemini request failed: {err}") from err

    result = read_answer(raw_reply, required_keys)
    cache[key] = raw_reply
    save_cache(cache, cache_path)
    return result


if __name__ == "__main__":
    prompt = PROMPT_TEMPLATE.format(summary="my emi bounced this month")
    print("Prompt template check passed:")
    print(prompt[:100] + "...")
