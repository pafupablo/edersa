import unittest

import pandas as pd

from surveys import build_surveys, document_id


def survey_rows(items):
    header = ["_uuid", "encuesta_responde", "terreno_tipo", "numero_cliente_edersa", "titular_servicio_dni", "barrio_nombre"]
    return [header] + [[item.get(column, "") for column in header] for item in items]


class SurveyIdentityLinkTests(unittest.TestCase):
    def setUp(self):
        self.users = pd.DataFrame(
            [
                {"usuario_id": "u1", "nis": "100", "renabap": ""},
                {"usuario_id": "u2", "nis": "200", "renabap": ""},
                {"usuario_id": "u3", "nis": "300", "renabap": ""},
            ]
        )
        self.neighborhoods = pd.DataFrame(
            [{"renabap": "R", "barrio": "Barrio", "localidad": "Localidad", "departamento_barrio": "Departamento", "pase_barrio": "No", "tipo_pase": "No es PASE"}]
        )
        self.documents = [
            ["Usua_ID", "DOC", "DOC N°"],
            ["u1", "DNI", "30.123.456"],
            ["u2", "DNI", "31.234.567"],
            ["u1", "DNI", "32.345.678"],
            ["u2", "DNI", "32.345.678"],
            ["u3", "CUIT", "33.456.789"],
        ]

    def test_links_by_nis_or_unique_dni_and_rejects_conflicts(self):
        surveys = survey_rows(
            [
                {"_uuid": "both", "encuesta_responde": "Sí", "terreno_tipo": "Vivienda ocupada", "numero_cliente_edersa": "100", "titular_servicio_dni": "30.123.456"},
                {"_uuid": "person", "encuesta_responde": "Sí", "terreno_tipo": "Vivienda ocupada"},
                {"_uuid": "conflict", "encuesta_responde": "Sí", "terreno_tipo": "Vivienda ocupada", "numero_cliente_edersa": "100", "titular_servicio_dni": "31.234.567"},
                {"_uuid": "ambiguous", "encuesta_responde": "Sí", "terreno_tipo": "Vivienda ocupada", "titular_servicio_dni": "32.345.678"},
                {"_uuid": "wrong-type", "encuesta_responde": "Sí", "terreno_tipo": "Vivienda ocupada", "titular_servicio_dni": "33.456.789"},
            ]
        )
        people = [
            ["_submission__uuid", "encuestado_dni"],
            ["person", "31.234.567"],
        ]

        result = build_surveys(surveys, people, self.users, self.neighborhoods, self.documents)
        records = result.records.set_index("survey_uuid")

        self.assertEqual(records.loc["both", "usuario_id"], "u1")
        self.assertEqual(records.loc["both", "vinculo_encuesta"], "NIS y DNI confirmados")
        self.assertEqual(records.loc["person", "usuario_id"], "u2")
        self.assertEqual(records.loc["person", "vinculo_encuesta"], "DNI confirmado")
        self.assertEqual(records.loc["conflict", "usuario_id"], "")
        self.assertEqual(records.loc["conflict", "vinculo_encuesta"], "NIS y DNI en conflicto")
        self.assertEqual(records.loc["ambiguous", "usuario_id"], "")
        self.assertEqual(records.loc["ambiguous", "vinculo_encuesta"], "DNI ambiguo")
        self.assertEqual(records.loc["wrong-type", "usuario_id"], "")

    def test_dni_is_not_returned_in_records_or_people(self):
        surveys = survey_rows(
            [{"_uuid": "one", "encuesta_responde": "Sí", "terreno_tipo": "Vivienda ocupada", "titular_servicio_dni": "30.123.456"}]
        )
        people = [["_submission__uuid", "encuestado_dni"], ["one", "31.234.567"]]

        result = build_surveys(surveys, people, self.users, self.neighborhoods, self.documents)

        self.assertNotIn("titular_servicio_dni", result.records.columns)
        self.assertNotIn("encuestado_dni", result.people.columns)
        self.assertFalse(any("30123456" in str(value) for value in result.records.to_numpy().ravel()))

    def test_normalizes_argentine_document_numbers(self):
        self.assertEqual(document_id("30.123.456"), "30123456")
        self.assertEqual(document_id("001234567"), "1234567")
        self.assertEqual(document_id("CUIT 20-30123456-7"), "")


if __name__ == "__main__":
    unittest.main()
