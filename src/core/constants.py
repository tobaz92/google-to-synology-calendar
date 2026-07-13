"""Constantes partagées du projet."""

SCOPES = ["https://www.googleapis.com/auth/calendar"]

GOOGLE_UID_SUFFIX = "@google2radicale"

# Marqueur de correspondance posé sur les événements écrits dans Google
# (extendedProperties.private) — permet de retrouver l'uid CalDAV si
# l'état local de sync est perdu
G2R_UID_PROP = "g2r_uid"

PRODID = "-//Google2Radicale//FR"

# Retry
MAX_RETRIES = 5
RETRY_BASE_DELAY = 2  # secondes
