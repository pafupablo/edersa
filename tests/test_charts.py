import unittest

import pandas as pd

from charts import evolution_chart, format_number


class EvolutionChartTests(unittest.TestCase):
    def setUp(self):
        self.summary = pd.DataFrame(
            {
                "periodo": pd.to_datetime(["2026-06-01", "2026-12-01"]),
                "p25": [900.25, 1000.5],
                "p75": [1500.75, 1800.25],
                "mediana": [1200.5, 1400.75],
                "promedio": [1250.25, 1450.5],
                "usuarios": [1234, 5678],
                "variacion_mediana_pct": [float("nan"), 16.6875],
                "cobertura": [74.125, 82.5],
            }
        )

    def test_uses_argentine_number_format(self):
        self.assertEqual(format_number(1234.5), "1.234,50")
        self.assertEqual(format_number(1234, 0), "1.234")
        fig = evolution_chart(self.summary)
        self.assertEqual(fig.layout.separators, ",.")
        median_trace = next(trace for trace in fig.data if trace.name == "Consumo · mediana")
        self.assertIn("%{y:,.2f}", median_trace.hovertemplate)

    def test_shows_user_values_on_the_bar_subplot(self):
        fig = evolution_chart(self.summary)
        bars = next(trace for trace in fig.data if trace.type == "bar")
        self.assertEqual(list(bars.text), ["1.234", "5.678"])
        self.assertEqual(bars.textposition, "outside")

    def test_adds_winter_and_summer_context(self):
        fig = evolution_chart(self.summary)
        annotations = {annotation.text for annotation in fig.layout.annotations}
        colors = {shape.fillcolor for shape in fig.layout.shapes}
        self.assertIn("❄️", annotations)
        self.assertIn("☀️", annotations)
        self.assertIn("#FFFFFF", colors)
        self.assertIn("#FFE16B", colors)


if __name__ == "__main__":
    unittest.main()
