"""Point d'entrée principal — boucle de synchronisation."""

import logging
import signal
import sys
import threading

from .core import load_config, load_state, save_state, setup_logging, get_logger
from .google import get_google_service, fetch_events_incremental
from .synology import get_caldav_client, get_or_create_calendar, sync_event_to_caldav

# Event pour arrêt coopératif — sort du sleep sans interrompre une écriture
_shutdown = threading.Event()


def sync_once(config: dict, state: dict, log, service=None) -> dict:
    """Effectue un cycle de synchronisation pour tous les calendriers."""
    if service is None:
        service = get_google_service()
    client = get_caldav_client(config)

    for mapping in config["calendars"]:
        gcal_id = mapping["google_calendar_id"]
        syn_cal_name = mapping["synology_calendar"]

        log.info("Sync : %s → %s", gcal_id, syn_cal_name)

        sync_token = state.get(gcal_id)
        events, new_sync_token = fetch_events_incremental(service, gcal_id, sync_token)

        if not events:
            log.info("  Aucun changement")
            if new_sync_token:
                state[gcal_id] = new_sync_token
            continue

        log.info("  %d événement(s) à traiter", len(events))
        caldav_calendar = get_or_create_calendar(client, syn_cal_name)
        stats = _process_events(caldav_calendar, events, log)

        log.info(
            "  Résultat : %d créé(s), %d mis à jour, %d supprimé(s), %d erreur(s)",
            stats["created"], stats["updated"], stats["deleted"], stats["errors"],
        )

        if new_sync_token:
            state[gcal_id] = new_sync_token

    return state


def _process_events(caldav_calendar, events: list, log) -> dict:
    """Traite une liste d'événements et retourne les statistiques."""
    stats = {"created": 0, "updated": 0, "deleted": 0, "errors": 0}

    for event in events:
        try:
            result = sync_event_to_caldav(caldav_calendar, event)
            stats[result] = stats.get(result, 0) + 1
        except Exception as e:
            stats["errors"] += 1
            summary = event.get("summary", event.get("id", "?"))
            log.error("  Erreur sync '%s': %s", summary, e)

    return stats


def main():
    signal.signal(signal.SIGTERM, lambda *_: _shutdown.set())
    signal.signal(signal.SIGINT, lambda *_: _shutdown.set())

    try:
        config = load_config()
    except (FileNotFoundError, ValueError) as e:
        print(f"ERREUR config : {e}", file=sys.stderr)
        sys.exit(1)

    setup_logging(config.get("log_level", "INFO"))
    log = get_logger()

    log.info("=== Google → Synology Calendar Sync ===")

    state = load_state()
    poll_interval = config.get("poll_interval", 300)

    log.info("Polling toutes les %d secondes", poll_interval)
    log.info("Calendriers configurés : %d", len(config["calendars"]))

    service = None

    while not _shutdown.is_set():
        try:
            if service is None:
                service = get_google_service()
            state = sync_once(config, state, log, service=service)
            save_state(state)
        except Exception as e:
            log.error("Erreur durant la sync : %s", e, exc_info=log.isEnabledFor(logging.DEBUG))
            # Reset le service uniquement sur erreur d'auth/réseau
            err_msg = str(e).lower()
            if "credentials" in err_msg or "token" in err_msg or "refused" in err_msg or "timeout" in err_msg:
                log.info("Recréation du service Google au prochain cycle")
                service = None

        log.info("Prochaine sync dans %d secondes...", poll_interval)
        _shutdown.wait(poll_interval)

    log.info("Arrêt demandé, fermeture propre.")
    save_state(state)
