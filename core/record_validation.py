"""Regole comuni per la modifica sicura dei record di molitura.

Non dipende da PyQt: può essere verificato e usato anche in test/headless.
Le modifiche sono parziali: i campi non cambiati non vengono sovrascritti.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

EDITABLE_FIELDS = frozenset({"name", "weight", "abbuono", "pagamento", "dataOra"})


def _original_value(record: Mapping[str, Any], key: str) -> Any:
    if key == "name":
        return record.get("name", record.get("nome", ""))
    if key == "weight":
        return record.get("weight", record.get("peso", 0.0))
    return record.get(key, 0.0 if key == "abbuono" else "")


def validate_record_changes(original: Mapping[str, Any], proposed: Mapping[str, Any]) -> dict[str, Any]:
    """Restituisce solo i campi realmente cambiati, con tipi normalizzati.

    Solleva ValueError su input non validi. L'ID resta immutabile.
    """
    unknown = set(proposed) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Campi non modificabili: {', '.join(sorted(unknown))}")

    changes: dict[str, Any] = {}
    for key, raw in proposed.items():
        if key == "name":
            value = str(raw or "").strip()
            if not value or len(value) > 120:
                raise ValueError("Il nome deve contenere da 1 a 120 caratteri.")
            old = str(_original_value(original, key) or "").strip()
        elif key in ("weight", "abbuono"):
            try:
                value = float(str(raw).replace(",", "."))
            except (TypeError, ValueError):
                raise ValueError("Peso e abbuono devono essere numeri validi.") from None
            if not isfinite(value):
                raise ValueError("Non sono ammessi valori infiniti o non numerici.")
            if key == "weight" and not (0 < value <= 100_000):
                raise ValueError("Il peso deve essere maggiore di zero e non oltre 100.000 kg.")
            if key == "abbuono" and not (0 <= value <= 1_000_000):
                raise ValueError("L'abbuono deve essere compreso tra 0 e 1.000.000 €.")
            try:
                old = float(_original_value(original, key) or 0)
            except (TypeError, ValueError):
                old = None
        elif key == "pagamento":
            value = str(raw or "").strip()
            if len(value) > 60:
                raise ValueError("Il metodo di pagamento è troppo lungo.")
            old = str(_original_value(original, key) or "").strip()
        elif key == "dataOra":
            try:
                value = int(raw)
            except (TypeError, ValueError, OverflowError):
                raise ValueError("Data e ora non valide.") from None
            # millisecondi Unix, dal 2000 al 2100
            if not (946684800000 <= value <= 4102444800000):
                raise ValueError("La data del record deve essere compresa tra il 2000 e il 2100.")
            try:
                old = int(float(_original_value(original, key)))
            except (TypeError, ValueError):
                old = None
        else:
            continue

        if value != old:
            changes[key] = value

    return changes
