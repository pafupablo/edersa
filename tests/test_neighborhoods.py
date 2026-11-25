import unittest

import pandas as pd

from neighborhoods import neighborhood_comparison_chart, neighborhood_indicators


def sample_neighborhood_data():
    users = pd.DataFrame(
        [
            {"usuario_id": "critico", "nis": "1", "renabap": "R1", "barrio": "Barrio Uno", "localidad": "Localidad"},
            {"usuario_id": "limite", "nis": "2", "renabap": "R1", "barrio": "Barrio Uno", "localidad": "Localidad"},
            {"usuario_id": "bajo", "nis": "3", "renabap": "R1", "barrio": "Barrio Uno", "localidad": "Localidad"},
            {"usuario_id": "sin_historial", "nis": "4", "renabap": "R1", "barrio": "Barrio Uno", "localidad": "Localidad"},
            {"usuario_id": "sin_dato_reciente", "nis": "5", "renabap": "R1", "barrio": "Barrio Uno", "localidad": "Localidad"},
        ]
    )
    consumption = pd.DataFrame(
        [
            {"usuario_id": "critico", "periodo": pd.Timestamp("2026-01-01"), "consumo": 1200},
            {"usuario_id": "critico", "periodo": pd.Timestamp("2026-03-01"), "consumo": 1400},
            {"usuario_id": "critico", "periodo": pd.Timestamp("2026-05-01"), "consumo": 50},
            {"usuario_id": "limite", "periodo": pd.Timestamp("2026-03-01"), "consumo": 1000},
            {"usuario_id": "limite", "periodo": pd.Timestamp("2026-05-01"), "consumo": 1000},
            {"usuario_id": "bajo", "periodo": pd.Timestamp("2026-03-01"), "consumo": 50},
            {"usuario_id": "bajo", "periodo": pd.Timestamp("2026-05-01"), "consumo": 50},
            {"usuario_id": "sin_dato_reciente", "periodo": pd.Timestamp("2026-03-01"), "consumo": 200},
        ]
    )
    neighborhoods = pd.DataFrame(
        [{"renabap": "R1", "barrio": "Barrio Uno", "localidad": "Localidad", "viviendas_estimadas": 10, "tipo_pase": "No PASE"}]
    )
    return users, consumption, neighborhoods


class NeighborhoodCriticalUsersTests(unittest.TestCase):
    def setUp(self):
        self.users, self.consumption, self.neighborhoods = sample_neighborhood_data()

    def test_uses_historical_median_above_1000_without_double_counting(self):
        table, detail, _ = neighborhood_indicators(self.users, self.consumption, self.neighborhoods)

        critical = detail.set_index("usuario_id").loc["critico"]
        boundary = detail.set_index("usuario_id").loc["limite"]
        self.assertEqual(critical.mediana_consumo_usuario, 1300)
        self.assertTrue(bool(critical.usuario_critico))
        self.assertEqual(boundary.mediana_consumo_usuario, 1000)
        self.assertFalse(bool(boundary.usuario_critico))

        row = table.iloc[0]
        self.assertEqual(row.usuarios_criticos, 1)
        chart_categories = [
            "usuarios_criticos",
            "usuarios_estadistica_grafico",
            "bajo_persistente_grafico",
            "sin_historial_grafico",
            "otros_registrados_grafico",
        ]
        self.assertEqual(row[chart_categories].sum(), row.usuarios_registrados)
        self.assertEqual(row.usuarios_registrados, 5)

    def test_chart_shows_critical_users_in_red(self):
        table, _, _ = neighborhood_indicators(self.users, self.consumption, self.neighborhoods)

        figure = neighborhood_comparison_chart(table)

        critical_trace = next(trace for trace in figure.data if trace.name == "Crítico · mediana >1.000")
        self.assertEqual(critical_trace.marker.color, "#D13C42")
        self.assertEqual(list(critical_trace.text), [1])


if __name__ == "__main__":
    unittest.main()
