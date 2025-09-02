# app_frantoio/util/config.py
from __future__ import annotations
import json, os, shutil
from pathlib import Path
from typing import Any, Dict
import platform

APP_NAME = "App_Frantoio"

def appdata_dir() -> Path:
    """Cartella di configurazione per utente (per-OS)."""
    if os.name == "nt":  # Windows
        base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / APP_NAME
    elif platform.system() == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / APP_NAME
    else:  # Linux e altri Unix-like
        return Path.home() / ".config" / APP_NAME

DEFAULT_CONFIG: Dict[str, Any] = {
    "api_key": "",
    "database_url": "",
    "collection": "molitura",
    "archive_db": "frantoio_archive.db",  # rimane relativo/libero, lo decidi tu
    "hybrid_days": 7,
    "retention_days": 7,
    "euro_per_kg": 0.30,
    "poll_ms": 3000,
    "mirror_interval_minutes": 5
}

def _migrate_legacy_file(target: Path):
    """Se esiste ./config.json nella CWD e non esiste il target, lo migra."""
    legacy = Path("config.json")
    if legacy.exists() and not target.exists():
        try:
            shutil.move(str(legacy), str(target))
        except Exception:
            try:
                shutil.copyfile(str(legacy), str(target))
            except Exception:
                pass

def load_config() -> Dict[str, Any]:
    """Carica config dalla cartella di sistema. Se manca, crea config di default."""
    appdir = appdata_dir()
    appdir.mkdir(parents=True, exist_ok=True)
    cfg_path = appdir / "config.json"
    _migrate_legacy_file(cfg_path)

    if not cfg_path.exists():
        cfg = DEFAULT_CONFIG.copy()
        cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return cfg

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("config non è un oggetto JSON")
        cfg = DEFAULT_CONFIG.copy()
        cfg.update(data)
        return cfg
    except Exception:
        # backup e rigenera
        try:
            shutil.copyfile(cfg_path, str(cfg_path) + ".bak")
        except Exception:
            pass
        cfg = DEFAULT_CONFIG.copy()
        cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return cfg

def save_config(cfg: Dict[str, Any]) -> None:
    """Salva config nella cartella di sistema."""
    appdir = appdata_dir()
    appdir.mkdir(parents=True, exist_ok=True)
    cfg_path = appdir / "config.json"
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
