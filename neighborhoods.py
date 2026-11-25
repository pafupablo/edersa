"""Indicadores barriales: usuarios observados y brechas estimadas por separado."""
import html
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from model import MIN_CONSUMPTION, label_period

CRITICAL_MEDIAN = 1000


def neighborhood_indicators(users, consumption, neighborhoods):
    reference = consumption.periodo.max() if len(consumption) else pd.NaT
    history = {uid: dict(zip(group.periodo, group.consumo)) for uid, group in consumption.groupby("usuario_id")}
    records = []
    for user in users.itertuples():
        readings = history.get(user.usuario_id, {})
        latest = readings.get(reference, float("nan"))
        consecutive = 0
        current = reference
        while pd.notna(current) and current in readings and readings[current] < MIN_CONSUMPTION:
            consecutive += 1
            current -= pd.DateOffset(months=2)
        no_history = not readings
        persistent = consecutive * 2 > 3
        eligible_readings = [value for value in readings.values() if pd.notna(value) and value >= MIN_CONSUMPTION]
        user_median = pd.Series(eligible_readings, dtype="float64").median() if eligible_readings else float("nan")
        critical = pd.notna(user_median) and user_median > CRITICAL_MEDIAN
        latest_eligible = pd.notna(latest) and latest >= MIN_CONSUMPTION
        chart_latest_eligible = not critical and latest_eligible
        chart_persistent = not critical and persistent
        chart_no_history = not critical and no_history
        chart_other = not (critical or chart_latest_eligible or chart_persistent or chart_no_history)
        status = "Sin consumo en todo el historial" if no_history else "Consumo bajo persistente" if persistent else "Consumo ≥100 en el último período" if pd.notna(latest) and latest >= MIN_CONSUMPTION else "Otros usuarios registrados"
        records.append({"usuario_id": user.usuario_id, "nis": user.nis, "renabap": user.renabap, "barrio": user.barrio, "localidad": user.localidad, "consumo_ultimo": latest, "mediana_consumo_usuario": user_median, "usuario_critico": critical, "meses_bajos_consecutivos": consecutive * 2, "sin_historial": no_history, "bajo_persistente": persistent, "posible_irregularidad": no_history or persistent, "grafico_consumo_valido": chart_latest_eligible, "grafico_bajo_persistente": chart_persistent, "grafico_sin_historial": chart_no_history, "grafico_otros": chart_other, "estado": status})
    detail = pd.DataFrame(records, columns=["usuario_id","nis","renabap","barrio","localidad","consumo_ultimo","mediana_consumo_usuario","usuario_critico","meses_bajos_consecutivos","sin_historial","bajo_persistente","posible_irregularidad","grafico_consumo_valido","grafico_bajo_persistente","grafico_sin_historial","grafico_otros","estado"])
    table = neighborhoods.copy()
    table["etiqueta"] = table.barrio + " · " + table.localidad + " · " + table.renabap
    aggregation = detail.groupby("renabap").agg(usuarios_registrados=("usuario_id","nunique"), sin_historial=("sin_historial","sum"), bajo_persistente=("bajo_persistente","sum"), posibles_irregulares=("posible_irregularidad","sum"), usuarios_criticos=("usuario_critico","sum"), usuarios_estadistica_grafico=("grafico_consumo_valido","sum"), bajo_persistente_grafico=("grafico_bajo_persistente","sum"), sin_historial_grafico=("grafico_sin_historial","sum"), otros_registrados_grafico=("grafico_otros","sum"))
    table = table.merge(aggregation,on="renabap",how="left",validate="one_to_one")
    for column in ("usuarios_registrados","sin_historial","bajo_persistente","posibles_irregulares","usuarios_criticos","usuarios_estadistica_grafico","bajo_persistente_grafico","sin_historial_grafico","otros_registrados_grafico"):
        table[column] = table[column].fillna(0).astype(int)
    observed = detail.loc[detail.consumo_ultimo.notna()].groupby("renabap").usuario_id.nunique()
    eligible = detail.loc[detail.consumo_ultimo.ge(MIN_CONSUMPTION)].groupby("renabap").agg(usuarios_estadistica=("usuario_id","nunique"), mediana_consumo=("consumo_ultimo","median"))
    table = table.merge(eligible,on="renabap",how="left",validate="one_to_one")
    table["usuarios_estadistica"] = table.usuarios_estadistica.fillna(0).astype(int)
    table["consumidores_con_registro"] = table.renabap.map(observed).fillna(0).astype(int)
    table["sin_dato_ultimo_con_historia"] = table.usuarios_registrados - table.consumidores_con_registro - table.sin_historial
    table["otros_registrados"] = table.usuarios_registrados - table.usuarios_estadistica - table.posibles_irregulares
    table["incidencia_pct"] = table.posibles_irregulares / table.usuarios_registrados.replace(0,float("nan")) * 100
    estimates = table.viviendas_estimadas.where(table.viviendas_estimadas.ge(0))
    table["sin_medidor_estimado"] = (estimates - table.usuarios_registrados).clip(lower=0)
    table["brecha_sin_medidor_pct"] = table.sin_medidor_estimado / estimates.where(estimates.gt(0)) * 100
    table["usuarios_sobre_estimacion"] = (table.usuarios_registrados - estimates).clip(lower=0)
    table["periodo_consumido"] = label_period(reference)
    return table, detail, reference


def fmt(value, digits=0):
    if pd.isna(value):
        return "—"
    return f"{value:,.{digits}f}".replace(",","_").replace(".",",").replace("_",".")


def plot(fig, key, height=530):
    fig.update_layout(template="plotly_white",height=height,margin=dict(l=8,r=100,t=200,b=40),font=dict(color="#36506B",size=11),paper_bgcolor="white",plot_bgcolor="white",legend=dict(orientation="h",y=1.16,yanchor="bottom",x=0,font=dict(size=10)),legend_title_text="",separators=",.")
    st.plotly_chart(fig,key=key,width="stretch",config={"displaylogo":False})


def neighborhood_comparison_chart(visible):
    """Shared barrio rows, two percentage panels and a final estimate column."""
    visible = visible.copy()
    visible["etiqueta"] = [f"{html.escape(str(row.barrio))} ({html.escape(str(row.renabap))})<br>{html.escape(str(row.localidad))}" for row in visible.itertuples()]
    fig = make_subplots(rows=1,cols=2,shared_yaxes=True,horizontal_spacing=.07,
                        subplot_titles=("Tipo de consumo", "Acceso al servicio"))
    fig.update_annotations(font_size=12)
    categories = [
        ("usuarios_estadistica_grafico","Consumo ≥100","#30598F"),
        ("otros_registrados_grafico","Bajo aislado / sin dato reciente","#CFD9E6"),
        ("bajo_persistente_grafico","Consumo <100 por ≥4 meses","#FFC600"),
        ("sin_historial_grafico","Sin registros de consumo","#8F6A6C"),
        ("usuarios_criticos","Crítico · mediana >1.000","#D13C42"),
    ]
    for column,label,color in categories:
        shares = visible[column] / visible.usuarios_registrados.replace(0,float("nan")) * 100
        fig.add_trace(go.Bar(y=visible.etiqueta,x=shares,name=label,
            orientation="h",marker_color=color,legendgroup="consumo",text=visible[column].where(visible[column].gt(0),""),textposition="inside",
            customdata=list(zip(visible[column],visible.usuarios_registrados)),hovertemplate=f"%{{y}}<br>{label}: %{{customdata[0]:,.0f}} usuarios<br>%{{x:,.2f}}% de %{{customdata[1]:,.0f}} registrados<extra></extra>"),row=1,col=1)
    estimates = visible.viviendas_estimadas.where(visible.viviendas_estimadas.gt(0))
    covered = visible.usuarios_registrados.clip(upper=estimates)
    for column,label,color in [("usuarios_registrados","Usuarios registrados","#91B2D6"),("sin_medidor_estimado","Sin servicio · estimación","#FFC600")]:
        shares = (covered if column == "usuarios_registrados" else visible[column]) / estimates * 100
        custom = list(zip(visible[column],visible.viviendas_estimadas,visible.usuarios_registrados))
        fig.add_trace(go.Bar(y=visible.etiqueta,x=shares,name=label,
            orientation="h",marker_color=color,legendgroup="servicio",text=visible[column].where(visible[column].gt(0),""),textposition="inside",
            customdata=custom,hovertemplate=f"%{{y}}<br>{label}: %{{customdata[0]:,.0f}}<br>Cobertura estimada: %{{x:,.2f}}%<br>Familias estimadas (base viviendas): %{{customdata[1]:,.0f}}<br>Usuarios registrados: %{{customdata[2]:,.0f}}<extra></extra>"),row=1,col=2)
    for row in visible.itertuples():
        fig.add_annotation(x=1.04,xref="x2 domain",y=row.etiqueta,yref="y2",text=fmt(row.viviendas_estimadas),showarrow=False,xanchor="left",font=dict(size=11,color="#30598F"))
    fig.add_annotation(x=1.04,xref="x2 domain",y=1.04,yref="paper",text="Familias<br>estimadas",showarrow=False,xanchor="left",yanchor="bottom",font=dict(size=11,color="#30598F"))
    fig.update_layout(barmode="stack",bargap=.28)
    fig.update_xaxes(title_text="Usuarios (%)",range=[0,100],ticksuffix="%",row=1,col=1)
    fig.update_xaxes(title_text="Cobertura estimada (%)",range=[0,100],ticksuffix="%",row=1,col=2)
    fig.update_yaxes(categoryorder="array",categoryarray=visible.etiqueta.tolist())
    return fig


def render_neighborhoods(dataset, selected_neighborhoods, csv_bytes):
    table, detail, reference = neighborhood_indicators(dataset.users,dataset.consumption,selected_neighborhoods)
    st.markdown("""<style>
    .barrio-hero{background:#30598F;color:white;border-top:5px solid #FFC600;border-radius:16px;padding:25px 30px;margin:0 0 20px}
    .barrio-hero h1{color:white;font-size:2.1rem;margin:0 0 12px}
    .barrio-hero p{color:#E7EFF8;line-height:1.6;margin:0}
    .barrio-note{background:#FFF6D5;border-left:4px solid #FFC600;border-radius:0 10px 10px 0;padding:16px 20px;margin:20px 0;color:#624C10;line-height:1.6}
    </style>""",unsafe_allow_html=True)
    st.markdown('<div class="barrio-hero"><h1>Barrios: cobertura e incidencia</h1><p>Usuarios registrados, señales de consumo y una estimación de la brecha de medición. Cada indicador conserva su unidad y su denominador.</p></div>',unsafe_allow_html=True)
    if table.empty:
        st.info("No hay barrios para la selección territorial.")
        return
    scoped = detail.loc[detail.renabap.isin(table.renabap)]
    registered = int(table.usuarios_registrados.sum())
    flagged = int(table.posibles_irregulares.sum())
    median = scoped.loc[scoped.consumo_ultimo.ge(MIN_CONSUMPTION),"consumo_ultimo"].median()
    a,b,c,d = st.columns(4)
    a.metric("Usuarios registrados",fmt(registered),help="Usua_ID únicos del padrón, con o sin registros de consumo.")
    b.metric("Posibles colgados",fmt(flagged),delta=f"{fmt(flagged / registered * 100 if registered else float('nan'),2)}% de usuarios",delta_color="off",help="Criterio de datos: consumo <100 durante al menos dos bimestres consecutivos o sin registros en todo el historial. No constata conexión irregular.")
    gap_sum = table.sin_medidor_estimado.sum(min_count=1)
    estimated_sum = table.viviendas_estimadas.sum(min_count=1)
    c.metric("Sin medidor · estimación",fmt(gap_sum),delta=f"{fmt(gap_sum / estimated_sum * 100 if estimated_sum > 0 else float('nan'),2)}% de viviendas estimadas",delta_color="off",help="Suma por barrio de máximo(viviendas estimadas − usuarios registrados, 0). No es una observación de medidores.")
    d.metric("Mediana de consumo",fmt(median,2),help="Último período consumido; solo usuarios con consumo ≥100. No es el promedio de las medianas de los barrios.")
    st.caption(f"Referencia de consumo: {label_period(reference)} · {fmt(len(table))} barrios · Incidencia de casos a revisar: {fmt(flagged / registered * 100 if registered else float('nan'),2)}% de los usuarios registrados.")
    st.markdown('<div class="barrio-note"><b>Dos lecturas diferentes:</b> los casos a revisar se cuentan entre usuarios registrados; la cantidad sin medidor es una brecha estimada de viviendas frente al padrón. Tener consumo bajo o ausente no confirma una conexión irregular.</div>',unsafe_allow_html=True)

    st.markdown("### Consumo y acceso al servicio, barrio por barrio")
    st.caption("Una fila por barrio: ambos paneles van de 0 a 100%. A la izquierda, tipos de consumo entre usuarios registrados; en rojo, usuarios críticos cuya mediana histórica de consumos válidos es mayor a 1.000. A la derecha, acceso al servicio sobre familias estimadas. Los números dentro de las barras son cantidades. Al final de cada fila figura el total de familias estimadas, usando el dato de viviendas de la fuente.")
    order = st.radio("Ordenar barrios por",["Cantidad de casos a revisar","Porcentaje de usuarios","Viviendas sin servicio estimadas","Usuarios registrados"],horizontal=True,key="barrio_ranking")
    sort_column = {"Cantidad de casos a revisar":"posibles_irregulares","Porcentaje de usuarios":"incidencia_pct","Viviendas sin servicio estimadas":"sin_medidor_estimado","Usuarios registrados":"usuarios_registrados"}[order]
    ordered = table.sort_values([sort_column,"renabap"],ascending=[False,True],na_position="last")
    page_size = 15
    signature = (sort_column,tuple(ordered.renabap))
    if st.session_state.get("barrio_chart_selection") != signature:
        st.session_state.barrio_chart_selection = signature
        st.session_state.barrio_chart_page = 0
    total_pages = max(1,(len(ordered)+page_size-1)//page_size)
    page = min(st.session_state.get("barrio_chart_page",0),total_pages-1)
    st.session_state.barrio_chart_page = page
    def move_page(step):
        st.session_state.barrio_chart_page = max(0,min(total_pages-1,st.session_state.barrio_chart_page+step))
    first,previous,status,following,last = st.columns([1,1,2,1,1])
    first.button("⇤ Primero",key="barrio_chart_first",disabled=page==0,on_click=move_page,args=(-total_pages,),width="stretch")
    previous.button("← Anterior",key="barrio_chart_previous",disabled=page==0,on_click=move_page,args=(-1,),width="stretch")
    start = page*page_size
    stop = min(start+page_size,len(ordered))
    status.markdown(f"<div style='text-align:center;padding:7px 0;color:#30598F'>Barrios <b>{start+1}–{stop}</b> de <b>{len(ordered)}</b> · Página {page+1}/{total_pages}</div>",unsafe_allow_html=True)
    following.button("Siguiente →",key="barrio_chart_next",disabled=page==total_pages-1,on_click=move_page,args=(1,),width="stretch")
    last.button("Último ⇥",key="barrio_chart_last",disabled=page==total_pages-1,on_click=move_page,args=(total_pages,),width="stretch")
    visible = ordered.iloc[start:stop].iloc[::-1]
    if visible.empty:
        st.info("No hay barrios para comparar.")
    else:
        fig = neighborhood_comparison_chart(visible)
        plot(fig,"barrio_consumption_and_service",max(560,len(visible)*48+300))
        st.caption("Recorré todos los barrios con las flechas, de a 15 y en el mismo orden en ambos paneles. En rojo se muestran los usuarios con mediana histórica mayor a 1.000, calculada sobre sus consumos ≥100. Cada usuario aparece en una sola categoría. ‘Sin registros de consumo’ significa que existe en el padrón pero no tiene consumo en todo el historial. El gris incluye consumo bajo aislado o ausencia de dato reciente con historial previo.")
    st.caption("Familias estimadas: se usa ‘Viviendas Estimadas’ como aproximación, con un usuario por vivienda. Sin servicio estimado = máximo(viviendas estimadas − usuarios registrados, 0). Si el padrón supera la estimación, la cobertura se muestra en 100% y se conserva la cantidad real de usuarios. Sin estimación válida no se dibuja la barra de acceso. No es una verificación territorial del servicio.")

    st.markdown("### Ficha del barrio")
    names = table.set_index("renabap").etiqueta.to_dict()
    chosen = st.selectbox("Barrio",table.renabap.tolist(),format_func=lambda value:names[value],key="barrio_detail")
    row = table.loc[table.renabap.eq(chosen)].iloc[0]
    a,b,c,d = st.columns(4)
    a.metric("Consumidores con registro · último período",fmt(row.consumidores_con_registro))
    b.metric("Usuarios críticos · mediana >1.000",fmt(row.usuarios_criticos),help="Mediana histórica por usuario calculada con sus consumos ≥100.")
    c.metric("Consumo bajo persistente",fmt(row.bajo_persistente))
    d.metric("Sin registros en todo el historial",fmt(row.sin_historial))
    a,b,c = st.columns(3)
    a.metric("Mediana de consumo · ≥100",fmt(row.mediana_consumo,2))
    b.metric("Incidencia de casos a revisar",fmt(row.incidencia_pct,2)+"%" if pd.notna(row.incidencia_pct) else "Sin base")
    c.metric("Brecha sin medidor · estimada",fmt(row.sin_medidor_estimado))
    st.caption(f"{fmt(row.usuarios_registrados)} usuarios registrados · {fmt(row.viviendas_estimadas)} viviendas estimadas · {fmt(row.usuarios_estadistica)} usuarios incluidos en la mediana · Tipo PASE: {row.tipo_pase}.")

    labels = {"renabap":"RENABAP","barrio":"Barrio","localidad":"Localidad","tipo_pase":"Tipo PASE","periodo_consumido":"Período consumido de referencia","viviendas_estimadas":"Viviendas estimadas · fuente","usuarios_registrados":"Usuarios registrados","consumidores_con_registro":"Usuarios con registro · último período","usuarios_estadistica":"Usuarios con consumo ≥100 · último período","mediana_consumo":"Mediana de consumo · ≥100","usuarios_criticos":"Usuarios críticos · mediana histórica >1.000","bajo_persistente":"Consumo <100 persistente · usuarios","sin_historial":"Sin registros en todo el historial · usuarios","posibles_irregulares":"Casos a revisar · usuarios","incidencia_pct":"Incidencia · % de usuarios registrados","sin_medidor_estimado":"Sin medidor · brecha estimada","brecha_sin_medidor_pct":"Brecha · % de viviendas estimadas","sin_dato_ultimo_con_historia":"Sin dato último período · con historial","usuarios_sobre_estimacion":"Usuarios por encima de viviendas estimadas"}
    export = table[list(labels)].rename(columns=labels)
    st.markdown("### Todos los barrios de la selección")
    st.dataframe(export,hide_index=True,width="stretch",column_config={"Incidencia · % de usuarios registrados":st.column_config.ProgressColumn(format="%.2f%%",min_value=0,max_value=100),"Brecha · % de viviendas estimadas":st.column_config.ProgressColumn(format="%.2f%%",min_value=0,max_value=100),"Mediana de consumo · ≥100":st.column_config.NumberColumn(format="%.2f")})
    st.download_button("Descargar indicadores por barrio · CSV",csv_bytes(export),"edersa_indicadores_barrios.csv","text/csv")
    cases = scoped.loc[scoped.posible_irregularidad].copy()
    with st.expander("Ver usuarios que cumplen el criterio de revisión"):
        st.dataframe(cases,hide_index=True,width="stretch")
        st.download_button("Descargar usuarios a revisar · CSV",csv_bytes(cases),"edersa_usuarios_barrios_revisar.csv","text/csv")
    with st.expander("Cómo se calcula cada indicador"):
        st.markdown("""
        - **Usuarios registrados:** identificadores Usua_ID distintos en el padrón. No equivale necesariamente a familias o viviendas.
        - **Consumo bajo persistente:** menos de 100 en al menos dos bimestres consecutivos, terminando en el último período disponible. Son cuatro meses; un período faltante corta la secuencia.
        - **Sin consumo:** sin registros válidos en todo el historial disponible. Tener historial y no tener dato en el último período se informa aparte.
        - **Casos a revisar:** unión sin duplicados de bajo consumo persistente y ausencia de historial. Es el criterio solicitado para identificar posibles ‘colgados’, no una constatación de conexión irregular.
        - **Usuarios críticos:** usuarios cuya mediana histórica individual es mayor a 1.000, calculada solo con sus consumos ≥100. En el gráfico se muestran en rojo y se priorizan como una categoría exclusiva, para que cada usuario se cuente una sola vez.
        - **Sin medidor estimado:** máximo(viviendas estimadas − usuarios registrados, 0), barrio por barrio. Los datos no permiten contar medidores ausentes de forma directa.
        - **Mediana:** consumo del último bimestre entre usuarios con valor ≥100. Los valores bajos se usan para las incidencias, pero no para la mediana.
        """)
    unknown = (~dataset.users.renabap.isin(dataset.neighborhoods.renabap)).sum()
    st.caption(f"Usuarios sin barrio vinculado en el padrón completo: {fmt(unknown)}. No se distribuyen entre barrios por suposición. Los indicadores se refieren al último bimestre disponible, no a una verificación territorial actual.")
