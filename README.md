# Google to Radicale Sync

Synchronisation **bidirectionnelle** entre Google Calendar et un serveur [Radicale](https://radicale.org/) (CalDAV).

Tout changement d'un côté (création, mise à jour, suppression) est répercuté de l'autre : un événement ajouté dans Google apparaît dans Radicale, un événement modifié dans Radicale est poussé vers Google.

## Fonctionnalités

- **Bidirectionnel** avec anti-boucle (nos propres écritures ne rebondissent pas)
- **Sync incrémentale des deux côtés** : Google `syncToken` + CalDAV `sync-collection` (RFC 6578)
- **Conflits** : le dernier modifié gagne (`updated` Google vs `LAST-MODIFIED` CalDAV)
- **Suppressions propagées** dans les deux sens ; une modification bat une suppression
- **Plusieurs calendriers** avec mapping 1↔1 configurable
- **Création automatique** des calendriers Radicale manquants
- **Polling** périodique (intervalle configurable)
- **Déploiement Docker** pensé pour Synology Container Manager

### Limitation connue

Les **exceptions d'occurrences** de récurrence (une seule occurrence déplacée/modifiée) ne sont pas converties : elles sont comptées « ignoré » dans les logs. Les récurrences simples (RRULE/EXDATE) passent dans les deux sens.

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

Édite `data/config.yaml` avec tes infos Radicale et tes calendriers Google :

```yaml
poll_interval: 300

radicale:
  url: "http://<IP_DU_NAS>:5232/syncuser/"
  username: "syncuser"
  password: "ton_mot_de_passe"

calendars:
  - google_calendar_id: "primary"
    radicale_calendar: "mon-calendrier"

  - google_calendar_id: "xxxx@group.calendar.google.com"
    radicale_calendar: "autre-calendrier"
```

Les calendriers Radicale sont créés automatiquement s'ils n'existent pas.

### 4. Lancer

**Docker Compose :**
```bash
docker-compose up -d
```

**Synology Container Manager :**
1. Copie le projet sur le NAS (ex: `/volume1/docker/google-to-radicale/`)
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
│   ├── google/              # auth, lecture/écriture événements, conversion
│   ├── radicale/            # client CalDAV, changements RFC 6578, CRUD
│   └── sync/                # moteur de réconciliation bidirectionnel
├── tests/                   # tests de la logique de réconciliation
└── data/                    # volume Docker (config, tokens, state)
```

## Conseils Radicale

- **Utilisateur dédié** : crée un user Radicale spécifique à la sync si ton serveur est multi-utilisateurs
- **HTTP local** : si Radicale et la sync tournent sur le même NAS, HTTP en réseau local suffit ; passe par HTTPS (reverse proxy) dès que le trafic sort du NAS
- **Certificat auto-signé** : mets `verify_ssl: false` uniquement dans ce cas

## Guide détaillé

Voir [SETUP.md](SETUP.md) pour le guide pas à pas.

## Licence

MIT
