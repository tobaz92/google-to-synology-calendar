"""Point d'entrée principal — boucle de synchronisation bidirectionnelle."""

import logging
import signal
import sys
import threading

from .core import (
    get_logger, get_mapping_state, load_config, load_state,
    reset_if_target_changed, save_state, setup_logging,
)
from .google import get_google_service
from .radicale import get_caldav_client, get_or_create_calendar, invalidate_calendar
from .sync import CalendarContext, sync_mapping

# Event pour arrêt coopératif — sort du sleep sans interrompre une écriture
_shutdown = threading.Event()


def sync_once(config: dict, state: dict, log, service) -> Exception | None:
    """Cycle de sync pour tous les mappings. Retourne la première erreur, ou None.

    Un mapping en échec ne bloque pas les suivants : erreur journalisée, cache
    d'URL invalidé (peut-être périmé), et l'état des mappings réussis reste
    exploitable. Les tokens du mapping en échec n'ont pas été avancés.
    """
    client = get_caldav_client(config)
    first_error = None

    for mapping in config["calendars"]:
        gcal_id = mapping["google_calendar_id"]
        name = mapping["radicale_calendar"]
        log.info("Sync : %s ↔ %s", gcal_id, name)
        try:
            calendar = get_or_create_calendar(client, name)
            ctx = CalendarContext(calendar=calendar, name=name)
            stats = sync_mapping(service, ctx, gcal_id, get_mapping_state(state, gcal_id))
        except Exception as e:
            invalidate_calendar(name)
            log.error("  Échec du mapping %s : %s", gcal_id, e,
                      exc_info=log.isEnabledFor(logging.DEBUG))
            first_error = first_error or e
            continue
        _log_stats(log, stats)

    return first_error


def _log_stats(log, stats: dict) -> None:
    """Journalise le bilan d'un mapping."""
    log.info(
        "  → Radicale : %d, → Google : %d, suppr. Radicale : %d, "
        "suppr. Google : %d, ignoré(s) : %d, erreur(s) : %d",
        stats["to_caldav"], stats["to_google"], stats["deleted_caldav"],
        stats["deleted_google"], stats["skipped"], stats["errors"],
    )


def _is_auth_or_network_error(error: Exception) -> bool:
    """Heuristique héritée de la phase 1 : recréer le service Google ?"""
    msg = str(error).lower()
    return any(k in msg for k in ("credentials", "token", "refused", "timeout"))


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

    log.info("=== Google ↔ Radicale Sync ===")

    state = reset_if_target_changed(load_state(), config["radicale"]["url"])
    poll_interval = config.get("poll_interval", 300)

    log.info("Polling toutes les %d secondes", poll_interval)
    log.info("Calendriers configurés : %d", len(config["calendars"]))

    service = None

    while not _shutdown.is_set():
        try:
            if service is None:
                service = get_google_service()
            cycle_error = sync_once(config, state, log, service)
            # Persiste aussi la progression des mappings réussis quand un
            # autre mapping a échoué (ses tokens à lui n'ont pas bougé)
            save_state(state)
        except Exception as e:
            cycle_error = e
            log.error("Erreur durant la sync : %s", e, exc_info=log.isEnabledFor(logging.DEBUG))

        if cycle_error is not None and _is_auth_or_network_error(cycle_error):
            log.info("Recréation du service Google au prochain cycle")
            service = None

        log.info("Prochaine sync dans %d secondes...", poll_interval)
        _shutdown.wait(poll_interval)

    log.info("Arrêt demandé, fermeture propre.")
    save_state(state)
