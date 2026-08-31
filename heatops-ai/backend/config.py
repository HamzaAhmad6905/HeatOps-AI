import os
from pathlib import Path

from dotenv import load_dotenv


# Project root:
# C:\Users\user\temperature-api-quickstart
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load the real .env from the Quickstart repository root.
load_dotenv(PROJECT_ROOT / ".env")

# Also allow environment variables supplied directly by the OS.
load_dotenv()

FORTYGUARD_BASE_URL = os.getenv(
    "FORTYGUARD_BASE_URL",
    "https://api.fortyguard.com",
)

FORTYGUARD_API_KEY = os.getenv(
    "FORTYGUARD_API_KEY",
    "",
)

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    "",
)

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5.6-luna",
)

POLICY_VERSION = os.getenv(
    "POLICY_VERSION",
    "heatops-v1",
)
