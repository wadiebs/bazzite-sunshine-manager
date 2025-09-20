# Minimal placeholder importer for Heroic (Epic/GOG/sideload).
# This scaffolding mirrors the old monolithic script API so we can iterate safely.
import os
from typing import List, Dict, Any
from common.utils import log

def import_heroic(home: str, conf_dir: str, images_dir: str, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    IMPORT_HEROIC = settings.get("IMPORT_HEROIC", True)
    if not IMPORT_HEROIC:
        log("Heroic import disabled."); return []

    # TODO: port full logic from sunshine-import.py.
    # For now, return an empty list to keep the pipeline working.
    log("Heroic importer is scaffolding-only right now. No titles imported.")
    return []
