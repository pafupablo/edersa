"""Helpers for the filters rendered in the Streamlit sidebar."""

import pandas as pd


PASE_FILTER_LABELS = {
    "BLANDO": "PASE blando",
    "DURO": "PASE duro",
    "No es PASE": "No es PASE",
}


def pase_filter_label(value):
    return PASE_FILTER_LABELS.get(value, value)


def filter_household_survey_status(users, choice):
    """Filter users by whether they have a linked residential survey."""
    if choice == "Todos":
        return users
    expected = {"Sí": True, "No": False}
    if choice not in expected:
        raise ValueError(f"Estado de encuesta desconocido: {choice}")
    linked = pd.to_numeric(users["encuestas_vinculadas"], errors="coerce").fillna(0).gt(0)
    return users.loc[linked.eq(expected[choice])]
