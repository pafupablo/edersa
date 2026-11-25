import unittest

import pandas as pd

from model import format_tenure, user_date, user_tenure_snapshot


class UserTenureTests(unittest.TestCase):
    def test_parses_source_dates_as_month_day_year(self):
        self.assertEqual(user_date("2/24/2003"), pd.Timestamp("2003-02-24"))
        self.assertEqual(user_date("12/31/2025"), pd.Timestamp("2025-12-31"))
        self.assertTrue(pd.isna(user_date("31/12/2025")))

    def test_classifies_tenure_at_close_of_latest_bimonthly_period(self):
        users = pd.DataFrame(
            {
                "usuario_id": ["reciente", "previo", "anual", "antiguo", "posterior", "sin_fecha"],
                "fecha_alta": pd.to_datetime(["2025-12-15", "2025-09-15", "2025-02-01", "2020-01-01", "2026-02-01", None]),
            }
        )

        result = user_tenure_snapshot(users, pd.Timestamp("2025-12-01")).set_index("usuario_id")

        self.assertEqual(result.loc["reciente", "antiguedad_grupo"], "Alta en último bimestre")
        self.assertTrue(bool(result.loc["reciente", "alta_en_ultimo_bimestre"]))
        self.assertEqual(result.loc["previo", "antiguedad_grupo"], "Alta previa · hasta 6 meses")
        self.assertEqual(result.loc["anual", "antiguedad_grupo"], "7–12 meses")
        self.assertEqual(result.loc["antiguo", "antiguedad_grupo"], "Más de 2 años")
        self.assertEqual(result.loc["posterior", "antiguedad_grupo"], "Alta posterior al período")
        self.assertTrue(pd.isna(result.loc["posterior", "antiguedad_meses"]))
        self.assertEqual(result.loc["sin_fecha", "antiguedad_grupo"], "Sin fecha de alta")

    def test_formats_complete_months_in_plain_language(self):
        self.assertEqual(format_tenure(0), "0 meses")
        self.assertEqual(format_tenure(13), "1 año y 1 mes")
        self.assertEqual(format_tenure(24), "2 años")
        self.assertEqual(format_tenure(float("nan")), "Sin información")


if __name__ == "__main__":
    unittest.main()
