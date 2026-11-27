import json
from pathlib import Path
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]


class PublishedPrivacyTests(unittest.TestCase):
    def test_derived_links_have_only_non_document_fields(self):
        payload = json.loads((ROOT / "survey_links.json").read_text(encoding="utf-8"))
        rows = payload["rows"]

        self.assertEqual(rows[0], ["survey_uuid", "usuario_id", "vinculo_encuesta"])
        self.assertTrue(all(len(row) == 3 for row in rows))

    def test_published_snapshot_excludes_document_columns_and_tables(self):
        with ZipFile(ROOT / "trial_snapshot.zip") as archive:
            names = set(archive.namelist())
            self.assertNotIn("usuarios_documentos.json", names)
            for name in ("encuestas.json", "personas.json"):
                rows = json.loads(archive.read(name))
                headers = {str(value).casefold() for value in rows[0]}
                self.assertFalse(any("dni" in header or header.startswith("doc") for header in headers))

    def test_published_app_has_no_manual_source_uploads(self):
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("st.file_uploader", app_source)
        self.assertNotIn("Usuario Alta · CSV", app_source)


if __name__ == "__main__":
    unittest.main()
