"""Lantern POC. Loads .env (GEMINI_API_KEY, LANTERN_MODEL) before any submodule reads the environment."""
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")  # real environment variables still win
except ImportError:  # python-dotenv is optional; offline mode needs no key
    pass
