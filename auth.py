#!/usr/bin/env python3
"""
Script d'authentification OAuth Google Calendar.
À lancer UNE FOIS sur ta machine (pas dans le container Docker)
pour générer le fichier token.json.

Usage :
    1. Place credentials.json dans le dossier data/
    2. Lance : python auth.py
    3. Un navigateur s'ouvre, connecte-toi à ton compte Google
    4. Le fichier data/token.json est créé automatiquement
"""

import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]

DATA_DIR = Path(__file__).parent / "data"
CREDENTIALS_PATH = DATA_DIR / "credentials.json"
TOKEN_PATH = DATA_DIR / "token.json"


def main():
    DATA_DIR.mkdir(exist_ok=True)

    if not CREDENTIALS_PATH.exists():
        print(f"ERREUR : {CREDENTIALS_PATH} introuvable.")
        print()
        print("Pour l'obtenir :")
        print("  1. Va sur https://console.cloud.google.com/")
        print("  2. Crée un projet (ou sélectionne-en un)")
        print("  3. Active l'API 'Google Calendar API'")
        print("  4. Va dans 'Identifiants' (Credentials)")
        print("  5. Crée un identifiant OAuth 2.0 (type 'Application de bureau')")
        print("  6. Télécharge le JSON et place-le dans data/credentials.json")
        sys.exit(1)

    creds = None

    # Vérifier si un token existe déjà
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.valid:
        print("Token déjà valide !")
        return

    if creds and creds.expired and creds.refresh_token:
        print("Token expiré, rafraîchissement...")
        creds.refresh(Request())
    else:
        print("Lancement de l'authentification OAuth...")
        print("Un navigateur va s'ouvrir. Connecte-toi avec ton compte Google.")
        print()
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
        creds = flow.run_local_server(port=0)

    fd = os.open(str(TOKEN_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(creds.to_json())

    print(f"Token sauvegardé dans {TOKEN_PATH}")
    print("Tu peux maintenant lancer le container Docker.")


if __name__ == "__main__":
    main()
