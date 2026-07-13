# Guide de Setup — Google to Radicale Sync

## Étape 1 : Configurer Google Cloud (5 min)

1. Va sur **https://console.cloud.google.com/**
2. Clique sur le sélecteur de projet en haut → **Nouveau projet**
   - Nom : `google-calendar-sync` (ou ce que tu veux)
   - Clique **Créer**
3. Sélectionne le projet créé
4. Va dans **API et services** → **Bibliothèque**
   - Cherche **Google Calendar API**
   - Clique dessus → **Activer**
5. Va dans **API et services** → **Écran de consentement OAuth**
   - Type : **Externe**
   - Remplis le nom de l'app (ex: "Calendar Sync")
   - Email de contact : ton email
   - Clique **Enregistrer et continuer** sur chaque page
6. Va dans **API et services** → **Identifiants**
   - Clique **+ Créer des identifiants** → **ID client OAuth 2.0**
   - Type d'application : **Application de bureau**
   - Nom : `calendar-sync`
   - Clique **Créer**
   - **Télécharge le JSON** (bouton de téléchargement)
   - Renomme le fichier en `credentials.json`
   - Place-le dans le dossier `data/`

> **Note** : L'app sera en mode "test". Va dans l'écran de consentement OAuth →
> **Utilisateurs test** → ajoute ton adresse Gmail. Sinon l'auth échouera.

## Étape 2 : Générer le token d'authentification

Sur ta machine locale (pas sur le Synology) :

```bash
# Installe les dépendances
pip install google-api-python-client google-auth-oauthlib

# Crée le dossier data si nécessaire
mkdir -p data

# Lance l'authentification
python auth.py
```

Un navigateur s'ouvre → connecte-toi avec ton compte Google → autorise l'accès.
Le fichier `data/token.json` est créé.

> **Sync bidirectionnelle** : le scope demandé est la lecture/écriture du
> calendrier. Si tu avais un `token.json` généré par une ancienne version
> (lecture seule), supprime-le et relance `python auth.py` — sinon les
> écritures vers Google échoueront en 403.

## Étape 3 : Radicale

Il te faut un serveur Radicale accessible depuis le container (par exemple un
container Radicale sur le même NAS).

1. Vérifie que Radicale répond : ouvre `http://<IP_DU_NAS>:5232/` dans un
   navigateur → l'interface web de Radicale s'affiche
2. Connecte-toi avec ton utilisateur Radicale (défini dans le `htpasswd` de
   Radicale, section `[auth]` de sa config)
3. L'URL CalDAV à utiliser est :
   ```
   http://<IP_DU_NAS>:5232/<username>/
   ```

Pas besoin de créer les calendriers à la main : le script les crée
automatiquement via CalDAV s'ils n'existent pas, et ils apparaissent dans
l'interface web de Radicale.

## Étape 4 : Configurer le sync

```bash
cp config.yaml.example data/config.yaml
```

Édite `data/config.yaml` :

```yaml
poll_interval: 300  # 5 minutes

radicale:
  url: "http://<IP_DU_NAS>:5232/ton_user/"  # ← URL Radicale + username
  username: "ton_user"                       # ← ton user Radicale
  password: "ton_password"                   # ← ton mot de passe Radicale

calendars:
  - google_calendar_id: "primary"
    radicale_calendar: "google-principal"
```

Plutôt que de mettre le mot de passe dans le fichier, tu peux l'exporter
avant de lancer le container — docker-compose le transmet :

```bash
export RADICALE_PASSWORD='ton_password'
docker-compose up -d
```

### Trouver l'ID d'un calendrier Google

1. Va sur **https://calendar.google.com**
2. À gauche, survole le calendrier → ⋮ → **Paramètres et partage**
3. Descends jusqu'à **Intégrer l'agenda**
4. Copie l'**ID de l'agenda** (ressemble à `xxxx@group.calendar.google.com`)
5. Pour le calendrier principal, utilise simplement `primary`

## Étape 5 : Lancer sur le Synology

### Option A : Via docker-compose (SSH)

Copie tout le projet sur ton Synology, puis :

```bash
cd /chemin/vers/googletocalendar
docker-compose up -d
```

### Option B : Via Container Manager (interface web)

1. Copie le dossier du projet sur le Synology (via File Station ou SMB)
2. Ouvre **Container Manager**
3. Va dans **Projet** → **Créer**
4. Sélectionne le dossier contenant `docker-compose.yml`
5. Lance le projet

### Vérifier les logs

```bash
docker logs -f google-to-radicale-sync
```

Ou via Container Manager → clique sur le container → **Journal**

## Dépannage

### "Token expiré" / erreur 401 côté Google
Relance `python auth.py` sur ta machine locale et recopie `data/token.json` sur le Synology.

### Erreur 403 quand une modif Radicale part vers Google
Ton `token.json` date d'une version lecture seule. Supprime-le, relance
`python auth.py` (le scope inclut maintenant l'écriture) et recopie-le.

### Des événements sont comptés « ignoré » dans les logs
Ce sont des exceptions d'occurrences de récurrence (une occurrence isolée
modifiée), non gérées. La série récurrente elle-même se synchronise.

### Erreur 401 côté Radicale
Vérifie le couple username/password dans le `htpasswd` de Radicale, et que
l'URL contient bien le username (`http://.../<username>/`).

### "Sync token invalide"
Normal après une longue période sans sync. L'app fait automatiquement un resync complet.

### Changement de serveur ou d'URL Radicale
Rien à faire : l'état de sync (`data/sync_state.json`) mémorise l'URL cible.
Si elle change, les syncTokens sont invalidés et un resync complet repeuple
automatiquement la nouvelle cible.

### Le container ne joint pas Radicale
Si Radicale tourne aussi en container sur le même NAS, utilise l'IP du NAS
(pas `localhost`, qui pointe vers le container de sync lui-même), ou mets les
deux containers sur le même réseau Docker.

### Erreur SSL / certificat
Mets `verify_ssl: false` dans config.yaml uniquement si tu passes par HTTPS
avec un certificat auto-signé.
