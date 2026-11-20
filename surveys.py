"""Encuestas: unidades, denominadores y vínculos explícitos."""
from dataclasses import dataclass
import re
from numbers import Real
import pandas as pd
from interventions import numeric_id, normalized, neighborhood_key

SURVEY_FIELDS = [
    "_id", "_uuid", "_submission_time", "start", "end", "barrio_nombre", "manzana", "lote", "vivienda_n", "terreno_tipo", "edificacion_tipo", "encuesta_responde", "edificacion_propiedad", "viviendas_cantidad", "familias_cantidad", "personas_cantidad", "personas_mayores_edad_cantidad", "personas_menores_edad_cantidad", "numero_cliente_edersa", "superficie_construida", "ambientes_totales", "ambientes_dormir", "bano_hay", "bano_descarga_agua", "cocina_hay", "vivienda_piso_material", "vivienda_pared_material", "vivienda_techo_exterior_material", "vivienda_techo_interior_material/Riesgo_de_derrumbe", "vivienda_estado_general", "vivienda_aberturas_filtraciones", "vivienda_ventanas_material", "pilar_hay", "tablero_hay", "puesta_tierra_hay", "cortes_electricidad", "tienen_cables_a_la_vista", "existen_corto_circuitos_sobrecarga", "falta_electricidad_en_algunas_partes_casa", "principio_incendio_prob_electr", "dano_electrodomestico_prob_electr", "descarga_electrica_personas", "estufa_gas", "estufa_lena", "aire_acondicionado_hay", "aire_acondicionado_cantidad", "calefactor_electrico_cantidad", "energia_calefaccion_agua", "energia_calefaccion_agua/Electricidad", "energia_calefaccion_agua/Gas", "energia_calefaccion_agua/Leña", "energia_cocina", "energia_cocina/Electricidad", "energia_cocina/Gas", "energia_cocina/Leña", "termotanque_electrico_hay", "termotanque_gas_hay", "ducha_electrica", "electrodependiente", "acceso_servicios", "acceso_servicios/Agua_de_red", "acceso_servicios/Cloaca_pública", "acceso_servicios/Gas_de_red", "acceso_servicios/Red_eléctrica",
]
PERSON_FIELDS = ["genero", "edad_encuesta", "_submission__uuid", "_submission__id", "datos_encuestado_hay", "nivel_educativo_alcanzado"]
PROBLEMS = {
    "tienen_cables_a_la_vista": "Cables a la vista",
    "existen_corto_circuitos_sobrecarga": "Cortocircuitos o sobrecargas",
    "falta_electricidad_en_algunas_partes_casa": "Sectores de la vivienda sin luz",
    "principio_incendio_prob_electr": "Principio de incendio eléctrico",
    "dano_electrodomestico_prob_electr": "Daño en electrodomésticos",
    "descarga_electrica_personas": "Descargas a personas",
}


@dataclass
class SurveyDataset:
    records: pd.DataFrame
    people: pd.DataFrame
    issues: dict


def yes_no(value):
    if isinstance(value, Real) and value in (0, 1):
        return bool(value)
    key = normalized(value)
    return True if key in ("si", "1", "true") else False if key in ("no", "0", "false") else None


def rows_frame(rows, fields):
    if not rows:
        return pd.DataFrame(columns=fields)
    headers = rows[0]
    indexes = {key: headers.index(key) for key in fields if key in headers}
    values = [{key: row[index] if index < len(row) else None for key, index in indexes.items()} for row in rows[1:]]
    return pd.DataFrame(values, columns=fields)


def build_surveys(raw, people_raw, users, neighborhoods):
    s = rows_frame(raw, SURVEY_FIELDS)
    p = rows_frame(people_raw, PERSON_FIELDS)
    s = s.loc[s._uuid.notna() & s._uuid.astype(str).str.strip().ne("")].copy()
    if s._uuid.duplicated().any():
        raise ValueError("Hay UUID de encuesta repetidos; revisar antes de caracterizar hogares.")
    s["survey_uuid"] = s._uuid.astype(str)
    s["completa"] = s.encuesta_responde.map(yes_no).eq(True)
    s["residencial"] = s.completa & s.terreno_tipo.map(normalized).eq("vivienda ocupada")
    b = neighborhoods.set_index("renabap", drop=False)
    name_map = {}
    for row in neighborhoods.itertuples():
        name_map.setdefault(neighborhood_key(row.barrio), []).append(row.renabap)

    def resolve_barrio(value):
        label = str(value or "").replace("_", " ").strip()
        match = re.search(r"ID\s*:\s*(\d+)", label, re.I)
        if match:
            renabap = match[1]
            return renabap if renabap in b.index else ""
        choices = name_map.get(neighborhood_key(label), [])
        return choices[0] if len(choices) == 1 else ""

    s["renabap_encuesta"] = s.barrio_nombre.map(resolve_barrio)
    def barrio_label(row):
        if row.renabap_encuesta in b.index:
            br = b.loc[row.renabap_encuesta]
            return f"{br.barrio} · {br.localidad}"
        original = str(row.barrio_nombre or "Sin información").replace("_", " ")
        return original.capitalize() + " · ubicación sin confirmar"
    s["barrio_encuesta"] = s.apply(barrio_label, axis=1) if len(s) else pd.Series(dtype="str")
    s["localidad_encuesta"] = s.renabap_encuesta.map(b.localidad).fillna("Sin información")
    s["departamento_encuesta"] = s.renabap_encuesta.map(b.departamento_barrio).fillna("Sin información")
    s["pase_encuesta"] = s.renabap_encuesta.map(b.pase_barrio).fillna("Sin información")
    s["tipo_pase_encuesta"] = s.renabap_encuesta.map(b.tipo_pase).fillna("No es PASE")
    numeric = ["personas_cantidad", "personas_mayores_edad_cantidad", "familias_cantidad", "superficie_construida", "ambientes_dormir", "ambientes_totales", "calefactor_electrico_cantidad", "aire_acondicionado_cantidad"]
    for col in numeric:
        s[col] = pd.to_numeric(s[col], errors="coerce").where(lambda v: v.ge(0))
    s["menores_derivados"] = (s.personas_cantidad - s.personas_mayores_edad_cantidad).where(s.personas_cantidad.ge(s.personas_mayores_edad_cantidad))
    s["personas_por_ambiente"] = s.personas_cantidad / s.ambientes_totales.where(s.ambientes_totales.gt(0))
    s["hacinamiento_critico"] = s.personas_por_ambiente.map(lambda n: None if pd.isna(n) else n > 3)
    s["calefactor_electrico"] = s.calefactor_electrico_cantidad.map(lambda n: None if pd.isna(n) else n > 0)
    for column in PROBLEMS:
        s[column + "_bool"] = s[column].map(yes_no)
    problems = s[[col + "_bool" for col in PROBLEMS]]
    s["algun_problema_electrico"] = [True if any(v is True for v in row) else False if all(v is False for v in row) else None for row in problems.itertuples(index=False, name=None)]
    # Las cantidades de menores se derivan de total y mayores; el campo homónimo cambió de significado.
    numeric_dates = pd.to_numeric(s._submission_time, errors="coerce")
    s["fecha_encuesta"] = pd.to_datetime(numeric_dates, unit="D", origin="1899-12-30", errors="coerce")
    non_numeric = numeric_dates.isna() & s._submission_time.notna()
    s.loc[non_numeric, "fecha_encuesta"] = pd.to_datetime(s.loc[non_numeric, "_submission_time"], errors="coerce")
    # El NIS es el único identificador de suministro documentado en esta encuesta.
    nis_map = {}
    for user in users.itertuples():
        if numeric_id(user.nis):
            nis_map.setdefault(numeric_id(user.nis), []).append(user)
    links, states = [], []
    for row in s.itertuples():
        nis = numeric_id(row.numero_cliente_edersa)
        candidates = nis_map.get(nis, [])
        if len(candidates) > 1 and row.renabap_encuesta:
            candidates = [user for user in candidates if user.renabap == row.renabap_encuesta]
        if len(candidates) == 1:
            candidate = candidates[0]
            conflict = bool(row.renabap_encuesta and candidate.renabap and row.renabap_encuesta != candidate.renabap)
            links.append("" if conflict else candidate.usuario_id)
            states.append("Barrio diferente; revisar" if conflict else "NIS confirmado")
        else:
            links.append("")
            states.append("NIS ambiguo" if len(candidates) > 1 else "Sin NIS" if not nis else "NIS fuera del padrón")
    s["usuario_id"] = links
    s["vinculo_encuesta"] = states
    key = ["barrio_nombre", "manzana", "lote", "vivienda_n"]
    keys = s[key].astype("string").fillna("")
    s["ubicacion_repetida"] = keys.duplicated(keep=False) & keys.ne("").all(axis=1) & s.residencial
    # Registros de personas siempre se vinculan por UUID, nunca por posición.
    p["survey_uuid"] = p["_submission__uuid"].fillna("").astype(str)
    p["edad"] = pd.to_numeric(p.edad_encuesta, errors="coerce").where(lambda v: v.between(0, 115))
    p["genero"] = p.genero.fillna("").astype(str).str.strip()
    p = p.loc[p.survey_uuid.isin(s.survey_uuid)].copy()
    issues = {
        "Ubicaciones con varias encuestas": s.loc[s.ubicacion_repetida, ["survey_uuid", "barrio_encuesta", "manzana", "lote", "vivienda_n", "fecha_encuesta"]],
        "Encuestas residenciales sin vínculo al padrón": s.loc[s.residencial & s.usuario_id.eq(""), ["survey_uuid", "barrio_encuesta", "vinculo_encuesta"]],
    }
    return SurveyDataset(s, p, issues)


def binary_stats(values, positive=True):
    answers = pd.Series(values).map(yes_no)
    valid = answers.notna()
    denominator = int(valid.sum())
    numerator = int(answers.loc[valid].eq(positive).sum())
    return {"n": numerator, "base": denominator, "missing": int((~valid).sum()), "pct": numerator / denominator * 100 if denominator else float("nan")}
