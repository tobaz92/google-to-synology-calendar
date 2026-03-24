# Google to Synology Calendar Sync

Synchronisation **unidirectionnelle** Google Calendar vers Synology Calendar (CalDAV).

Dès qu'un changement est détecté dans un calendrier Google, il est automatiquement répercuté (création, mise à jour, suppression) dans le calendrier Synology correspondant.

## Fonctionnalités

- **Sync incrémentale** via Google `syncToken` (ne récupère que les changements)
- **Plusieurs calendriers** avec mapping configurable
- **Polling** périodique (intervalle configurable)
- **Déploiement Docker** pensé pour Synology Container Manager
- **Détection intelligente** des calendriers Synology (évite les doublons CalDAV)

## Quickstart

### 1. Google Cloud

- Crée un projet sur [Google Cloud Console](https://console.cloud.google.com/)
- Active l'API **Google Calendar**
- Crée des identifiants OAuth 2.0 (type "Application de bureau")
- Télécharge le JSON → `data/credentials.json`

### 2. Authentification

```bash
pip install google-api-python-client google-auth-oauthlib
python auth.py
```

Un navigateur s'ouvre, connecte-toi avec ton compte Google. Le fichier `data/token.json` est généré.

### 3. Configuration

```bash
cp config.yaml.example data/config.yaml
```

Édite `data/config.yaml` avec tes infos Synology et tes calendriers Google :

```yaml
poll_interval: 300

synology:
  url: "https://<IP_DU_NAS>:5001/caldav/syncuser"
  username: "syncuser"
  password: "ton_mot_de_passe"
  verify_ssl: false

calendars:
  - google_calendar_id: "primary"
    synology_calendar: "mon-calendrier"

  - google_calendar_id: "xxxx@group.calendar.google.com"
    synology_calendar: "autre-calendrier"
```

> **Important** : crée les calendriers **manuellement** dans l'interface Synology Calendar avant de lancer la sync. Les calendriers créés via CalDAV n'apparaissent pas dans l'UI.

### 4. Lancer

**Docker Compose :**
```bash
docker-compose up -d
```

**Synology Container Manager :**
1. Copie le projet sur le NAS (ex: `/volume1/docker/google-to-synology/`)
2. Container Manager → Projet → Créer → sélectionne le dossier
3. Construire et Démarrer

**Sans Docker :**
```bash
pip install -r requirements.txt
DATA_DIR=./data python -m src
```

## Structure

```
├── auth.py                  # script OAuth (une fois, hors container)
├── config.yaml.example      # template de configuration
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── src/
│   ├── main.py              # boucle de sync principale
│   ├── core/                # config, state, logging, constantes
│   ├── google/              # auth + lecture événements Google
│   └── synology/            # client CalDAV, conversion, CRUD
└── data/                    # volume Docker (config, tokens, state)
```

## Conseils Synology

- **Compte dédié** : crée un user Synology séparé (ex: `syncuser`) pour isoler les credentials
- **Partage** : partage les calendriers du compte dédié en lecture seule avec ton compte principal
- **CalDAV** : vérifie que le service CalDAV est activé dans les paramètres de Synology Calendar
- **SSL** : utilise `verify_ssl: false` si ton NAS a un certificat auto-signé

## Guide détaillé

Voir [SETUP.md](SETUP.md) pour le guide pas à pas.

## Licence

MIT
