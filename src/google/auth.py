"""Authentification Google Calendar API."""

import logging
import os

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from ..core.constants import SCOPES
from ..core.paths import TOKEN_PATH

log = logging.getLogger("google2synology")


def get_google_service():
    """Retourne un service Google Calendar API authentifié."""
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"{TOKEN_PATH} introuvable. Lance d'abord : python auth.py"
        )

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as e:
            raise RuntimeError(
                f"Impossible de rafraîchir le token Google : {e}. "
                "Relance python auth.py pour régénérer le token."
            ) from e
        fd = os.open(str(TOKEN_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(creds.to_json())
    elif creds.expired:
        raise RuntimeError(
            "Token Google expiré et pas de refresh_token disponible. "
            "Relance python auth.py pour régénérer le token."
        )

    return build("calendar", "v3", credentials=creds)
