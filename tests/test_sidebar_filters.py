import unittest
from pathlib import Path

import pandas as pd

from model import filter_household_survey_status, pase_filter_label


class HouseholdSurveyFilterTests(unittest.TestCase):
    def setUp(self):
        self.users = pd.DataFrame(
            {
                "usuario_id": ["con-una", "sin", "con-dos", "faltante"],
                "encuestas_vinculadas": [1, 0, 2, None],
            }
        )

    def test_filters_users_with_linked_household_survey(self):
        result = filter_household_survey_status(self.users, "Sí")
        self.assertEqual(result.usuario_id.tolist(), ["con-una", "con-dos"])

    def test_filters_users_without_linked_household_survey(self):
        result = filter_household_survey_status(self.users, "No")
        self.assertEqual(result.usuario_id.tolist(), ["sin", "faltante"])

    def test_all_keeps_the_complete_selection(self):
        result = filter_household_survey_status(self.users, "Todos")
        self.assertEqual(result.usuario_id.tolist(), self.users.usuario_id.tolist())

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(ValueError):
            filter_household_survey_status(self.users, "Tal vez")


class PaseFilterTests(unittest.TestCase):
    def test_pase_options_have_clear_labels(self):
        self.assertEqual(pase_filter_label("BLANDO"), "PASE blando")
        self.assertEqual(pase_filter_label("DURO"), "PASE duro")
        self.assertEqual(pase_filter_label("No es PASE"), "No es PASE")

    def test_sidebar_uses_one_pase_filter_and_no_category_filter(self):
        source = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertIn('multiselect_filter("PASE", "tipo_pase"', source)
        self.assertNotIn('multiselect_filter("PASE del barrio", "pase_barrio")', source)
        self.assertNotIn('multiselect_filter("Tipo PASE del barrio", "tipo_pase")', source)
        self.assertNotIn('multiselect_filter("Categoría · código", "categoria")', source)


if __name__ == "__main__":
    unittest.main()
