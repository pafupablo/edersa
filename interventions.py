"""Vinculación auditable de propuestas y acciones, sin cruces por barrio solo."""
from datetime import date, datetime
from io import BytesIO
import re
import unicodedata
import pandas as pd

SHEET = "CARGAR SOLUCIONES ACÁ"
SOURCE_URL = "https://docs.google.com/spreadsheets/d/1x-KtYXZDIbylgitLAVtcNcFkib5NGajz/edit?gid=1014042561"
COLUMNS = ["remesa", "nis_fuente", "persona", "cuenta", "solucion", "fecha_fuente", "ejecutada_fuente", "observacion", "sum_fuente", "nombre_fuente", "domicilio_fuente", "barrio_fuente"]
EXPECTED = {1: "nis", 2: "persona", 3: "cuenta", 4: "solucion propuesta", 5: "fecha", 6: "ejecutada", 11: "barrio"}
EMPTY_HEADER = ["Remesa", "NIS", "Persona", "Cuenta", "SOLUCIÓN/PROPUESTA", "Fecha", "Ejecutada", "Observación", "sum", "Nombre", "Domicilio", "barrio"]


def plain(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def normalized(value):
    value = "".join(c for c in unicodedata.normalize("NFD", plain(value).casefold()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


def numeric_id(value):
    value = re.sub(r"\.0$", "", plain(value)).replace(" ", "")
    return str(int(value)) if value.isdigit() and int(value) > 0 else ""


def neighborhood_key(value):
    value = normalized(value)
    words = {"2": "dos", "4": "cuatro", "10": "diez"}
    value = " ".join(words.get(word, word) for word in value.split())
    return re.sub(r"^barrio ", "", value)


def same_neighborhood(source, user):
    source_key = neighborhood_key(source)
    target_key = neighborhood_key(user.barrio)
    if not source_key or not bool(user.barrio_vinculado):
        return None
    options = {target_key}
    locality = neighborhood_key(user.localidad)
    if locality and target_key.endswith(" " + locality):
        options.add(target_key[:-(len(locality) + 1)])
    return source_key in options


def read_workbook(content):
    """Solo A:L de la pestaña solicitada. No importa contactos, DNI ni deudas."""
    from openpyxl import load_workbook
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    try:
        if SHEET not in workbook.sheetnames:
            raise ValueError(f"No se encontró la pestaña {SHEET}.")
        rows = []
        for row in workbook[SHEET].iter_rows(max_col=12, values_only=True):
            rows.append([v.isoformat() if isinstance(v, (date, datetime)) else v for v in row])
        return rows
    finally:
        workbook.close()


def execution_status(value):
    key = normalized(value)
    return {"si": "Ejecutada", "no": "No ejecutada", "se niega": "Rechazada", "resolvieron": "Resuelto por la familia", "": "Sin confirmar"}.get(key, plain(value))


def intervention_date(value):
    raw = plain(value)
    if not raw:
        return pd.NaT
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T.*| .*)?", raw):
        return pd.to_datetime(raw, errors="coerce")
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", raw):
        return pd.to_datetime(raw, format="%d/%m/%Y", errors="coerce")
    return pd.NaT


def link_interventions(rows, users):
    if not rows or any(i >= len(rows[0]) or normalized(rows[0][i]) != name for i, name in EXPECTED.items()):
        raise ValueError("La estructura de CARGAR SOLUCIONES ACÁ cambió; revisar NIS, Persona, Cuenta, solución, fecha y barrio.")
    records, incomplete = [], []
    for row_number, values in enumerate(rows[1:], 2):
        values = list(values[:12]) + [None] * max(0, 12 - len(values))
        if not any(plain(v) for v in values):
            continue
        record = dict(zip(COLUMNS, values))
        record["fila_fuente"] = row_number
        record["registro_id"] = f"soluciones:{row_number}"
        (records if plain(record["solucion"]) else incomplete).append(record)
    events = pd.DataFrame(records, columns=COLUMNS + ["fila_fuente", "registro_id"])
    lookup = users.set_index("usuario_id", drop=False)
    nis_index, pc_index, person_index = {}, {}, {}
    user_parts = {}
    for user in users.itertuples():
        parts = plain(user.usuario_id).split("-")
        person, account = (numeric_id(parts[1]), numeric_id(parts[2])) if len(parts) == 3 else ("", "")
        user_parts[user.usuario_id] = (person, account)
        if numeric_id(user.nis):
            nis_index.setdefault(numeric_id(user.nis), set()).add(user.usuario_id)
        if person and account:
            pc_index.setdefault((person, account), set()).add(user.usuario_id)
        if person:
            person_index.setdefault(person, set()).add(user.usuario_id)

    def match(row):
        nis = numeric_id(row.nis_fuente)
        person, account = numeric_id(row.persona), numeric_id(row.cuenta)
        sum_match = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", plain(row.sum_fuente))
        sum_pc = (numeric_id(sum_match[1]), numeric_id(sum_match[2])) if sum_match else ("", "")
        if all(sum_pc) and ((person and person != sum_pc[0]) or (account and account != sum_pc[1])):
            candidates = nis_index.get(nis, set()) | pc_index.get((person, account), set()) | pc_index.get(sum_pc, set())
            return "Conflicto", "Persona/Cuenta y sum difieren", candidates, ""
        person = person or sum_pc[0]
        account = account or sum_pc[1]
        nis_candidates = nis_index.get(nis, set())
        pc_candidates = pc_index.get((person, account), set()) if person and account else set()
        candidates = nis_candidates | pc_candidates
        if nis_candidates and pc_candidates and not nis_candidates.intersection(pc_candidates):
            return "Conflicto", "NIS y Persona/Cuenta apuntan a usuarios diferentes", candidates, ""
        if nis_candidates:
            candidates = nis_candidates & pc_candidates if pc_candidates else nis_candidates
            method = "NIS exacto" + (" + Persona/Cuenta" if pc_candidates else "")
        elif pc_candidates:
            candidates, method = pc_candidates, "Persona/Cuenta exactos"
        elif person:
            candidates, method = person_index.get(person, set()), "Persona + barrio"
        else:
            return ("Sin coincidencia" if nis or account else "Sin identificadores"), "No hay clave suficiente en el padrón", set(), ""
        if not candidates:
            return "Sin coincidencia", "Identificadores ausentes del padrón", set(), ""
        matches_by_barrio = {uid for uid in candidates if same_neighborhood(row.barrio_fuente, lookup.loc[uid]) is True}
        if len(candidates) > 1:
            if len(matches_by_barrio) == 1:
                candidates = matches_by_barrio
                method += " + barrio"
            else:
                return "Ambiguo", "Más de un usuario posible; el barrio no resuelve el cruce", candidates, ""
        uid = next(iter(candidates))
        user_person, user_account = user_parts[uid]
        if (person and person != user_person) or (account and account != user_account):
            return "Conflicto", "Los componentes Persona/Cuenta contradicen al candidato", candidates, ""
        barrio_agrees = same_neighborhood(row.barrio_fuente, lookup.loc[uid])
        if barrio_agrees is False:
            return "Probable", method + "; barrio diferente: revisar", candidates, uid
        if nis and not nis_candidates:
            return "Probable", method + "; NIS informado no encontrado: revisar", candidates, uid
        if method == "Persona + barrio":
            if barrio_agrees is True:
                return "Probable", method + "; falta confirmar Cuenta", candidates, uid
            return "Sin coincidencia", "Persona sin Cuenta y sin corroboración de barrio", candidates, ""
        if not nis_candidates and barrio_agrees is not True:
            return "Probable", method + "; barrio sin corroborar", candidates, uid
        return "Confirmado", method + ("; barrio coincide" if barrio_agrees else ""), candidates, uid

    matched = [match(row) for row in events.itertuples()]
    events["vinculo"] = [r[0] for r in matched]
    events["criterio"] = [r[1] for r in matched]
    events["candidatos"] = [", ".join(sorted(r[2])) for r in matched]
    events["usuario_candidato"] = [r[3] for r in matched]
    events["usuario_id"] = [r[3] if r[0] == "Confirmado" else "" for r in matched]
    events["estado"] = events.ejecutada_fuente.map(execution_status)
    events["fecha"] = pd.to_datetime(events.fecha_fuente.map(intervention_date))
    for col in ("solucion", "barrio_fuente", "fecha_fuente", "observacion", "nombre_fuente", "domicilio_fuente"):
        events[col] = events[col].map(plain)
    # Cada fila es un registro, no una cantidad de obras. Duplicados exactos no cuentan dos veces.
    keys = events[COLUMNS].map(plain)
    events["duplicado_exacto"] = keys.duplicated(keep="first")
    return events, pd.DataFrame(incomplete, columns=COLUMNS + ["fila_fuente", "registro_id"])


def attach_interventions(users, events):
    users = users.copy()
    confirmed = events.loc[events.vinculo.eq("Confirmado") & ~events.duplicado_exacto]
    counts = confirmed.groupby("usuario_id").size()
    executed = confirmed.loc[confirmed.estado.eq("Ejecutada")].groupby("usuario_id").size()
    types = confirmed.groupby("usuario_id").solucion.agg(lambda values: "; ".join(sorted(set(values))))
    users["intervenciones_registros"] = users.usuario_id.map(counts).fillna(0).astype(int)
    users["intervenciones_ejecutadas"] = users.usuario_id.map(executed).fillna(0).astype(int)
    users["intervencion_tipos"] = users.usuario_id.map(types).astype("string").fillna("Sin registros vinculados")
    users["intervencion_grupo"] = users.intervenciones_ejecutadas.map(lambda n: "Con ejecución registrada" if n else "Sin ejecución registrada")
    return users
