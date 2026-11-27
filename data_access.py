"""Lectura del paquete publicado y sus vínculos derivados sin documentos."""
import json
from zipfile import ZipFile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCES = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))


def local_available():
    required = [key for key, source in SOURCES.items() if not source.get("optional_local")]
    return (ROOT / "trial_snapshot.zip").exists() or all((ROOT / "data" / f"{key}.json").exists() for key in required)


def empty_optional_source(source):
    return [source.get("empty_headers", [])]


def add_derived_links(raw):
    """Adjunta vínculos ya resueltos sin cargar documentos personales."""
    path = ROOT / "survey_links.json"
    if not path.exists():
        raw["survey_links"] = []
        return raw
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("survey_links.json no contiene una tabla válida.")
    raw["survey_links"] = rows
    return raw


def load_local():
    snapshot_zip = ROOT / "trial_snapshot.zip"
    if snapshot_zip.exists():
        with ZipFile(snapshot_zip) as archive:
            names = set(archive.namelist())
            raw = {
                key: json.loads(archive.read(f"{key}.json")) if f"{key}.json" in names else empty_optional_source(source)
                for key, source in SOURCES.items()
            }
            metadata = json.loads(archive.read("snapshot.json"))
        return add_derived_links(raw), metadata.get("fetched_at", "Copia de prueba sin fecha")
    raw = {
        key: json.loads((ROOT / "data" / f"{key}.json").read_text(encoding="utf-8"))
        if (ROOT / "data" / f"{key}.json").exists() else empty_optional_source(source)
        for key, source in SOURCES.items()
    }
    metadata_path = ROOT / "data" / "snapshot.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    return add_derived_links(raw), metadata.get("fetched_at", "Copia local sin fecha")
