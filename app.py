from __future__ import annotations

import html
import json
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

from data_access import ROOT, SOURCES, load_local, load_sheets, local_available
from model import DataError, UNKNOWN, build_dataset, evolution_statistics, group_statistics, label_period, general_consumption_trend, critical_consumption
from sidebar_filters import filter_household_survey_status, pase_filter_label
from charts import evolution_chart, individual_history_chart, trend_sparkline_svg
from characterization import render_characterization, render_linked_household
from neighborhoods import render_neighborhoods

st.set_page_config(page_title="EdERSA · Explorador", page_icon="◉", layout="wide")

st.info("Versión de prueba · datos al 17/11/2026 · no se actualizan automáticamente desde Sheets.")

st.markdown("""<style>
.block-container{padding-top:3.5rem;padding-bottom:3rem;max-width:1550px}
[data-testid="stSidebar"]{background:#30598F}
[data-testid="stSidebar"] *{color:#E5EEF5}
[data-testid="stSidebar"] input{color:#152B42}
[data-testid="stSidebar"] [data-baseweb="select"] *{color:#152B42}
[data-testid="stSidebar"] button,[data-testid="stSidebar"] button *{color:#152B42}
[data-testid="stSidebar"] [data-testid="stButton"] button{background:#FFC600;border-color:#FFC600}
h1,h2,h3{letter-spacing:-.035em}
.eyebrow{font-size:.72rem;font-weight:700;letter-spacing:.16em;color:#1B5798;margin-bottom:.4rem}
.intro{color:#5B6E80;font-size:1rem;max-width:850px;line-height:1.6}
.badge{display:inline-block;padding:5px 11px;border-radius:20px;background:#FFF3C7;color:#234B7B;font-size:.75rem;font-weight:600}
[data-testid="stMetric"]{background:white;border:1px solid #E1E8EF;padding:18px;border-radius:12px}
[data-testid="stMetricLabel"]{color:#5B6E80;font-size:.82rem}
[data-testid="stMetricValue"]{font-size:1.9rem}
[data-testid="stDataFrame"]{border-radius:10px}
.source-foot{color:#64798B;font-size:.78rem;padding-top:15px;border-top:1px solid #DFE7EF;margin-top:25px}
@media(max-width:1100px){
 [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]){flex-wrap:wrap}
 [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"]{min-width:calc(50% - 1rem);flex:1 1 calc(50% - 1rem)}
}
</style>""", unsafe_allow_html=True)

COLORS = ["#30598F", "#EBAE00", "#008DB8", "#6E86AF", "#B27D00", "#8ABBD6", "#634C99", "#52705A", "#AE6672", "#806B51", "#576070", "#B6A3CF"]


def fmt(value, decimals=0):
    if pd.isna(value):
        return "—"
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def csv_bytes(frame):
    safe = frame.copy()
    for col in safe.select_dtypes(include=["object", "str"]).columns:
        safe[col] = safe[col].map(lambda v: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) else v)
    return safe.to_csv(index=False, sep=";").encode("utf-8-sig")


def median_style(value):
    if pd.isna(value):
        return ""
    if value > 1000:
        return "background-color: #FDE2E2; color: #9F1239; font-weight: bold"
    if value >= 800:
        return "background-color: #FFF0B3; color: #754900; font-weight: bold"
    return ""


def chart(fig, key=None, height=320, top_margin=15, plot_background="rgba(0,0,0,0)"):
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=12, r=12, t=top_margin, b=15), font=dict(family="Arial", color="#36506B"), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=plot_background, colorway=COLORS, legend_title_text="", separators=",.")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#E6EDF2")
    st.plotly_chart(fig, width="stretch", key=key, config={"displaylogo": False})


@st.cache_data(ttl=300, show_spinner=False)
def cached_load(mode, model_version):
    if mode == "Google Sheets + Drive":
        raw, fetched_at = load_sheets(st.secrets["gcp_service_account"])
    else:
        raw, fetched_at = load_local()
    return build_dataset(raw), fetched_at


def credentials_available():
    try:
        return "gcp_service_account" in st.secrets
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return False


def source_controls(options, mode):
    with st.sidebar:
        st.divider()
        st.caption("FUENTES Y ACTUALIZACIÓN")
        st.selectbox("Fuente de datos", options, index=options.index(mode), key="source_mode")
        if st.button("↻ Actualizar datos", width="stretch"):
            cached_load.clear()
            st.rerun()


with st.sidebar:
    st.markdown("### ◉ EdERSA")
    st.caption("EXPLORADOR DE USUARIOS")
    options = (["Google Sheets + Drive"] if credentials_available() else []) + (["Copia de prueba"] if local_available() else [])
    if not options:
        st.info("Falta configurar el acceso a las fuentes.")
        st.markdown("Consultá la guía de conexión del proyecto.")
        st.stop()
    mode = st.session_state.get("source_mode", options[0])
    if mode not in options:
        mode = options[0]
        st.session_state["source_mode"] = mode

try:
    with st.spinner("Relacionando usuarios, barrios y consumos…"):
        dataset, fetched_at = cached_load(mode, "household-details-roof-v3")
except DataError as exc:
    source_controls(options, mode)
    st.error(str(exc))
    st.info("Se detuvo la consulta para evitar resultados duplicados o cruces incorrectos. Corregí la fuente y actualizá los datos.")
    st.stop()
except Exception:
    source_controls(options, mode)
    st.error("No se pudieron leer las fuentes. Revisá la conexión, las credenciales y que todos los archivos estén compartidos como lector con la cuenta de servicio. El Excel de soluciones requiere acceso a Google Drive API.")
    st.info("La actualización no modifica las planillas. Podés volver a intentar con ‘Actualizar datos’.")
    st.stop()

u, c, interventions = dataset.users, dataset.consumption, dataset.interventions
all_periods = sorted(c.periodo.unique())
all_periods = [pd.Timestamp(p) for p in all_periods]

with st.sidebar:
    st.divider()
    section = st.radio("Navegación", ["Panorama", "Usuarios y fichas", "Comparar grupos", "Intervenciones", "Barrios", "Caracterización de hogares", "Fuentes y calidad"], label_visibility="collapsed", key="navigation")
    st.divider()
    st.markdown("#### Selección de encuestas" if section == "Caracterización de hogares" else "#### Selección de barrios" if section == "Barrios" else "#### Selección de usuarios")
    if st.button("Limpiar filtros", width="stretch"):
        for key in list(st.session_state):
            if key.startswith(("filter_", "survey_filter_", "barrio_filter_")):
                del st.session_state[key]
        st.rerun()

    filtered = u.copy()

    def multiselect_filter(label, column, format_func=str):
        global filtered
        values = sorted(filtered[column].dropna().astype(str).unique())
        key = f"filter_{column}"
        if key in st.session_state:
            st.session_state[key] = [v for v in st.session_state[key] if v in values]
        selected = st.multiselect(label, values, key=key, placeholder="Todos", format_func=format_func)
        if selected:
            filtered = filtered.loc[filtered[column].isin(selected)]

    if section == "Caracterización de hogares":
        survey_selected = dataset.surveys.records.copy()
        def survey_filter(label, column):
            global survey_selected
            values = sorted(survey_selected[column].dropna().astype(str).unique())
            key = "survey_filter_" + column
            if key in st.session_state:
                st.session_state[key] = [v for v in st.session_state[key] if v in values]
            selection = st.multiselect(label, values, key=key, placeholder="Todos")
            if selection:
                survey_selected = survey_selected.loc[survey_selected[column].astype(str).isin(selection)]
        survey_filter("Departamento", "departamento_encuesta")
        survey_filter("Localidad", "localidad_encuesta")
        survey_filter("Barrio de la encuesta", "barrio_encuesta")
        survey_filter("Tipo PASE del barrio", "tipo_pase_encuesta")
        with st.expander("Ubicación y vínculo al padrón"):
            survey_filter("Manzana", "manzana")
            survey_filter("Lote", "lote")
            scope = st.selectbox("Universo de lectura", ["Todas las encuestas", "Solo NIS confirmado en el padrón"], key="survey_filter_scope")
            if scope != "Todas las encuestas":
                survey_selected = survey_selected.loc[survey_selected.usuario_id.ne("")]
        st.caption(f"{fmt(survey_selected.residencial.sum())} encuestas residenciales completas")
        st.caption("Esta sección utiliza filtros de encuestas y conserva los hogares sin NIS vinculado.")
    elif section == "Barrios":
        neighborhoods_selected = dataset.neighborhoods.copy()
        neighborhoods_selected["etiqueta_barrio"] = neighborhoods_selected.barrio + " · " + neighborhoods_selected.localidad + " · " + neighborhoods_selected.renabap
        def barrio_filter(label, column):
            global neighborhoods_selected
            values = sorted(neighborhoods_selected[column].dropna().astype(str).unique())
            key = "barrio_filter_" + column
            if key in st.session_state:
                st.session_state[key] = [value for value in st.session_state[key] if value in values]
            selected = st.multiselect(label, values, key=key, placeholder="Todos")
            if selected:
                neighborhoods_selected = neighborhoods_selected.loc[neighborhoods_selected[column].isin(selected)]
        barrio_filter("Departamento", "departamento_barrio")
        barrio_filter("Localidad", "localidad")
        barrio_filter("Barrio · localidad · RENABAP", "etiqueta_barrio")
        barrio_filter("Tipo PASE", "tipo_pase")
        st.caption(f"{fmt(len(neighborhoods_selected))} barrios. Se incluyen también los que no tienen usuarios en el padrón.")
    else:
        multiselect_filter("Departamento", "departamento")
        multiselect_filter("Localidad", "localidad")
        multiselect_filter("Barrio · localidad · RENABAP", "barrio_etiqueta")
        multiselect_filter("PASE", "tipo_pase", format_func=pase_filter_label)
        survey_status = st.selectbox(
            "Encuesta de hogar vinculada",
            ["Todos", "Sí", "No"],
            key="filter_household_survey",
            help="Sí indica que el usuario tiene al menos una encuesta residencial vinculada de forma confirmada.",
        )
        filtered = filter_household_survey_status(filtered, survey_status)
        multiselect_filter("Programa", "programa_grupo")
        multiselect_filter("Ejecución registrada · cualquier fecha", "intervencion_grupo")
        with st.expander("Más filtros"):
            multiselect_filter("Registro de gas", "gas")
            for label, col in [("Con consumo ≥100 en algún período", "tiene_consumo_estadistico")]:
                choice = st.selectbox(label, ["Todos", "Sí", "No"], key=f"filter_{col}")
                if choice != "Todos":
                    filtered = filtered.loc[filtered[col].eq(choice == "Sí")]
        search = st.text_input("Buscar Usua_ID o NIS", key="filter_search", placeholder="Escribí parte del identificador")
        if search.strip():
            query = search.strip().casefold()
            filtered = filtered.loc[filtered.usuario_id.str.casefold().str.contains(query, regex=False) | filtered.nis.str.casefold().str.contains(query, regex=False)]
        st.caption(f"{fmt(len(filtered))} de {fmt(len(u))} usuarios")

source_controls(options, mode)

if section == "Caracterización de hogares":
    render_characterization(dataset.surveys, survey_selected, fetched_at, csv_bytes)
    st.stop()

if section == "Barrios":
    render_neighborhoods(dataset, neighborhoods_selected, csv_bytes)
    st.stop()

st.markdown('<div class="eyebrow">INFORMACIÓN TERRITORIAL Y CONSUMOS</div>', unsafe_allow_html=True)
st.title({"Panorama": "Una mirada integrada", "Usuarios y fichas": "Del conjunto a cada usuario", "Comparar grupos": "Caracterizar y comparar", "Intervenciones": "Intervenciones en territorio", "Fuentes y calidad": "Conocer la cobertura"}[section])
st.markdown('<p class="intro">Explorá los usuarios registrados, su contexto barrial y sus consumos. Los filtros de la izquierda se aplican a todas las vistas.</p>', unsafe_allow_html=True)
st.markdown(f'<span class="badge">{html.escape(mode)} · {fmt(len(filtered))} usuarios seleccionados</span>', unsafe_allow_html=True)
st.caption("Unidad de análisis actual: usuario/suministro (Usua_ID). Estas fuentes no permiten confirmar un hogar por registro. PASE es una característica del barrio, no una intervención individual acreditada.")

if section not in ("Fuentes y calidad", "Intervenciones") and filtered.empty:
    st.info("No hay usuarios con esta combinación. Modificá los filtros o usá ‘Limpiar filtros’.")
    st.stop()

periods = all_periods
if section not in ("Fuentes y calidad", "Intervenciones") and all_periods:
    if len(all_periods) > 1:
        start, end = st.select_slider("Períodos consumidos", options=all_periods, value=(all_periods[0], all_periods[-1]), format_func=label_period, key="consumed_period_window")
        periods = [p for p in all_periods if start <= p <= end]
    else:
        st.caption(f"Período disponible: {label_period(all_periods[0])}")

selected_c, summary = evolution_statistics(c, filtered, periods)
raw_selected_c = c.loc[c.usuario_id.isin(filtered.usuario_id) & c.periodo.isin(periods)]
latest = periods[-1] if periods else None
latest_c = selected_c.loc[selected_c.periodo.eq(latest)] if latest is not None else selected_c
latest_raw = raw_selected_c.loc[raw_selected_c.periodo.eq(latest)] if latest is not None else raw_selected_c
if section not in ("Fuentes y calidad", "Intervenciones"):
    st.caption("Estadísticas: solo consumos ≥100; los menores a 100 se conservan en las fichas. Período consumido = los dos meses anteriores al mes facturado: feb-26 → dic-25 / ene-26. No se imputan faltantes como cero.")


def distribution(df, column, title, key, top=12):
    st.markdown(f"#### {title}")
    table = df.groupby(column, dropna=False).size().rename("Usuarios").reset_index().sort_values("Usuarios", ascending=False)
    if table.empty:
        st.info("Sin datos para esta selección.")
        return
    visible = table.head(top).sort_values("Usuarios")
    fig = px.bar(visible, y=column, x="Usuarios", orientation="h", color_discrete_sequence=COLORS, labels={column: ""}, text="Usuarios")
    fig.update_traces(textposition="outside", texttemplate="%{x:,.0f}", cliponaxis=False)
    chart(fig, key)
    if len(table) > top:
        st.caption(f"Se muestran las {top} categorías con más usuarios de {len(table)}.")


if section == "Panorama":
    st.write("")
    a, b, d, e = st.columns(4)
    a.metric("Usuarios seleccionados", fmt(len(filtered)))
    b.metric("Barrios vinculados", fmt(filtered.loc[filtered.barrio_vinculado, "renabap"].nunique()))
    d.metric("Usuarios con consumo ≥100", fmt(latest_c.usuario_id.nunique()), help=f"Período consumido: {label_period(latest)}.")
    e.metric("Consumo mediano · último período", fmt(latest_c.consumo.median(), 2), help="Mediana entre usuarios con consumo ≥100; se excluyen faltantes y valores menores a 100.")
    st.caption(f"Período consumido: {label_period(latest)} · Cobertura estadística: {fmt(100 * latest_c.usuario_id.nunique() / len(filtered), 2)}% · Mediciones de consumo menores a 100 excluidas: {fmt(latest_raw.consumo.lt(100).sum())}.")
    st.caption(f"En la selección: {fmt(filtered.intervenciones_registros.gt(0).sum())} usuarios con registros de soluciones vinculados y {fmt(filtered.intervenciones_ejecutadas.gt(0).sum())} con ejecución marcada ‘sí’ en alguna fecha. Sin registro no equivale a ausencia de intervención.")
    st.markdown("#### Evolución del consumo · mediana y media")
    if selected_c.empty:
        st.info("No hay consumos ≥100 para la selección y la ventana elegida.")
    else:
        chart(evolution_chart(summary), "evolution", height=680, top_margin=105, plot_background="#EEF3F8")
        st.caption("Arriba: mediana, media y 50% central del consumo bimestral, en la unidad de la fuente. Abajo: cantidad de usuarios (Usua_ID únicos) con consumo ≥100. Son ejes y magnitudes diferentes.")
        st.caption("❄️ Banda blanca: invierno austral (21 de junio–20 de septiembre). ☀️ Banda amarilla: verano austral (21 de diciembre–20 de marzo). Cada punto corresponde al total de un bimestre completo.")
        st.caption("El cursor informa la variación porcentual de la mediana respecto al período anterior y la cobertura de usuarios. La banda P25–P75 describe dispersión, no un intervalo de confianza.")
        st.caption("La cantidad de usuarios incluidos cambia por período. La evolución no representa necesariamente un grupo fijo de usuarios.")
    evolution_columns = {"periodo":"Período consumido", "mediana":"Consumo · mediana", "promedio":"Consumo · media", "p25":"Consumo · P25", "p75":"Consumo · P75", "total":"Consumo · total de valores ≥100", "usuarios_padron":"Usuarios · padrón seleccionado", "usuarios_observados":"Usuarios · con registro en período", "usuarios":"Usuarios · incluidos (consumo ≥100)", "menores_100":"Usuarios · excluidos por consumo <100", "sin_registro_periodo":"Usuarios · sin registro en período", "cobertura":"Usuarios · cobertura estadística %", "variacion_mediana_pct":"Consumo · variación de mediana %"}
    evolution_export = summary.assign(periodo=summary.periodo.map(label_period))[list(evolution_columns)].rename(columns=evolution_columns)
    st.download_button("Descargar evolución de consumo y usuarios · CSV",csv_bytes(evolution_export),"edersa_evolucion_consumo_usuarios.csv","text/csv")
    left, right = st.columns(2)
    with left:
        distribution(filtered, "localidad", "Distribución por localidad", "locality", 10)
    with right:
        distribution(filtered, "tipo_pase", "Tipo PASE del barrio", "pase_type")
    with st.expander("Ver cifras de la evolución"):
        evolution_display = evolution_export.copy()
        decimal_columns = ["Consumo · mediana", "Consumo · media", "Consumo · P25", "Consumo · P75", "Consumo · total de valores ≥100", "Usuarios · cobertura estadística %", "Consumo · variación de mediana %"]
        integer_columns = ["Usuarios · padrón seleccionado", "Usuarios · con registro en período", "Usuarios · incluidos (consumo ≥100)", "Usuarios · excluidos por consumo <100", "Usuarios · sin registro en período"]
        for column in decimal_columns:
            evolution_display[column] = evolution_display[column].map(lambda value: fmt(value, 2))
        for column in integer_columns:
            evolution_display[column] = evolution_display[column].map(lambda value: fmt(value, 0))
        st.dataframe(evolution_display, hide_index=True, width="stretch")

elif section == "Usuarios y fichas":
    metrics = latest_raw[["usuario_id", "consumo"]].rename(columns={"consumo": "consumo_ultimo"})
    view = filtered.merge(metrics, on="usuario_id", how="left", validate="one_to_one")
    medians = selected_c.groupby("usuario_id").consumo.median()
    view["mediana_usuario"] = view.usuario_id.map(medians)
    view["cantidad_consumos"] = view.usuario_id.map(raw_selected_c.groupby("usuario_id").size()).fillna(0).astype(int)
    executed_events = interventions.loc[interventions.vinculo.eq("Confirmado") & ~interventions.duplicado_exacto & interventions.estado.eq("Ejecutada")]
    executed_labels = executed_events.groupby("usuario_id").solucion.agg(lambda values: "; ".join(sorted(set(values))))
    view["ejecuciones_etiquetas"] = view.usuario_id.map(executed_labels).fillna("Sin ejecución registrada")
    view["consumo_critico"] = view.apply(lambda item:critical_consumption(item.mediana_usuario,item.consumo_ultimo),axis=1)
    columns = {"usuario_id": "Usua_ID", "nis": "NIS", "mediana_usuario": "Mediana", "cantidad_consumos": "Mediciones de consumo", "consumo_critico": "Consumo crítico", "barrio": "Barrio", "localidad": "Localidad", "tipo_pase": "Tipo PASE", "programa_grupo": "Programa", "intervencion_tipos": "Soluciones registradas", "ejecuciones_etiquetas": "Intervenciones ejecutadas"}
    listing = view[list(columns)].rename(columns=columns).reset_index(drop=True)
    st.markdown("#### Usuarios de la selección")
    st.caption("Seleccioná una fila para abrir su ficha. También podés buscar por identificador con los filtros.")
    st.caption("Mediana: consumos ≥100 en la ventana seleccionada. Rojo: >1000; amarillo: 800–1000. Cantidad: todos los registros de consumo de esa ventana, incluidos los menores a 100. Consumo crítico: mediana o último valor >1000. Las soluciones y ejecuciones muestran sus etiquetas; pasá el cursor sobre una celda para leer el texto completo.")
    compact_listing = listing.copy()
    compact_listing.columns = pd.MultiIndex.from_tuples([("Usuario","ID"),("Usuario","NIS"),("Mediana","consumo"),("Mediciones","de consumo"),("Consumo","crítico"),("Ubicación","Barrio"),("Ubicación","Localidad"),("Tipo","PASE"),("Programa","300 / No 300"),("Soluciones","registradas"),("Intervenciones","ejecutadas")])
    styled_listing = compact_listing.style.map(median_style, subset=[("Mediana","consumo")]).map(lambda value:"background-color:#FDE2E2;color:#9F1239;font-weight:bold" if value != "—" else "",subset=[("Consumo","crítico")]).format({("Mediana","consumo"): lambda value: fmt(value, 2), ("Mediciones","de consumo"): lambda value: fmt(value, 0)}, na_rep="—")
    # Posiciones Arrow: el índice oculto ocupa la posición cero.
    configs = {i:st.column_config.Column(width=width) for i,width in enumerate([125,90,75,75,80,140,115,75,85,155,155],start=1)}
    configs[3] = st.column_config.NumberColumn(width=75,help="Mediana de los consumos ≥100 del usuario dentro de la ventana seleccionada.",format="%.2f")
    configs[4] = st.column_config.NumberColumn(width=75,help="Cantidad de registros de consumo en la ventana seleccionada, incluidos los menores a 100.",format="%d")
    configs[5] = st.column_config.TextColumn(width=100,help="Indica si la mediana, el último consumo o ambos superan 1000. Exactamente 1000 no se considera crítico.")
    event = st.dataframe(styled_listing, hide_index=True, width="stretch", height=350, row_height=30, on_select="rerun", selection_mode="single-row", column_config=configs, key="user_table_" + str(pd.util.hash_pandas_object(listing[["Usua_ID"]]).sum()))
    st.download_button("Descargar selección · CSV", csv_bytes(listing), "edersa_usuarios.csv", "text/csv", key="download_users")
    selected_rows = event.selection.rows
    default_index = selected_rows[0] if selected_rows and selected_rows[0] < len(view) else 0
    options_ids = view.usuario_id.tolist()
    selected_id = st.selectbox("Ficha de usuario", options_ids, index=default_index, key="selected_user_" + str(default_index), help="La ficha muestra las mediciones de consumo dentro de la ventana seleccionada.")
    row = view.loc[view.usuario_id.eq(selected_id)].iloc[0]
    st.divider()
    st.markdown(f"### {selected_id}")
    a, median_card, e = st.columns([1,1.4,1])
    a.metric("Barrio", row.barrio)
    full_history = c.loc[c.usuario_id.eq(selected_id)].sort_values("periodo")
    trend_values = general_consumption_trend(full_history,full_history.periodo).dropna().tolist()
    critical = row.consumo_critico != "—"
    with median_card:
        with st.container(key="individual_median_kpi"):
            sparkline = trend_sparkline_svg(trend_values)
            st.markdown('<div style="background:white;border:1px solid #E1E8EF;padding:18px;border-radius:12px;min-height:108px;box-sizing:border-box" title="Mediana de consumos ≥100 en la ventana seleccionada. Tendencia de todo el historial: verde si sube, roja si baja; más intensa según la variación."><div style="color:#5B6E80;font-size:.82rem;margin-bottom:4px">Consumo mediano</div><div style="display:flex;align-items:center;justify-content:space-between;gap:10px"><span style="font-size:1.9rem;font-weight:600;white-space:nowrap">'+fmt(row.mediana_usuario,2)+'</span><div style="flex:0 0 38%;max-width:110px;height:44px">'+sparkline+'</div></div></div>',unsafe_allow_html=True)
            if critical:
                reasons = []
                if pd.notna(row.mediana_usuario) and row.mediana_usuario > 1000:
                    reasons.append(f"mediana {fmt(row.mediana_usuario,2)}")
                if pd.notna(row.consumo_ultimo) and row.consumo_ultimo > 1000:
                    reasons.append(f"último {fmt(row.consumo_ultimo,2)} ({label_period(latest)})")
                st.markdown('<div style="background:#FDE2E2;color:#9F1239;border-radius:8px;padding:7px 10px;font-size:.8rem"><b>Consumo crítico</b> · '+html.escape(" · ".join(reasons))+'</div>',unsafe_allow_html=True)
    e.metric("Mediciones de consumo", fmt(raw_selected_c.usuario_id.eq(selected_id).sum()))

    left, right = st.columns([1, 1.5])
    with left:
        st.markdown("#### Caracterización disponible")
        attrs = {"NIS": row.nis, "Gas":row.gas, "Localidad": row.localidad, "Departamento": row.departamento, "RENABAP": row.renabap or UNKNOWN, "Uso": row.uso, "Categoría · código": row.categoria, "Programa": row.programa_grupo, "Tipo PASE": row.tipo_pase}
        st.dataframe(pd.DataFrame(attrs.items(), columns=["Variable", "Valor"]), hide_index=True, width="stretch")
        if row.nis_repetido:
            st.warning("Este NIS aparece en más de un usuario. No se asume que representan hogares distintos.")
    with right:
        st.markdown("#### Historial de consumo")
        history = raw_selected_c.loc[raw_selected_c.usuario_id.eq(selected_id)].sort_values("periodo")
        if history.empty:
            st.info("Sin consumo disponible en esta ventana.")
        else:
            # Reindexar para que un período sin medición de consumo se vea como un hueco.
            complete = history.set_index("periodo")["consumo"].reindex(periods).rename_axis("periodo").reset_index()
            fig = individual_history_chart(complete,full_history)
            chart(fig, "individual_history",height=420,top_margin=75,plot_background="#EEF3F8")
            st.caption("La línea punteada muestra la tendencia lineal general, calculada con todo el historial del usuario y consumos ≥100. Se dibuja solo entre registros válidos, sin proyectar a futuro. No es un ajuste por estacionalidad. Con menos de dos registros aptos no se calcula.")
            st.caption("❄️ Banda blanca: invierno austral (21 de junio–20 de septiembre). ☀️ Banda amarilla: verano austral (21 de diciembre–20 de marzo). Cada punto corresponde al total de un bimestre completo.")
            complete["criterio"] = complete.consumo.map(lambda v: "Sin dato" if pd.isna(v) else "Excluido de estadísticas (<100)" if v < 100 else "Incluido en estadísticas")
            history_display = complete.assign(periodo=complete.periodo.map(label_period)).rename(columns={"periodo": "Período consumido", "consumo": "Consumo", "criterio": "Uso estadístico"})
            history_display["Consumo"] = history_display["Consumo"].map(lambda value: fmt(value, 2))
            st.dataframe(history_display, hide_index=True, width="stretch")
    st.markdown("#### Soluciones e intervenciones vinculadas")
    user_events = interventions.loc[interventions.usuario_id.eq(selected_id)].copy()
    if user_events.empty:
        st.info("No hay soluciones con vínculo confirmado para este usuario. Esto no acredita que no haya recibido intervenciones; los cruces pendientes se muestran en Intervenciones.")
    else:
        history_columns = {"fila_fuente": "Fila fuente", "solucion": "Solución / propuesta", "estado": "Estado", "fecha": "Fecha", "fecha_fuente": "Fecha o nota original", "barrio_fuente": "Barrio informado", "criterio": "Criterio del vínculo", "duplicado_exacto": "Duplicado exacto"}
        st.dataframe(user_events.sort_values("fecha", ascending=False, na_position="last")[list(history_columns)].rename(columns=history_columns), hide_index=True, width="stretch")
        st.caption("‘Ejecutada’ requiere ‘sí’ explícito en la fuente. Las propuestas no se cuentan como obras realizadas. Una fila puede describir más de una solución; el contador es de registros.")
    st.markdown("#### Encuesta residencial vinculada")
    household_surveys = dataset.surveys.records.loc[dataset.surveys.records.residencial & dataset.surveys.records.usuario_id.eq(selected_id)].sort_values("fecha_encuesta", ascending=False)
    if household_surveys.empty:
        st.caption("Sin encuesta residencial con NIS confirmado para este usuario. La caracterización territorial completa está disponible en Caracterización de hogares.")
    else:
        survey_row = household_surveys.iloc[0]
        render_linked_household(survey_row)
        st.caption(f"{len(household_surveys)} encuestas asociadas por NIS. Se muestra la más reciente; el suministro puede corresponder a más de una vivienda.")

elif section == "Comparar grupos":
    group_options = {"Tipo PASE del barrio": "tipo_pase", "PASE del barrio": "pase_barrio", "Ejecución de intervenciones · cualquier fecha": "intervencion_grupo", "Programa · 300 / No 300": "programa_grupo", "Registro de gas": "gas", "Localidad": "localidad", "Barrio": "barrio_etiqueta", "Categoría · código": "categoria"}
    chosen = st.selectbox("Comparar por", list(group_options), key="compare_groupby")
    group = group_options[chosen]
    available_groups = filtered.groupby(group).size().sort_values(ascending=False).index.tolist()
    available_groups = sorted(available_groups, key=lambda name: name == UNKNOWN)
    selection_key = f"compare_selection_{group}"
    if selection_key in st.session_state:
        st.session_state[selection_key] = [v for v in st.session_state[selection_key] if v in available_groups]
    selected_groups = st.multiselect("Grupos a contrastar", available_groups, default=available_groups[:6], max_selections=12, key=selection_key)
    st.caption("Podés contrastar hasta 12 grupos. Si hay muchos, se proponen inicialmente los seis con más usuarios.")
    compare_users = filtered.loc[filtered[group].isin(selected_groups)]
    if not selected_groups or not periods:
        st.info("Seleccioná al menos un grupo y un período para comparar sus consumos.")
    else:
        observations, stats = group_statistics(c, compare_users, group, periods)
        color_map = {name: COLORS[i] for i, name in enumerate(selected_groups)}
        st.markdown("#### Evolución del consumo de cada grupo")
        metric = st.radio("Estadístico de la evolución", ["Mediana", "Media"], horizontal=True, key="compare_metric")
        metric_col = "mediana" if metric == "Mediana" else "media"
        fig = px.line(stats, x="periodo", y=metric_col, color="grupo", markers=True, color_discrete_map=color_map, custom_data=["con_dato", "cobertura"], labels={"periodo": "Período consumido", metric_col: f"Consumo · {metric.lower()}", "grupo": chosen})
        fig.update_traces(connectgaps=False, hovertemplate="%{y:,.2f}<br>Usuarios ≥100: %{customdata[0]:,.0f}<br>Cobertura: %{customdata[1]:,.2f}%<extra>%{fullData.name}</extra>")
        ticks = periods[::max(1, (len(periods) + 5) // 6)]
        fig.update_xaxes(tickvals=ticks, ticktext=[label_period(p) for p in ticks], tickangle=-35)
        fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
        chart(fig, "group_evolution", height=440)
        st.caption("Cada línea representa un grupo. Los huecos indican ausencia de consumos ≥100; la composición observada puede cambiar entre períodos.")
        chosen_period = st.selectbox("Período consumido para comparar distribuciones", periods, index=len(periods)-1, format_func=label_period, key="compare_distribution_period")
        distribution_data = observations.loc[observations.periodo.eq(chosen_period)]
        st.markdown("#### Cómo se distribuyen los consumos dentro de cada grupo")
        if distribution_data.empty:
            st.info("Sin consumos ≥100 en este período para los grupos elegidos.")
        else:
            fig = px.box(distribution_data, x="grupo", y="consumo", color="grupo", color_discrete_map=color_map, points=False, labels={"grupo": chosen, "consumo": "Consumo registrado"})
            current_stats = stats.loc[stats.periodo.eq(chosen_period)]
            upper_fence = (current_stats.p75 + 1.5 * (current_stats.p75 - current_stats.p25)).max()
            if pd.notna(upper_fence):
                fig.update_yaxes(range=[0, upper_fence * 1.08])
            fig.update_layout(showlegend=False)
            chart(fig, "group_distribution", height=390)
            st.caption("La línea central es la mediana; la caja abarca P25–P75. Los bigotes alcanzan el último dato dentro de 1,5 veces el rango intercuartílico. El eje se ajusta a ese rango; los extremos no se dibujan individualmente, pero sí participan de las estadísticas.")
        reference_options = sorted(selected_groups, key=lambda name: name == UNKNOWN)
        reference = st.selectbox("Grupo de referencia para medir diferencias", reference_options, key=f"compare_reference_{group}")
        ref = stats.loc[stats.grupo.eq(reference), ["periodo", "mediana"]].rename(columns={"mediana": "mediana_referencia"})
        stats = stats.merge(ref, on="periodo", how="left", validate="many_to_one")
        stats["diferencia"] = stats.mediana - stats.mediana_referencia
        stats["diferencia_pct"] = stats.diferencia / stats.mediana_referencia * 100
        st.caption(f"Diferencias de mediana respecto a «{reference}», dentro de cada período. Positivo = mayor consumo que la referencia; negativo = menor.")
        renames = {"grupo": chosen, "periodo": "Período consumido", "usuarios": "Usuarios del grupo", "con_dato": "Usuarios ≥100", "mediana": "Mediana", "media": "Media", "p25": "P25", "p75": "P75", "desvio": "Desvío estándar", "cobertura": "Cobertura %", "diferencia": "Diferencia de mediana", "diferencia_pct": "Diferencia %", "mediana_referencia": "Mediana de referencia"}
        shown = stats.assign(periodo=stats.periodo.map(label_period)).rename(columns=renames)
        st.markdown(f"#### Diferencias entre grupos · {label_period(chosen_period)}")
        numeric_columns = ["Mediana", "Media", "P25", "P75", "Desvío estándar", "Cobertura %", "Diferencia de mediana", "Diferencia %", "Mediana de referencia"]
        shown_display = shown.copy()
        for column in numeric_columns:
            shown_display[column] = shown_display[column].map(lambda value: fmt(value, 2))
        for column in ["Usuarios del grupo", "Usuarios ≥100"]:
            shown_display[column] = shown_display[column].map(lambda value: fmt(value, 0))
        st.dataframe(shown_display.loc[stats.periodo.eq(chosen_period)], hide_index=True, width="stretch")
        with st.expander("Ver comparación en todos los períodos"):
            st.dataframe(shown_display, hide_index=True, width="stretch")
        st.download_button("Descargar comparación por grupo y período · CSV", csv_bytes(shown), "edersa_comparacion.csv", "text/csv")
    st.info("Comparación descriptiva. El grupo de intervenciones indica ejecución registrada en cualquier fecha, no necesariamente anterior al período consumido. No estima efecto causal; sin ejecución registrada no significa ausencia confirmada de intervención.")

elif section == "Intervenciones":
    confirmed = interventions.loc[interventions.vinculo.eq("Confirmado") & interventions.usuario_id.isin(filtered.usuario_id) & ~interventions.duplicado_exacto].copy()
    pending = interventions.loc[~interventions.vinculo.eq("Confirmado")].copy()
    a, b, d, e = st.columns(4)
    a.metric("Registros vinculados · selección", fmt(len(confirmed)))
    b.metric("Usuarios vinculados · selección", fmt(confirmed.usuario_id.nunique()))
    d.metric("Marcados ejecutados · selección", fmt(confirmed.estado.eq("Ejecutada").sum()))
    e.metric("Vínculos pendientes · toda la fuente", fmt(len(pending)))
    linked_tab, pending_tab = st.tabs(["Vinculadas a la selección", "Vínculos a revisar"])
    with linked_tab:
        st.caption("Se aplican los filtros de usuarios de la barra lateral. Solo se incluyen vínculos confirmados; los duplicados exactos se cuentan una vez.")
        chosen_type = st.multiselect("Solución / propuesta", sorted(confirmed.solucion.unique()), key="intervention_type")
        chosen_state = st.multiselect("Estado de la solución", sorted(confirmed.estado.unique()), key="intervention_state")
        if chosen_type:
            confirmed = confirmed.loc[confirmed.solucion.isin(chosen_type)]
        if chosen_state:
            confirmed = confirmed.loc[confirmed.estado.isin(chosen_state)]
        labels = {"registro_id": "Registro", "fila_fuente": "Fila fuente", "usuario_id": "Usua_ID", "solucion": "Solución / propuesta", "estado": "Estado", "fecha": "Fecha", "fecha_fuente": "Fecha o nota original", "barrio_fuente": "Barrio informado", "criterio": "Criterio del vínculo"}
        shown_events = confirmed.sort_values("fecha", ascending=False, na_position="last")[list(labels)].rename(columns=labels)
        st.dataframe(shown_events, hide_index=True, width="stretch")
        st.download_button("Descargar intervenciones vinculadas · CSV", csv_bytes(shown_events), "edersa_intervenciones.csv", "text/csv")
    with pending_tab:
        st.caption("Universo completo de soluciones pendientes de vincular. Estos registros no se asignan a los hogares ni entran en el filtro de ejecución. El barrio por sí solo no identifica a un usuario.")
        pending_status = st.multiselect("Situación del vínculo", sorted(pending.vinculo.unique()), key="intervention_pending_status")
        if pending_status:
            pending = pending.loc[pending.vinculo.isin(pending_status)]
        review_labels = {"fila_fuente": "Fila fuente", "solucion": "Solución / propuesta", "estado": "Estado", "barrio_fuente": "Barrio informado", "nis_fuente": "NIS informado", "persona": "Persona", "cuenta": "Cuenta", "sum_fuente": "Persona-Cuenta en sum", "vinculo": "Situación", "criterio": "Motivo", "candidatos": "Usuarios candidatos"}
        shown_pending = pending[list(review_labels)].rename(columns=review_labels)
        st.dataframe(shown_pending, hide_index=True, width="stretch")
        st.download_button("Descargar vínculos a revisar · CSV", csv_bytes(shown_pending), "edersa_intervenciones_revisar.csv", "text/csv")
    st.caption("NIS exacto tiene prioridad; se contrastan también Persona/Cuenta, el campo sum y el barrio. Los conflictos de identificadores quedan sin asignar. Las fechas no interpretables se conservan como nota original.")

else:
    st.markdown("#### Fuentes conectadas")
    st.caption("Los controles de esta sección corresponden al universo completo, independientemente de los filtros laterales.")
    source_table = pd.DataFrame([{"Fuente": s["title"], "Pestaña": s["worksheet"], "Filas": dataset.raw_counts[key], "Archivo": f"https://docs.google.com/spreadsheets/d/{s['id']}/edit"} for key, s in SOURCES.items()])
    st.dataframe(source_table, hide_index=True, width="stretch", column_config={"Archivo": st.column_config.LinkColumn("Abrir fuente", display_text="Abrir archivo")})
    st.markdown("#### Controles de vinculación y cobertura")
    st.dataframe(dataset.quality, hide_index=True, width="stretch")
    for title, issue in dataset.issues.items():
        if not issue.empty:
            with st.expander(f"{title} · {fmt(len(issue))} registros"):
                st.dataframe(issue, hide_index=True, width="stretch", height=280)
    st.markdown("#### Criterios de lectura")
    st.markdown("""
    - **Universo:** Usuarios general; una fila por Usua_ID. GPS no agrega nuevos usuarios.
    - **Vínculos:** Usua_ID une usuarios, GPS y consumos; RENABAP une usuarios y barrios. No se cruza por nombres ni por NIS.
    - **Períodos consumidos:** se toman los dos meses anteriores al mes facturado. feb-26 corresponde a dic-25 / ene-26. Se conserva el rótulo original en la base.
    - **Gas:** vacío significa sin información, no confirma acceso a gas.
    - **Programa:** se agrupa en 300 / No 300; un valor faltante permanece como sin información. Categoría conserva su código original.
    - **PASE:** clasificación del barrio; no prueba una intervención en cada suministro.
    - **Cobertura:** cada período informa cuántos usuarios tienen una medición de consumo. No se completan faltantes con ceros.
    - **Umbral estadístico:** se excluye cada medición de consumo menor a 100 de medias, medianas, percentiles, desvíos, totales y recuentos estadísticos. Los usuarios siguen en el padrón y esos valores se conservan en sus fichas.
    - **Dispersión:** P25–P75 contiene el 50% central; el desvío estándar es muestral y queda sin calcular cuando hay menos de dos mediciones de consumo.
    - **Intervenciones:** se lee únicamente A:L de CARGAR SOLUCIONES ACÁ del Excel de soluciones. Se conservan propuestas, ejecución, negativas y registros sin confirmar. Solo los vínculos confirmados se asignan al usuario.
    - **Cruces de soluciones:** NIS exacto, Persona/Cuenta y corroboración con barrio. Conflictos y vínculos probables quedan pendientes. Nunca se identifica a un hogar solo por barrio.
    - **Encuestas:** la caracterización incluye todas las encuestas residenciales completas seleccionadas, también las que no tienen vínculo confirmado con el padrón. Sus filtros territoriales son independientes de los filtros de usuarios.
    """)
    if mode == "Copia de prueba":
        st.info("Esta vista usa una copia de revisión. Para recibir cambios de las fuentes, configurá la cuenta de servicio y seleccioná ‘Google Sheets + Drive’. No cambia automáticamente al modo online.")

st.markdown(f'<div class="source-foot">EdERSA · Explorador de información · Lectura: {html.escape(str(fetched_at))} · {"Consulta a Sheets y Drive con caché de hasta 5 minutos; Actualizar datos fuerza una nueva lectura." if mode == "Google Sheets + Drive" else "Copia de prueba: los cambios en Drive no se sincronizan en este modo."}</div>', unsafe_allow_html=True)
