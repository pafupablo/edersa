"""Modelo de lectura: nunca escribe en las fuentes ni cruza por nombres."""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
import pandas as pd
from interventions import EMPTY_HEADER, link_interventions, attach_interventions
from surveys import SurveyDataset, build_surveys

UNKNOWN = "Sin información"
NO_BARRIO = "Sin barrio vinculado"
MIN_CONSUMPTION = 100


def general_consumption_trend(history, periods):
    """Linear fit to all eligible user history, without extrapolation."""
    eligible = history.loc[history.consumo.ge(MIN_CONSUMPTION)].dropna(subset=["periodo","consumo"]).sort_values("periodo")
    dates = pd.DatetimeIndex(periods)
    empty = pd.Series(float("nan"),index=dates,dtype=float)
    if eligible.periodo.nunique() < 2:
        return empty
    x = eligible.periodo.dt.year*12 + eligible.periodo.dt.month
    y = eligible.consumo
    centered = x - x.mean()
    slope = (centered*(y-y.mean())).sum() / (centered**2).sum()
    predicted = pd.Series(y.mean()+slope*(dates.year*12+dates.month-x.mean()),index=dates,dtype=float)
    return predicted.where((dates >= eligible.periodo.min()) & (dates <= eligible.periodo.max()))


HEADERS = {
    "usuarios": ["Usua_ID", "NIS", "Categoría", "Uso", "Programa", "Departamento por poligono", "id_renabap por poligono", "Hogares Sin Gas"],
    "gps": ["Usua_ID", "NIS", "Subt_coord", "Sibt_coord"],
    "consumo": ["Usua_ID", "Bimestre", "Consumo"],
    "barrios": ["ID Renabap", "Barrio", "Localidad", "Departamento", "Provincia", "Viviendas Estimadas", "PASE", "Tipo PASE", "Barrios para comparar"],
}


class DataError(ValueError):
    pass


def identifier(value):
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\.0$", "", str(value).strip())


def text(value):
    return "" if value is None or pd.isna(value) else str(value).strip()


def fold(value):
    return "".join(c for c in unicodedata.normalize("NFD", text(value).lower()) if unicodedata.category(c) != "Mn")


def number(value):
    if isinstance(value, (int, float)):
        return float(value)
    s = text(value).replace("\u00a0", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    return pd.to_numeric(s, errors="coerce")


MONTHS = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12}


def period(value):
    """Las fuentes muestran mmm-aa; no interpretar sus seriales como fechas."""
    s = fold(value)
    match = re.fullmatch(r"([a-z]{3})[- /](\d{2}|\d{4})", s)
    if match and match[1] in MONTHS:
        year = int(match[2])
        year = 2000 + year if year < 100 else year
        return pd.Timestamp(year, MONTHS[match[1]], 1)
    match = re.fullmatch(r"(\d{4})-(\d{2})(?:-\d{2})?", s)
    if match:
        return pd.to_datetime(s, errors="coerce").to_period("M").to_timestamp() if not pd.isna(pd.to_datetime(s, errors="coerce")) else pd.NaT
    return pd.NaT


def label_period(value):
    if pd.isna(value):
        return UNKNOWN
    names = list(MONTHS)
    end = value + pd.DateOffset(months=1)
    return f"{names[value.month - 1]}-{str(value.year)[-2:]} / {names[end.month - 1]}-{str(end.year)[-2:]}"


def frame(rows, key):
    if not rows:
        raise DataError(f"La fuente {key} está vacía.")
    headers = [text(h) for h in rows[0]]
    missing = set(HEADERS[key]) - set(headers)
    if missing:
        raise DataError(f"Faltan columnas en {key}: {', '.join(sorted(missing))}.")
    if len(headers) != len(set(headers)):
        raise DataError(f"Hay encabezados repetidos en {key}.")
    values = [list(r) + [None] * (len(headers) - len(r)) for r in rows[1:] if any(text(v) for v in r)]
    if any(len(r) > len(headers) for r in values):
        raise DataError(f"Hay filas con más columnas que encabezados en {key}.")
    return pd.DataFrame(values, columns=headers)


def unique_key(df, key, source):
    if df[key].eq("").any():
        raise DataError(f"Hay identificadores vacíos en {source}; corregir antes de consultar.")
    if df[key].duplicated().any():
        raise DataError(f"Hay identificadores repetidos en {source}; el cruce duplicaría los resultados.")


@dataclass
class Dataset:
    users: pd.DataFrame
    consumption: pd.DataFrame
    neighborhoods: pd.DataFrame
    quality: pd.DataFrame
    issues: dict[str, pd.DataFrame]
    raw_counts: dict[str, int]
    interventions: pd.DataFrame
    intervention_incomplete: pd.DataFrame
    surveys: SurveyDataset


def build_dataset(raw):
    frames = {key: frame(raw[key], key) for key in HEADERS}
    u, c, g, b = [frames[k].copy() for k in ("usuarios", "consumo", "gps", "barrios")]
    counts = {k: len(v) for k, v in frames.items()}
    for df in (u, c, g):
        df["Usua_ID"] = df["Usua_ID"].map(identifier)
    for df in (u, g):
        df["NIS"] = df["NIS"].map(identifier)
    u["id_renabap por poligono"] = u["id_renabap por poligono"].map(identifier)
    b["ID Renabap"] = b["ID Renabap"].map(identifier)
    for df, col, name in ((u, "Usua_ID", "Usuarios general"), (g, "Usua_ID", "Usuarios GPS"), (b, "ID Renabap", "Barrios")):
        unique_key(df, col, name)

    b = b.rename(columns={"ID Renabap": "renabap", "Barrio": "barrio", "Localidad": "localidad", "Departamento": "departamento_barrio", "PASE": "pase_barrio", "Tipo PASE": "tipo_pase", "Viviendas Estimadas": "viviendas_estimadas", "Barrios para comparar": "comparacion"})
    for col in ("barrio", "localidad", "departamento_barrio", "pase_barrio", "tipo_pase", "comparacion"):
        b[col] = b[col].map(text).replace("", UNKNOWN)
    b["tipo_pase_original"] = b.tipo_pase
    b["tipo_pase"] = b.tipo_pase.replace(UNKNOWN, "No es PASE")
    b["viviendas_estimadas"] = b["viviendas_estimadas"].map(number)
    u = u.rename(columns={"Usua_ID": "usuario_id", "NIS": "nis", "Categoría": "categoria", "Uso": "uso", "Programa": "programa", "Departamento por poligono": "departamento_usuario", "id_renabap por poligono": "renabap", "Hogares Sin Gas": "gas_fuente"})
    for col in ("categoria", "programa", "uso", "departamento_usuario"):
        u[col] = u[col].map(text).map(identifier).replace("", UNKNOWN)
    u["programa_grupo"] = u.programa.map(lambda v: UNKNOWN if v == UNKNOWN else "300" if v == "300" else "No 300")
    u["gas"] = u["gas_fuente"].map(lambda v: "Sin gas" if fold(v) == "sin gas" else UNKNOWN if not text(v) else text(v))
    unknown_b = u.loc[u.renabap.ne("") & ~u.renabap.isin(b.renabap)].copy()
    u = u.merge(b, on="renabap", how="left", validate="many_to_one", indicator="barrio_cruce")
    u["barrio_vinculado"] = u.barrio_cruce.eq("both")
    u["barrio"] = u.barrio.fillna(NO_BARRIO)
    u["barrio_etiqueta"] = u.apply(lambda r: f"{r.barrio} · {r.localidad} · {r.renabap}" if r.barrio_vinculado else NO_BARRIO, axis=1)
    for col in ("localidad", "pase_barrio", "tipo_pase", "comparacion"):
        u[col] = u[col].fillna("No es PASE" if col == "tipo_pase" else UNKNOWN)
    u["departamento"] = u.departamento_barrio.fillna(u.departamento_usuario).replace("", UNKNOWN)

    g = g.rename(columns={"Usua_ID": "usuario_id", "NIS": "nis_gps", "Subt_coord": "longitud", "Sibt_coord": "latitud"})
    for col in ("longitud", "latitud"):
        g[col] = g[col].map(number)
    g["gps_valido"] = g.latitud.between(-90, 90) & g.longitud.between(-180, 180) & ~(g.latitud.eq(0) & g.longitud.eq(0))
    invalid_g = g.loc[~g.gps_valido].copy()
    u = u.merge(g, on="usuario_id", how="left", validate="one_to_one")
    u["tiene_gps"] = u.gps_valido.fillna(False).astype(bool)
    u["nis_repetido"] = u.nis.ne("") & u.nis.duplicated(keep=False)

    c = c.rename(columns={"Usua_ID": "usuario_id", "Bimestre": "bimestre_fuente", "Consumo": "consumo_fuente"})
    c["periodo_facturado"] = c.bimestre_fuente.map(period)
    c["periodo"] = c.periodo_facturado - pd.DateOffset(months=2)
    c["consumo"] = c.consumo_fuente.map(number)
    duplicate_c = c.duplicated(["usuario_id", "periodo"], keep=False)
    invalid_c = c.periodo.isna() | c.consumo.isna() | c.consumo.lt(0) | c.usuario_id.eq("") | duplicate_c
    excluded_c = c.loc[invalid_c].copy()
    orphan_c = c.loc[~c.usuario_id.isin(u.usuario_id)].copy()
    c = c.loc[~invalid_c & c.usuario_id.isin(u.usuario_id)].copy()
    c = c.sort_values(["periodo", "usuario_id"]).reset_index(drop=True)
    u["tiene_consumo"] = u.usuario_id.isin(c.usuario_id)
    u["tiene_consumo_estadistico"] = u.usuario_id.isin(c.loc[c.consumo.ge(MIN_CONSUMPTION), "usuario_id"])
    mismatch = u.nis_gps.notna() & u.nis.ne(u.nis_gps)
    u["nis_gps_distinto"] = mismatch
    issues = {
        "RENABAP sin correspondencia": unknown_b,
        "Consumos excluidos": excluded_c,
        "Consumos sin usuario": orphan_c,
        "GPS sin usuario": g.loc[~g.usuario_id.isin(u.usuario_id)].copy(),
        "GPS inválido": invalid_g,
        "NIS diferente entre fuentes": u.loc[mismatch, ["usuario_id", "nis", "nis_gps"]],
        "NIS repetido en usuarios": u.loc[u.nis_repetido, ["usuario_id", "nis"]],
    }
    quality = pd.DataFrame([
        {"Control": "Usuarios sin consumo válido", "Cantidad": int((~u.tiene_consumo).sum()), "Criterio": "No se imputa consumo cero."},
        {"Control": "Mediciones de consumo menores a 100", "Cantidad": int(c.consumo.lt(MIN_CONSUMPTION).sum()), "Criterio": "Se conservan en las fichas; no entran en estadísticas ni en su cantidad de mediciones de consumo."},
        {"Control": "Usuarios sin GPS válido", "Cantidad": int((~u.tiene_gps).sum()), "Criterio": "La ficha sigue disponible."},
        {"Control": "Usuarios sin RENABAP", "Cantidad": int(u.renabap.eq("").sum()), "Criterio": "Sin asignación de barrio."},
        {"Control": "RENABAP sin correspondencia", "Cantidad": len(unknown_b), "Criterio": "El código no existe en Barrios."},
        {"Control": "Consumos excluidos", "Cantidad": len(excluded_c), "Criterio": "Valor inválido, negativo, período inválido o clave repetida; nunca se suman duplicados."},
        {"Control": "Consumos sin usuario", "Cantidad": len(orphan_c), "Criterio": "Se excluyen del universo principal."},
        {"Control": "GPS sin usuario", "Cantidad": len(issues["GPS sin usuario"]), "Criterio": "No se crean hogares a partir de estos puntos."},
        {"Control": "NIS diferente entre fuentes", "Cantidad": int(mismatch.sum()), "Criterio": "Cruce por Usua_ID; revisar discrepancia."},
        {"Control": "Usuarios con NIS repetido", "Cantidad": int(u.nis_repetido.sum()), "Criterio": "No unir por NIS ni interpretar como hogares distintos confirmados."},
    ])
    events, incomplete = link_interventions(raw.get("intervenciones", [EMPTY_HEADER]), u)
    u = attach_interventions(u, events)
    counts["intervenciones"] = len(events) + len(incomplete)
    issues["Intervenciones con vínculo pendiente"] = events.loc[~events.vinculo.eq("Confirmado")].copy()
    issues["Filas sin solución especificada"] = incomplete
    quality = pd.concat([quality, pd.DataFrame([
        {"Control": "Intervenciones con vínculo confirmado", "Cantidad": int(events.vinculo.eq("Confirmado").sum()), "Criterio": "Vínculo de identidad; no implica que la acción esté ejecutada."},
        {"Control": "Intervenciones con vínculo pendiente", "Cantidad": int((~events.vinculo.eq("Confirmado")).sum()), "Criterio": "Probables, conflictos, ambiguos o sin coincidencia: no se asignan al usuario."},
        {"Control": "Filas sin solución especificada", "Cantidad": len(incomplete), "Criterio": "Se conservan para revisar; no se contabilizan como intervenciones."},
        {"Control": "Registros de intervención duplicados exactos", "Cantidad": int(events.duplicado_exacto.sum()), "Criterio": "Se conservan para auditar; no se cuentan dos veces en el usuario."},
    ])], ignore_index=True)
    surveys = build_surveys(raw.get("encuestas", []), raw.get("personas", []), u, b)
    counts["encuestas"] = len(surveys.records)
    counts["personas"] = len(surveys.people)
    survey_links = surveys.records.loc[surveys.records.residencial & surveys.records.usuario_id.ne("")].groupby("usuario_id").size()
    u["encuestas_vinculadas"] = u.usuario_id.map(survey_links).fillna(0).astype(int)
    return Dataset(u, c, b, quality, issues, counts, events, incomplete, surveys)


def consumption_summary(consumption, ids, periods):
    selected = consumption.loc[consumption.usuario_id.isin(ids) & consumption.periodo.isin(periods) & consumption.consumo.ge(MIN_CONSUMPTION)]
    if selected.empty:
        return selected, pd.DataFrame(columns=["periodo", "promedio", "mediana", "p25", "p75", "desvio", "total", "usuarios"])
    summary = selected.groupby("periodo", as_index=False).agg(promedio=("consumo", "mean"), mediana=("consumo", "median"), p25=("consumo", lambda s: s.quantile(.25)), p75=("consumo", lambda s: s.quantile(.75)), desvio=("consumo", "std"), total=("consumo", "sum"), usuarios=("usuario_id", "nunique"))
    return selected, summary


def evolution_statistics(consumption, users, periods):
    """Consumo y cantidades con denominadores explícitos para pantalla y CSV."""
    selected, summary = consumption_summary(consumption, users.usuario_id, periods)
    result = pd.DataFrame({"periodo": periods}).merge(summary.drop(columns=["desvio"]), on="periodo", how="left")
    raw = consumption.loc[consumption.usuario_id.isin(users.usuario_id) & consumption.periodo.isin(periods)]
    observed = raw.groupby("periodo").usuario_id.nunique()
    below = raw.loc[raw.consumo.lt(MIN_CONSUMPTION)].groupby("periodo").usuario_id.nunique()
    result["usuarios_padron"] = len(users)
    result["usuarios_observados"] = result.periodo.map(observed).fillna(0).astype(int)
    result["usuarios"] = result.usuarios.fillna(0).astype(int)
    result["menores_100"] = result.periodo.map(below).fillna(0).astype(int)
    result["sin_registro_periodo"] = len(users) - result.usuarios_observados
    result["cobertura"] = result.usuarios / len(users) * 100 if len(users) else float("nan")
    previous = result.mediana.shift(1)
    result["variacion_mediana_pct"] = (result.mediana / previous.where(previous.ne(0)) - 1) * 100
    return selected, result


def group_statistics(consumption, users, group, periods):
    selected, _ = consumption_summary(consumption, users.usuario_id, periods)
    observations = selected.merge(users[["usuario_id", group]].rename(columns={group: "grupo"}), on="usuario_id", how="inner", validate="many_to_one")
    groups = users.groupby(group).usuario_id.nunique()
    index = pd.MultiIndex.from_product([groups.index, periods], names=["grupo", "periodo"])
    stats = observations.groupby(["grupo", "periodo"]).agg(mediana=("consumo", "median"), media=("consumo", "mean"), p25=("consumo", lambda s: s.quantile(.25)), p75=("consumo", lambda s: s.quantile(.75)), desvio=("consumo", "std"), con_dato=("usuario_id", "nunique")).reindex(index).reset_index()
    stats["con_dato"] = stats.con_dato.fillna(0).astype(int)
    stats["usuarios"] = stats.grupo.map(groups)
    stats["cobertura"] = stats.con_dato / stats.usuarios * 100
    return observations, stats
