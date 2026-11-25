"""Lectura local para revisión y Google Sheets para la aplicación online."""
from datetime import datetime, timezone
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
        return raw, metadata.get("fetched_at", "Copia de prueba sin fecha")
    raw = {
        key: json.loads((ROOT / "data" / f"{key}.json").read_text(encoding="utf-8"))
        if (ROOT / "data" / f"{key}.json").exists() else empty_optional_source(source)
        for key, source in SOURCES.items()
    }
    metadata_path = ROOT / "data" / "snapshot.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    return raw, metadata.get("fetched_at", "Copia local sin fecha")


def load_sheets(service_account):
    import gspread
    from google.oauth2.service_account import Credentials

    credentials = Credentials.from_service_account_info(dict(service_account), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly", "https://www.googleapis.com/auth/drive.readonly"])
    client = gspread.authorize(credentials)
    raw = {}
    for key, source in SOURCES.items():
        if source.get("kind") == "excel":
            from google.auth.transport.requests import AuthorizedSession
            from interventions import read_workbook
            with AuthorizedSession(credentials) as session:
                response = session.get(f"https://www.googleapis.com/drive/v3/files/{source['id']}", params={"alt": "media"}, timeout=90)
                response.raise_for_status()
                raw[key] = read_workbook(response.content)
            continue
        worksheet = client.open_by_key(source["id"]).worksheet(source["worksheet"])
        # FORMATTED_VALUE preserva oct-24: el serial subyacente no representa el año mostrado.
        values = worksheet.get(source["range"], value_render_option=source.get("value_render_option", "FORMATTED_VALUE"))
        if source.get("columns") and values:
            indexes = [values[0].index(name) for name in source["columns"] if name in values[0]]
            values = [[row[i] if i < len(row) else None for i in indexes] for row in values]
        raw[key] = values
    return raw, datetime.now(timezone.utc).isoformat()
