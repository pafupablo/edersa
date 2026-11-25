"""Relato visual de las encuestas, con bases visibles y sin índices inventados."""
import html
import textwrap
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from surveys import PROBLEMS, binary_stats, yes_no

BLUE = "#30598F"
YELLOW = "#FFC600"
LIGHT = "#91B2D6"
RED = "#B7474C"
GRAY = "#CBD5E1"


def fmt(value, digits=0):
    if pd.isna(value):
        return "—"
    return f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def pct(value):
    return fmt(value, 2) + "%" if pd.notna(value) else "Sin base"


def plot(fig, key, height=310):
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=8, r=26, t=15, b=25), font=dict(family="Arial", color="#36506B", size=12), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend_title_text="", legend=dict(orientation="h", y=1.12, x=0), separators=",.")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#E6EDF2")
    st.plotly_chart(fig, key=key, width="stretch", config={"displaylogo": False})


def section(number, title, subtitle):
    st.markdown(f'<div class="survey-section"><span>{number}</span><div><h2>{html.escape(title)}</h2><p>{html.escape(subtitle)}</p></div></div>', unsafe_allow_html=True)


def cards(items, class_name="survey-cards"):
    content = "".join(f'<div class="survey-card"><div class="survey-label">{html.escape(label)}</div><div class="survey-value">{html.escape(value)}</div><p>{html.escape(note)}</p></div>' for label, value, note in items)
    st.markdown(f'<div class="{class_name}">{content}</div>', unsafe_allow_html=True)


def linked_household_html(row):
    """Residential survey facts, with explicit unknowns and counted equipment."""
    def value(field):
        raw = row.get(field)
        return "Sin dato" if raw is None or pd.isna(raw) or str(raw).strip()=="" else str(raw).replace("_"," ").strip()
    def binary(field):
        answer = yes_no(row.get(field))
        return "Sí" if answer is True else "No" if answer is False else "Sin dato"
    def number(field):
        return fmt(pd.to_numeric(row.get(field),errors="coerce"))
    def card(label, content, note="", icons="", tone=""):
        return f'<div class="linked-card {tone}"><div class="linked-label">{html.escape(label)}</div><div class="linked-value">{html.escape(str(content))} <span class="linked-icons" aria-hidden="true">{html.escape(icons)}</span></div><p>{html.escape(note)}</p></div>'
    def equipment(label, quantity_field, icon, presence_field=None):
        quantity = pd.to_numeric(row.get(quantity_field),errors="coerce")
        presence = yes_no(row.get(presence_field)) if presence_field else None
        if pd.notna(quantity) and quantity>=0 and float(quantity).is_integer():
            count = int(quantity)
            icons = " ".join([icon]*min(count,12)) + (f" +{count-12}" if count>12 else "")
            note = "Un ícono por equipo declarado." if count else "No tiene equipos declarados."
            if presence is False and count>0 or presence is True and count==0:
                note = "Revisar: la cantidad y la respuesta de presencia no coinciden."
            return card(label,str(count),note,icons)
        if presence is False:
            return card(label,"0","No tiene, según la encuesta.")
        return card(label,"Tiene" if presence is True else "Sin dato","Cantidad no informada.",icon if presence is True else "")
    def presence(label,field,icon):
        answer = binary(field)
        return card(label,answer,"Presencia declarada; la encuesta no releva cantidad.",icon if answer=="Sí" else "")

    ratio = pd.to_numeric(row.get("personas_por_ambiente"),errors="coerce")
    crowded = pd.notna(ratio) and ratio>3
    crowd_label = "Hacinamiento crítico" if crowded else "Sin hacinamiento crítico" if pd.notna(ratio) else "Sin dato"
    occupancy = '<div class="linked-grid">'+''.join([
        card("Personas en el hogar",number("personas_cantidad"),f'Mayores: {number("personas_mayores_edad_cantidad")} · Menores: {number("menores_derivados")}'),
        card("Superficie construida",number("superficie_construida")+" m²" if value("superficie_construida")!="Sin dato" else "Sin dato"),
        card("Ambientes",number("ambientes_totales"),"Se cuentan todos los ambientes, no solo dormitorios."),
        card("Personas por ambiente",fmt(ratio,2),crowd_label+" · crítico si supera 3 personas/ambiente.",tone="linked-alert" if crowded else ""),
        card("Estado general",value("vivienda_estado_general")),
        card("Familias declaradas",number("familias_cantidad")),
    ])+'</div>'
    water = binary("energia_calefaccion_agua/Electricidad")
    if water=="Sin dato" and "electricidad" in value("energia_calefaccion_agua").casefold():
        water="Sí"
    equipment_cards = '<div class="linked-grid">'+''.join([
        equipment("Aires acondicionados","aire_acondicionado_cantidad","❄️","aire_acondicionado_hay"),
        equipment("Estufas / calefactores eléctricos","calefactor_electrico_cantidad","🔥"),
        presence("Estufa a gas","estufa_gas","🔥"),
        presence("Estufa a leña","estufa_lena","🪵"),
        card("Agua caliente con electricidad",water,"Fuentes declaradas: "+value("energia_calefaccion_agua"),"⚡" if water=="Sí" else ""),
        card("Equipos para agua caliente",f'Termotanque eléctrico: {binary("termotanque_electrico_hay")}',f'Ducha eléctrica: {binary("ducha_electrica")} · Termotanque a gas: {binary("termotanque_gas_hay")}'),
    ])+'</div>'
    materials = '<div class="linked-grid linked-materials">'+''.join(card(label,value(field)) for label,field in [
        ("Techo exterior","vivienda_techo_exterior_material"),
        ("Techo interior · componentes","vivienda_techo_interior_material"),
        ("Pared externa","vivienda_pared_material"),
        ("Piso","vivienda_piso_material"),
    ])+'</div>'
    board = value("tablero_hay")
    board_key = board.casefold()
    disconnector = "Sí, declarado" if "disyuntor" in board_key else "No, solo térmicas" if "solo" in board_key and ("termica" in board_key or "térmica" in board_key) else "No, sin tablero" if board_key=="no" else "Tablero completo declarado" if "completo" in board_key else "Sin dato específico"
    protections = '<div class="linked-grid">'+''.join([
        card("Disyuntor",disconnector,"El formulario describe el tablero; no releva cantidad de disyuntores."),
        card("Tablero eléctrico",board),
        card("Puesta a tierra",binary("puesta_tierra_hay")),
        card("Cortes de electricidad",value("cortes_electricidad")),
    ])+'</div>'
    problem_cards = []
    for field,label in PROBLEMS.items():
        answer = binary(field)
        problem_cards.append(card(label,answer,tone="linked-alert" if answer=="Sí" else ""))
    problems = '<div class="linked-grid">'+''.join(problem_cards)+'</div>'
    date = row.get("fecha_encuesta")
    date_label = pd.Timestamp(date).strftime("%d/%m/%Y") if pd.notna(date) else "Sin fecha"
    return '<div class="linked-household"><div class="linked-heading">Encuesta del '+html.escape(date_label)+'</div><h4>El hogar y sus espacios</h4>'+occupancy+'<h4>Climatización y agua caliente</h4>'+equipment_cards+'<h4>Materialidad de la vivienda</h4>'+materials+'<h4>Protecciones e instalación eléctrica</h4>'+protections+'<h4>Problemas eléctricos declarados</h4>'+problems+'</div>'


def render_linked_household(row):
    st.markdown('''<style>
    .linked-household{margin:8px 0 18px;color:#234B7B}
    .linked-household h4{margin:17px 0 7px;font-size:.95rem}
    .linked-heading{border-left:4px solid #FFC600;background:#EAF0F8;padding:8px 12px;border-radius:0 6px 6px 0;font-size:.85rem;font-weight:600}
    .linked-grid{border:1px solid #DFE7F0;border-radius:8px;overflow:hidden}
    .linked-card{display:grid;grid-template-columns:minmax(135px,.95fr) minmax(90px,.9fr) minmax(100px,1.5fr);align-items:center;gap:8px;border-bottom:1px solid #E9EEF4;background:white;padding:8px 12px;overflow-wrap:anywhere}
    .linked-card:last-child{border-bottom:0}
    .linked-label{color:#526C84;font-size:.8rem}
    .linked-value{font-weight:600;font-size:.88rem;line-height:1.4}
    .linked-card p{font-size:.72rem;color:#64798B;margin:0;line-height:1.4}
    .linked-icons{font-size:1.05rem;word-spacing:2px;white-space:normal}
    .linked-alert{background:#FFF0F0}.linked-alert .linked-value{color:#A62D35}
    @media(max-width:520px){.linked-card{grid-template-columns:1fr 1fr;gap:3px 8px}.linked-card p{grid-column:2}.linked-card p:empty{display:none}}
    </style>''',unsafe_allow_html=True)
    st.markdown(linked_household_html(row),unsafe_allow_html=True)


def categorical(values, title, key, aliases=None, order=None, height=290, donut=False):
    st.markdown(f"#### {title}")
    clean = values.dropna().astype(str).str.strip()
    clean = clean.loc[clean.ne("")]
    if clean.empty:
        st.info("Sin respuestas disponibles para esta selección.")
        return
    counts = clean.value_counts()
    if order:
        counts = counts.reindex([v for v in order if v in counts.index] + [v for v in counts.index if v not in order])
    data = counts.rename_axis("original").rename("n").reset_index()
    data["porcentaje"] = data.n / len(clean) * 100
    data["etiqueta"] = data.original.map(lambda value: (aliases or {}).get(value, value))
    data["etiqueta"] = data.etiqueta.map(lambda value: "<br>".join(textwrap.wrap(value, 27)))
    data["texto"] = data.apply(lambda r: f"{pct(r.porcentaje)} · {fmt(r.n)}", axis=1)
    palette = [BLUE, YELLOW, LIGHT, "#637693", "#D7A94A", GRAY]
    colors = [{"Bueno": BLUE, "Regular": YELLOW, "Malo": RED}.get(value, palette[i % len(palette)]) for i, value in enumerate(data.original)]
    if donut:
        fig = go.Figure(go.Pie(labels=data.etiqueta, values=data.n, hole=.66, marker=dict(colors=colors, line=dict(color="white", width=2)), texttemplate="%{percent:.2%}", textposition="inside", hovertemplate="%{label}<br>%{value:,.0f} respuestas · %{percent:.2%}<extra></extra>"))
        fig.update_layout(annotations=[dict(text=f"<b>{fmt(len(clean))}</b><br>respuestas", x=.5, y=.5, showarrow=False, font_size=18)], legend=dict(orientation="h", y=-.12, x=0))
        # Mantener la leyenda debajo del anillo, con etiquetas completas.
        fig.update_layout(template="plotly_white", height=height, margin=dict(l=8,r=8,t=10,b=80), font=dict(color="#36506B", size=11), paper_bgcolor="white")
        st.plotly_chart(fig, key=key, width="stretch", config={"displaylogo": False})
        st.caption(f"Base: {fmt(len(clean))} respuestas · {fmt(len(values) - len(clean))} sin dato.")
        return
    fig = px.bar(data, y="etiqueta", x="porcentaje", orientation="h", text="texto", custom_data=["n", "original"], color_discrete_sequence=[BLUE], labels={"etiqueta": "", "porcentaje": "% de respuestas"})
    fig.update_traces(marker_color=colors, textposition="outside", cliponaxis=False, hovertemplate="%{customdata[1]}<br>%{customdata[0]:,.0f} respuestas · %{x:,.2f}%<extra></extra>")
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(range=[0, min(115, max(20, float(data.porcentaje.max()) * 1.38))])
    plot(fig, key, height)
    st.caption(f"Base: {fmt(len(clean))} respuestas · {fmt(len(values) - len(clean))} sin dato.")


def rates(items, title, key, height=310, kind="stacked"):
    st.markdown(f"#### {title}")
    data = pd.DataFrame([{"indicador": label, **stats} for label, stats in items])
    data = data.loc[data.base.gt(0)].sort_values("pct")
    if data.empty:
        st.info("Sin respuestas definidas en esta selección.")
        return
    if kind == "stacked":
        fig = go.Figure()
        for name, color in [("Sí", BLUE), ("No", "#DFE8F3"), ("Sin dato / NSNC", "#B8C0CD")]:
            counts = data.n if name == "Sí" else data.base - data.n if name == "No" else data.missing
            total = data.base + data.missing
            shares = counts / total * 100
            texts = [f"{pct(p)}<br>{fmt(n)}" if p >= 8 else "" for p, n in zip(shares, counts)]
            custom = list(zip(counts, total, data["pct"]))
            fig.add_trace(go.Bar(name=name, y=data.indicador, x=shares, orientation="h", marker_color=color, text=texts, textposition="inside", insidetextfont=dict(color="white" if name == "Sí" else "#234B7B", size=12), customdata=custom, hovertemplate=f"%{{y}}<br>{name}: %{{customdata[0]:,.0f}} de %{{customdata[1]:,.0f}} encuestas · %{{x:,.2f}}%<br>Sí entre respuestas definidas: %{{customdata[2]:,.2f}}%<extra></extra>"))
        fig.update_layout(barmode="stack", bargap=.3)
        fig.update_xaxes(title="% de las encuestas seleccionadas", range=[0,100], ticksuffix="%", dtick=25)
        plot(fig, key, height)
        st.caption("Azul: presencia o uso declarado. Gris claro: no. Gris: sin dato/NSNC. Se muestran cantidades y porcentajes del total seleccionado; el cursor agrega la tasa entre respuestas definidas.")
        return
    data["texto"] = data.apply(lambda r: f"{pct(r['pct'])} · {fmt(r['n'])}", axis=1)
    fig = px.bar(data, x="pct", y="indicador", orientation="h", text="texto", custom_data=["n", "base", "missing"], color_discrete_sequence=[BLUE], labels={"pct": "% de respuestas definidas", "indicador": ""})
    fig.update_traces(textposition="outside", cliponaxis=False, hovertemplate="%{y}<br>%{customdata[0]:,.0f} de %{customdata[1]:,.0f} · %{x:,.2f}%<br>Sin respuesta definida: %{customdata[2]:,.0f}<extra></extra>")
    fig.update_traces(marker_color=[RED if value in ("Descargas a personas", "Principio de incendio eléctrico") else BLUE for value in data.indicador])
    fig.update_xaxes(range=[0, max(15, float(data["pct"].max()) * 1.45)])
    plot(fig, key, height)
    st.caption("Cada barra usa su propia base de respuestas definidas. Pasá el cursor para ver numerador, base y faltantes.")


def age_pyramid(people):
    data = people.loc[people.edad.notna() & people.genero.isin(["Femenino", "Masculino", "Otro"])].copy()
    if data.empty:
        st.info("Sin edades y géneros consignados en esta selección.")
        return
    labels = ["Hasta 17", "18–35", "36–50", "51–65", "66–79", "80 o más"]
    data["edad_grupo"] = pd.cut(data.edad, [-1,17,35,50,65,79,115], labels=labels)
    fig = go.Figure()
    peak = 0
    for gender, color, sign in [("Femenino", BLUE, -1), ("Masculino", YELLOW, 1), ("Otro", "#7B8AA8", 1)]:
        counts = data.loc[data.genero.eq(gender)].edad_grupo.value_counts().reindex(labels, fill_value=0)
        shares = counts / len(data) * 100
        peak = max(peak, float(shares.max()))
        fig.add_trace(go.Bar(name=gender, y=labels, x=shares * sign, orientation="h", marker_color=color, customdata=list(zip(counts, shares)), text=[f"{fmt(n)}" if p >= 3 else "" for n,p in zip(counts,shares)], textposition="inside", hovertemplate="%{y}<br>%{customdata[0]:,.0f} personas · %{customdata[1]:,.2f}%<extra>%{fullData.name}</extra>"))
    extent = max(10, peak * 1.3)
    ticks = [-extent, -extent/2, 0, extent/2, extent]
    fig.update_layout(barmode="relative", bargap=.18)
    fig.update_xaxes(title="% del total con edad y género", range=[-extent,extent], tickvals=ticks, ticktext=[pct(abs(v)) for v in ticks], zeroline=True, zerolinecolor="#9AAFC5")
    fig.update_yaxes(title="Edad")
    plot(fig, "survey_age_pyramid", 350)
    st.caption(f"Base: {fmt(len(data))} personas con edad y género consignados. Es una cobertura parcial del total de habitantes declarado.")


def housing_cross(h):
    data = h[["vivienda_estado_general", "vivienda_aberturas_filtraciones"]].copy()
    data["filtraciones"] = data.vivienda_aberturas_filtraciones.map(yes_no)
    data = data.loc[data.filtraciones.notna() & data.vivienda_estado_general.isin(["Bueno","Regular","Malo"])]
    if data.empty:
        return
    counts = pd.crosstab(data.vivienda_estado_general, data.filtraciones).reindex(index=["Bueno","Regular","Malo"], columns=[False,True], fill_value=0)
    shares = counts.div(counts.sum(axis=1).replace(0, float("nan")), axis=0) * 100
    xlabels = ["Sin filtraciones", "Con filtraciones"]
    fig = go.Figure(go.Heatmap(z=shares.values, x=xlabels, y=counts.index, colorscale=[[0,"#EEF3F9"],[.5,"#91B2D6"],[1,BLUE]], zmin=0,zmax=100,colorbar=dict(title="% por fila",thickness=12), customdata=counts.values, hovertemplate="Estado %{y}<br>%{x}<br>%{customdata:,.0f} encuestas · %{z:,.2f}% del estado<extra></extra>"))
    for i, state in enumerate(counts.index):
        for j, label in enumerate(xlabels):
            value = shares.iloc[i,j]
            fig.add_annotation(x=label,y=state,text=f"<b>{fmt(counts.iloc[i,j])}</b><br>{pct(value)}" if pd.notna(value) else "Sin base",showarrow=False,font=dict(size=14,color="white" if pd.notna(value) and value>=70 else "#173954"))
    fig.update_yaxes(autorange="reversed",title="Estado general declarado")
    plot(fig,"survey_condition_leaks",300)
    st.caption(f"Cruce de {fmt(len(data))} encuestas con ambos datos. Cada fila suma 100%: permite ver las filtraciones dentro de cada estado general.")
    if counts.loc["Bueno"].sum() and counts.loc["Malo"].sum():
        st.markdown(f"**Lectura del cruce:** declaran filtraciones {fmt(counts.loc['Bueno',True])} de {fmt(counts.loc['Bueno'].sum())} viviendas con estado general ‘Bueno’ ({pct(shares.loc['Bueno',True])}) y {fmt(counts.loc['Malo',True])} de {fmt(counts.loc['Malo'].sum())} con estado ‘Malo’ ({pct(shares.loc['Malo',True])}).")


def render_characterization(survey_data, records, fetched_at, csv_bytes):
    st.markdown("""<style>
    .survey-hero{background:linear-gradient(110deg,#234B7B,#30598F);border-radius:18px;padding:28px 32px;border-top:5px solid #FFC600;color:white;margin-bottom:20px}
    .survey-hero h1{color:white;font-size:2.35rem;line-height:1.15;margin:10px 0 15px;letter-spacing:-.035em}
    .survey-hero p{color:#E5EDF7;font-size:1rem;line-height:1.6;max-width:900px;margin:0}
    .survey-hero small{color:#FFE589;font-size:.72rem;letter-spacing:.14em;font-weight:700}
    .survey-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:20px 0}
    .survey-insights{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:20px 0}
    .survey-card{background:#FFF;border:1px solid #E0E7EF;border-radius:13px;padding:20px;border-top:3px solid #91B2D6}
    .survey-insights .survey-card{background:#FFF8DF;border-top-color:#FFC600}
    .survey-label{font-size:.8rem;color:#526D87;font-weight:600;min-height:24px}
    .survey-value{font-size:2.15rem;color:#234B7B;font-weight:750;letter-spacing:-.04em;margin:5px 0}
    .survey-card p{font-size:.77rem;line-height:1.5;color:#62788C;margin:6px 0 0}
    .survey-section{display:flex;gap:15px;align-items:flex-start;margin:42px 0 20px;border-top:1px solid #DCE5EF;padding-top:25px}
    .survey-section>span{background:#30598F;color:#FFC600;border-radius:9px;padding:6px 11px;font-weight:700;margin-top:4px}
    .survey-section h2{font-size:1.55rem;margin:0 0 5px;color:#234B7B;letter-spacing:-.025em}
    .survey-section p{color:#647B90;line-height:1.5;font-size:.9rem;margin:0}
    .survey-note{border-left:4px solid #FFC600;background:#EEF3FA;border-radius:0 10px 10px 0;padding:18px 22px;margin:20px 0;color:#234B7B;line-height:1.6}
    [data-testid="stPlotlyChart"]{background:#FFF;border:1px solid #DFE7EF;border-radius:13px;padding:8px 4px}
    @media(max-width:1050px){.survey-cards{grid-template-columns:repeat(2,minmax(0,1fr))}.survey-insights{grid-template-columns:1fr}}
    @media(max-width:550px){.survey-hero{padding:22px}.survey-hero h1{font-size:1.9rem}.survey-value{font-size:1.8rem}}
    </style>""", unsafe_allow_html=True)
    h = records.loc[records.residencial].copy()
    people = survey_data.people.loc[survey_data.people.survey_uuid.isin(h.survey_uuid)].copy()
    st.markdown('<div class="survey-hero"><small>EDERSA · CARACTERIZACIÓN DE HOGARES</small><h1>Cómo se vive y se usa la energía</h1><p>Una lectura de las encuestas para conocer quiénes habitan las viviendas, cómo se construyen y qué condiciones de abrigo y seguridad eléctrica se declaran.</p></div>', unsafe_allow_html=True)
    st.caption(f"Recorrido de la selección: {fmt(len(records))} registros de campo → {fmt(records.completa.sum())} encuestas completadas → {fmt(len(h))} encuestas residenciales. Fecha de la copia / lectura: {str(fetched_at).split('T')[0]}.")
    if h.empty:
        st.info("No hay encuestas residenciales completas para estos filtros. Probá ampliar la selección territorial.")
        return
    adults = h.personas_mayores_edad_cantidad.sum(min_count=1)
    minors = h.menores_derivados.sum(min_count=1)
    total_people = h.personas_cantidad.sum(min_count=1)
    cards([
        ("Encuestas residenciales", fmt(len(h)), f"{h.barrio_encuesta.nunique()} barrios o sectores en la selección"),
        ("Personas declaradas", fmt(total_people), f"{fmt(adults)} mayores y {fmt(minors)} menores derivados de total menos mayores"),
        ("Personas por vivienda", fmt(h.personas_cantidad.median(), 2), f"Mediana · base {fmt(h.personas_cantidad.notna().sum())} encuestas"),
        ("Familias declaradas", fmt(h.familias_cantidad.sum(min_count=1)), f"{fmt(h.familias_cantidad.gt(1).sum())} encuestas declaran más de una familia"),
    ])
    ground = binary_stats(h.puesta_tierra_hay, positive=False)
    leaks = binary_stats(h.vivienda_aberturas_filtraciones)
    water_electric = binary_stats(h["energia_calefaccion_agua/Electricidad"])
    cards([
        ("Protección eléctrica", pct(ground["pct"]), f"Declara no tener puesta a tierra · {fmt(ground['n'])} de {fmt(ground['base'])} respuestas definidas"),
        ("Abrigo de la vivienda", pct(leaks["pct"]), f"Declara filtraciones de aire · {fmt(leaks['n'])} de {fmt(leaks['base'])} respuestas definidas"),
        ("Electricidad para agua caliente", pct(water_electric["pct"]), f"La utiliza sola o combinada con otras fuentes · {fmt(water_electric['n'])} de {fmt(water_electric['base'])} respuestas"),
    ], "survey-insights")
    st.caption("Los porcentajes usan respuestas definidas; NS/NC y faltantes no se convierten en ‘no’. Los conteos describen las encuestas seleccionadas, sin extrapolar al padrón de usuarios.")

    st.markdown("#### Qué se encontró en el territorio")
    terrain = records.terreno_tipo.fillna("Sin dato").value_counts().rename_axis("tipo").rename("n").reset_index()
    fig = px.treemap(terrain, names="tipo", parents=[""] * len(terrain), values="n", color="tipo", color_discrete_sequence=[BLUE,YELLOW,LIGHT,"#D5A354","#A8B8CA","#657C9D","#B6C4D4"])
    fig.update_traces(texttemplate="%{label}<br><b>%{value:,.0f}</b> · %{percentRoot:.2%}", textfont_size=14, marker_line_color="white", marker_line_width=3, hovertemplate="%{label}<br>%{value:,.0f} registros · %{percentRoot:.2%}<extra></extra>")
    fig.update_layout(showlegend=False)
    plot(fig,"survey_territory",270)
    st.caption(f"Los rectángulos representan los {fmt(len(records))} registros de campo seleccionados, no solo las viviendas que respondieron. El resto de la caracterización utiliza las {fmt(len(h))} encuestas residenciales completas.")

    section("01", "Quiénes viven en las viviendas", "El tamaño y la composición de los hogares dan contexto a sus necesidades de espacio y energía.")
    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("#### Tamaño de las viviendas en personas")
        data = h.loc[h.personas_cantidad.gt(0)].copy()
        data["tamaño"] = data.personas_cantidad.map(lambda n: "7 o más" if n >= 7 else str(int(n)))
        data["composición"] = data.menores_derivados.map(lambda n: "Sin dato de menores" if pd.isna(n) else "Con menores" if n > 0 else "Sin menores")
        sizes = data.groupby(["tamaño", "composición"], as_index=False).size().rename(columns={"size": "encuestas"})
        sizes["porcentaje"] = sizes.encuestas / len(data) * 100 if len(data) else 0
        fig = px.bar(sizes, x="tamaño", y="porcentaje", color="composición", barmode="stack", category_orders={"tamaño": ["1", "2", "3", "4", "5", "6", "7 o más"]}, color_discrete_map={"Con menores": YELLOW, "Sin menores": BLUE, "Sin dato de menores": GRAY}, labels={"tamaño": "Personas por vivienda", "porcentaje": "% de encuestas", "composición": ""}, custom_data=["encuestas"])
        fig.update_traces(hovertemplate="%{x:,.0f} personas<br>%{customdata[0]:,.0f} encuestas · %{y:,.2f}%<extra>%{fullData.name}</extra>")
        totals = sizes.groupby("tamaño").agg(n=("encuestas","sum"),p=("porcentaje","sum"))
        for label, value in totals.iterrows():
            fig.add_annotation(x=label, y=value.p, text=f"<b>{pct(value.p)}</b><br>{fmt(value.n)}", showarrow=False, yshift=18, font_size=10)
        fig.update_yaxes(range=[0, max(30, float(totals.p.max()) + 9)])
        plot(fig, "survey_household_sizes", 330)
        st.caption(f"Base: {fmt(len(data))} encuestas con cantidad de personas. Menores = total declarado menos mayores cuando ambos datos son coherentes.")
    with right:
        st.markdown("#### Composición declarada")
        consistent = h.loc[h.menores_derivados.notna()]
        ad = consistent.personas_mayores_edad_cantidad.sum()
        mi = consistent.menores_derivados.sum()
        if ad + mi:
            fig = go.Figure(go.Pie(labels=["Mayores", "Menores"], values=[ad, mi], hole=.73, marker_colors=[BLUE, YELLOW], textinfo="label+percent", textposition="outside", hovertemplate="%{label}: %{value} personas<extra></extra>"))
            fig.update_layout(showlegend=False, annotations=[dict(text=f"<b>{pct(mi / (ad + mi) * 100)}</b><br>menores", x=.5, y=.5, showarrow=False, font_size=19)])
            plot(fig, "survey_composition", 270)
        st.caption(f"Base coherente: {fmt(len(consistent))} encuestas. Son cantidades declaradas, no un padrón nominativo de personas únicas.")
    with st.container():
        st.markdown("#### Perfil de las personas registradas en detalle")
        st.caption("Esta tabla de personas tiene cobertura parcial respecto al total declarado de habitantes. Cada gráfico muestra únicamente las personas con esa respuesta; no representa la estructura completa de edades del hogar.")
        a, b = st.columns(2)
        with a:
            categorical(people.genero.replace("", pd.NA), "Género registrado", "survey_gender", height=350, donut=True)
        with b:
            st.markdown("#### Edad y género")
            age_pyramid(people)

    section("02", "Cómo son los espacios que habitan", "Estado general, superficie y materiales: distintas dimensiones de la vivienda, sin combinarlas en un índice no definido por la encuesta.")
    a, b = st.columns(2)
    with a:
        categorical(h.vivienda_estado_general, "Estado general declarado", "survey_condition", order=["Bueno", "Regular", "Malo"], height=280)
    with b:
        surface = h.superficie_construida.loc[h.superficie_construida.gt(0)]
        bins = pd.cut(surface, [0, 20, 40, 60, 80, 100, 120, float("inf")], labels=["Hasta 20", "21–40", "41–60", "61–80", "81–100", "101–120", "Más de 120"])
        categorical(bins.astype("str"), "Superficie construida · m²", "survey_surface", order=["Hasta 20", "21–40", "41–60", "61–80", "81–100", "101–120", "Más de 120"], height=280)
    density = binary_stats(h.hacinamiento_critico)
    collapse = binary_stats(h["vivienda_techo_interior_material/Riesgo_de_derrumbe"])
    cards([
        ("Personas por ambiente", fmt(h.personas_por_ambiente.median(), 2), f"Mediana · base {fmt(h.personas_por_ambiente.notna().sum())} encuestas"),
        ("Hacinamiento crítico", pct(density["pct"]), f"{fmt(density['n'])} de {fmt(density['base'])} casos con datos · más de 3 personas por ambiente"),
        ("Riesgo de derrumbe señalado", pct(collapse["pct"]), f"Marcado en la pregunta de techo interior · {fmt(collapse['n'])} de {fmt(collapse['base'])} respuestas"),
    ], "survey-insights")
    st.markdown("#### Estado de la vivienda y filtraciones de aire")
    housing_cross(h)
    with st.expander("Tipo de edificación, materiales y servicios", expanded=True):
        a, b = st.columns(2)
        with a:
            categorical(h.edificacion_tipo, "Tipo de edificación", "survey_building", height=260)
        with b:
            rates([("Agua de red", binary_stats(h["acceso_servicios/Agua_de_red"])), ("Cloaca pública", binary_stats(h["acceso_servicios/Cloaca_pública"])), ("Gas de red", binary_stats(h["acceso_servicios/Gas_de_red"])), ("Red eléctrica", binary_stats(h["acceso_servicios/Red_eléctrica"]))], "Servicios declarados", "survey_services", 260)
        a, b, c = st.columns(3)
        with a:
            categorical(h.vivienda_pared_material, "Paredes", "survey_walls", {"Paredes de ladrillo revocadas": "Ladrillo revocado", "Cartón, palma, paja sola o material de desecho": "Cartón / paja / desecho", "Piedra, bloque u hormigón": "Piedra / bloque / hormigón"}, height=370, donut=True)
        with b:
            categorical(h.vivienda_piso_material, "Pisos", "survey_floor", {"Mosaico, baldosa, cerámica, microcemento o cemento alisado": "Mosaico / cerámica / alisado"}, height=370, donut=True)
        with c:
            categorical(h.vivienda_techo_exterior_material, "Techo exterior", "survey_roof", {"Caña, palma, tabla, paja con barro o paja sola": "Caña / palma / paja / tabla"}, height=370, donut=True)

    section("03", "Cómo se calienta, se cocina y se usa la energía", "La presencia de un equipo no mide cuánto se lo usa. Las fuentes de energía pueden combinarse en una misma vivienda.")
    rates([
        ("Estufa a leña", binary_stats(h.estufa_lena)),
        ("Estufa a gas", binary_stats(h.estufa_gas)),
        ("Aire acondicionado", binary_stats(h.aire_acondicionado_hay)),
        ("Calefactor eléctrico declarado", binary_stats(h.calefactor_electrico)),
    ], "Equipamiento presente", "survey_equipment", 330)
    a, b = st.columns(2)
    for container, prefix, title, key in [(a, "energia_calefaccion_agua", "Energía para agua caliente", "survey_water"), (b, "energia_cocina", "Energía para cocinar", "survey_cooking")]:
        with container:
            rates([(name, binary_stats(h[prefix + "/" + name])) for name in ["Electricidad", "Gas", "Leña"]], title, key, 260)
    st.caption("Selección múltiple: los porcentajes de fuentes pueden sumar más de 100%. ‘Gas’ conserva el significado de la encuesta; estas preguntas no distinguen gas de red y envasado.")

    section("04", "Qué condiciones eléctricas requieren atención", "Separamos la infraestructura observada de las situaciones declaradas por las familias, para leer cada señal por su significado.")
    a, b = st.columns([1, 1.25])
    with a:
        tabs = st.tabs(["Pilar y medición", "Tablero"])
        with tabs[0]:
            categorical(h.pilar_hay, "Pilar eléctrico", "survey_pillar", height=300)
        with tabs[1]:
            categorical(h.tablero_hay, "Tablero eléctrico", "survey_board", {"Sí, con tablero completo": "Tablero completo", "Sí, solo con termicas": "Solo térmicas", "Sí, solo con disyuntor": "Solo disyuntor", "No": "Sin tablero"}, height=300)
    with b:
        rates([(label, binary_stats(h[column])) for column, label in PROBLEMS.items()], "Situaciones declaradas", "survey_problems", 360, kind="incidents")
    any_problem = binary_stats(h.algun_problema_electrico)
    st.markdown(f'<div class="survey-note"><b>{pct(any_problem["pct"])}</b> declara al menos una de las seis situaciones eléctricas relevadas: <b>{fmt(any_problem["n"])}</b> de <b>{fmt(any_problem["base"])}</b> respuestas definidas. Una misma vivienda puede reportar varias situaciones; las categorías no se suman.</div>', unsafe_allow_html=True)
    st.markdown("#### Cuántas situaciones se acumulan en una misma vivienda")
    flags = h[[column + "_bool" for column in PROBLEMS]]
    complete_flags = flags.loc[flags.notna().all(axis=1)]
    if len(complete_flags):
        problem_count = complete_flags.eq(True).sum(axis=1)
        count_distribution = problem_count.value_counts().reindex(range(7), fill_value=0).rename_axis("cantidad").rename("n").reset_index()
        count_distribution["porcentaje"] = count_distribution.n / len(complete_flags) * 100
        count_distribution["texto"] = count_distribution.apply(lambda r:f"{pct(r.porcentaje)}<br>{fmt(r.n)}",axis=1)
        fig = px.bar(count_distribution, x="cantidad", y="porcentaje", text="texto", custom_data=["n"], labels={"cantidad":"Cantidad de situaciones eléctricas declaradas", "porcentaje":"% de encuestas"})
        fig.update_traces(marker_color=[BLUE,YELLOW,"#D8A240",RED,RED,RED,RED],textposition="outside",cliponaxis=False,hovertemplate="%{x:,.0f} situaciones<br>%{customdata[0]:,.0f} encuestas · %{y:,.2f}%<extra></extra>")
        fig.update_yaxes(range=[0,float(count_distribution.porcentaje.max())+13])
        fig.update_xaxes(dtick=1)
        plot(fig,"survey_problem_count",330)
        st.caption(f"Base: {fmt(len(complete_flags))} encuestas con respuesta definida en las seis preguntas. El gráfico cuenta situaciones declaradas; no es un índice de riesgo.")
    categorical(h.cortes_electricidad, "Frecuencia de cortes declarada", "survey_outages", {"Sí, algunas veces en el año": "Algunas veces en el año", "No, nunca": "Nunca", "Si, Frecuentemente durante todo el año (en verano y en invierno)": "Frecuentes todo el año", "Sí, frecuentemente en invierno (al menos una vez por mes)": "Frecuentes en invierno", "Sí, frecuentemente en verano (al menos una vez por mes)": "Frecuentes en verano"}, height=280)

    section("05", "Alcance de esta lectura", "La cobertura y la calidad de las respuestas son parte de la caracterización.")
    linked = h.usuario_id.ne("").sum()
    repeated = h.loc[h.ubicacion_repetida]
    st.caption(f"Vínculo confirmado con el padrón: {fmt(linked)} de {fmt(len(h))} encuestas residenciales. Se incluyen también los hogares encuestados que no tienen NIS vinculado.")
    with st.expander("Definiciones, cobertura y registros para revisar"):
        st.markdown("""
        - La unidad es **la encuesta residencial completada**, identificada por UUID. No se confunden predios visitados, viviendas, familias y usuarios eléctricos.
        - Las cantidades de menores se derivan como total menos mayores cuando ambos valores son coherentes. El campo homónimo del formulario contiene ahora respuestas sobre asistencia escolar y no se usa como cantidad.
        - NS/NC y faltantes quedan fuera de porcentajes de Sí/No; cada indicador muestra su base. Los valores ausentes no se convierten en cero.
        - Las edades y géneros pertenecen a las personas registradas en detalle, una cobertura parcial del total declarado de habitantes.
        - No se calcula NBI ni una clasificación estructural compuesta: falta una definición validada en la fuente. Hacinamiento crítico se calcula como más de tres personas por ambiente: personas declaradas / ambientes totales, según el criterio operativo de esta herramienta.
        - Las ubicaciones repetidas se conservan: pueden corresponder a visitas o familias distintas. Los totales son de registros y personas declaradas, no un conteo depurado de individuos únicos.
        """)
        st.caption(f"Encuestas de la selección con ubicación repetida: {fmt(len(repeated))}.")
        if not repeated.empty:
            review = repeated[["survey_uuid", "barrio_encuesta", "manzana", "lote", "vivienda_n", "fecha_encuesta"]].copy()
            for column in ("manzana", "lote", "vivienda_n"):
                review[column] = review[column].astype("string")
            st.dataframe(review, hide_index=True, width="stretch")
    export_columns = ["survey_uuid", "barrio_encuesta", "fecha_encuesta", "personas_cantidad", "personas_mayores_edad_cantidad", "menores_derivados", "familias_cantidad", "superficie_construida", "ambientes_totales", "personas_por_ambiente", "hacinamiento_critico", "vivienda_estado_general", "vivienda_aberturas_filtraciones", "puesta_tierra_hay", "usuario_id", "vinculo_encuesta"]
    st.download_button("Descargar caracterización de la selección · CSV", csv_bytes(h[export_columns]), "edersa_caracterizacion.csv", "text/csv")
    st.markdown("[Abrir formulario de producción](https://docs.google.com/spreadsheets/d/15ErlZXsZgrmHpKdeWLPDsgcI9A5AhqBjrUCFWmgAm5Q/edit#gid=1160852517)")
