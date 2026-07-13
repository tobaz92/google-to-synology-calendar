"""Gestion de l'état de synchronisation — schéma v2 bidirectionnel.

Schéma v2 persisté dans ``sync_state.json`` :

    {
      "_version": 2,
      "_target_url": "http://...",
      "mappings": {
        "<google_calendar_id>": {
          "google_sync_token": null,   # syncToken Google (sync incrémentale)
          "caldav_sync_token": null,   # sync-token CalDAV (RFC 6578)
          "events": {
            "<caldav_uid>": {
              "google_id": "abc123",
              "google_updated": "2026-07-13T10:00:00.000Z",
              "caldav_fingerprint": "sha256hex",
              "href": "/tomi/uuid/xyz.ics"
            }
          }
        }
      }
    }

Sémantique de la table ``events`` (anti-boucle + résolution de conflits) :
- Indexée par UID iCal, stable des deux côtés : un événement d'origine
  Google a un uid = ``google_id + "@google2radicale"``, un événement
  d'origine Radicale garde son UID natif.
- ``google_updated`` : timestamp ``updated`` retourné par l'API Google lors
  de notre dernière écriture, ou dernière valeur vue. Détecte l'écho de nos
  propres écritures côté Google.
- ``caldav_fingerprint`` : empreinte sémantique (sha256 des champs
  synchronisés) du payload iCal que NOUS avons écrit en dernier sur Radicale.
  Détecte l'écho de nos propres écritures côté CalDAV, indépendamment du
  reformatage serveur (LF, DTSTAMP ajouté, ordre des propriétés).
- ``href`` : chemin de la ressource CalDAV. Mappe les suppressions, car le
  REPORT sync-collection renvoie des href, pas des UID.
"""

import json
import logging
import os

from .paths import STATE_PATH

log = logging.getLogger("google2radicale")

STATE_VERSION = 2


def load_state() -> dict:
    """Charge l'état de sync et le migre vers le schéma v2."""
    if not STATE_PATH.exists():
        return _migrate({})

    try:
        with open(STATE_PATH) as f:
            raw = json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        log.warning("sync_state.json corrompu (%s), reset de l'état", e)
        return _migrate({})

    return _migrate(raw)


def _migrate(raw: dict) -> dict:
    """Migre un état brut vers le schéma v2, ou renvoie un squelette vierge.

    L'état v1 (dict plat de syncTokens) n'a pas de table de correspondance :
    la reconstruire est impossible sans resync complet. On repart donc d'un
    squelette vierge ; le matching par UID côté moteur évite les doublons.
    """
    if raw.get("_version") == STATE_VERSION:
        return raw

    skeleton = {"_version": STATE_VERSION, "_target_url": raw.get("_target_url"), "mappings": {}}

    v1_tokens = [k for k in raw if not k.startswith("_")]
    if v1_tokens:
        log.warning(
            "État v1 détecté — syncTokens abandonnés, resync complet forcé "
            "(%d calendrier(s) concerné(s))",
            len(v1_tokens),
        )

    return skeleton


def reset_if_target_changed(state: dict, target_url: str) -> dict:
    """Purge les mappings si la cible CalDAV a changé.

    Sans purge, les tokens de l'ancienne cible feraient croire que tout est
    déjà synchronisé et la nouvelle cible resterait vide. L'état retourné est
    toujours un v2 valide.
    """
    if state.get("_target_url") == target_url:
        return state

    if state.get("mappings"):
        log.warning("Cible CalDAV changée — resync complet forcé")

    state["_target_url"] = target_url
    state["mappings"] = {}
    return state


def get_mapping_state(state: dict, gcal_id: str) -> dict:
    """Retourne le sous-état d'un mapping, créé vierge à la demande.

    Référence vive dans ``state`` : les mutations sont visibles par save_state.
    """
    mappings = state["mappings"]
    if gcal_id not in mappings:
        mappings[gcal_id] = {"google_sync_token": None, "caldav_sync_token": None, "events": {}}
    return mappings[gcal_id]


def save_state(state: dict) -> None:
    """Sauvegarde l'état de sync de manière atomique (write + rename)."""
    tmp_path = STATE_PATH.with_suffix(".tmp")
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(state, f, indent=2)
    tmp_path.rename(STATE_PATH)
