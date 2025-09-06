from pathlib import Path
import sys

def resource_path(rel: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        # quando freezato, i dati stanno sotto app_frantoio/resources
        base = Path(sys._MEIPASS) / "app_frantoio" / "resources"
    else:
        base = Path(__file__).resolve().parent
    return str((base / rel).resolve())