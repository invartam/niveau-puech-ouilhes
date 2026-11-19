"""Configuration for Niv'eau Puech des Ouilhes monitor."""
import os

# API endpoint
API_URL = "https://data.niv-eau.fr/hydro/lieu/119/d/{date}/{nb}"
API_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.niv-eau.fr/",
    "Origin": "https://www.niv-eau.fr",
    "Accept": "application/json, text/plain, */*",
    "laetis": "Basic TGFldGlzTjF2ZWF1",
}

# Thresholds (mNGF)
THRESHOLD_HIGH = 498.0   # alert if level goes ABOVE this
THRESHOLD_LOW = 501.0    # alert if level goes BELOW this

# Database
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "levels.db")

# Export directory for GitHub Pages
EXPORT_DIR = os.path.join(os.path.dirname(__file__), "docs", "data")

# Email (from env)
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
_smtp_port = os.environ.get("SMTP_PORT", "587")
SMTP_PORT = int(_smtp_port) if _smtp_port.strip() else 587
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "")

# Alert state file
ALERT_STATE_PATH = os.path.join(os.path.dirname(__file__), "data", "alert_state.json")

# Location info
LOCATION_NAME = "Puech des Ouilhes"
LOCATION_ID = 119
ENSEMBLE_NAME = "Barrage de Saint-Etienne-Cantales"
UNIT = "mNGF"