import plotly.graph_objects as go
import pandas as pd
from plotly.subplots import make_subplots
from model import label_period, general_consumption_trend


def trend_sparkline_svg(values):
    data = pd.to_numeric(pd.Series(values,dtype="float64"),errors="coerce").dropna().tolist()
    if len(data)<2:
        return '<span style="color:#8A98A7;font-size:.7rem">Sin tendencia</span>'
    change = (data[-1]-data[0])/max(abs(data[0]),100)*100
    direction = "up" if change>1 else "down" if change< -1 else "flat"
    low,high = min(data),max(data)
    strength = min(abs(change)/100,1)
    light,dark = ((159,206,179),(22,131,74)) if direction=="up" else ((233,172,177),(180,35,50))
    color = "#8A98A7" if direction=="flat" else '#'+''.join(f'{round(a+(b-a)*strength):02x}' for a,b in zip(light,dark))
    points = ' '.join(f'{4+i*100/(len(data)-1):.2f},{22 if high==low else 40-(value-low)/(high-low)*36:.2f}' for i,value in enumerate(data))
    label = "creciente" if direction=="up" else "decreciente" if direction=="down" else "estable"
    return f'<svg data-direction="{direction}" role="img" aria-label="Tendencia {label}" viewBox="0 0 108 44" style="width:100%;height:44px"><title>Tendencia general {label}</title><polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'


def individual_history_chart(complete,history=None):
    labels = complete.periodo.map(label_period)
    values = complete.consumo.map(lambda value: "" if pd.isna(value) else f"{value:,.0f}".replace(",","."))
    fig = go.Figure(go.Scatter(x=complete.periodo,y=complete.consumo,name="Consumo registrado",mode="lines+markers+text",text=values,textposition="top center",textfont=dict(size=11,color="#234B7B"),line=dict(color="#30598F",width=3),marker=dict(size=7),connectgaps=False,cliponaxis=False,customdata=labels,hovertemplate="%{customdata}<br>Consumo registrado: %{y}<extra></extra>"))
    trend = general_consumption_trend(complete if history is None else history,complete.periodo)
    if trend.notna().any():
        fig.add_trace(go.Scatter(x=complete.periodo,y=trend,name="Tendencia general",mode="lines",line=dict(color="#6C7D91",width=2,dash="dash"),connectgaps=False,customdata=labels,hovertemplate="%{customdata}<br>Tendencia general: %{y:.1f}<extra></extra>"))
    if complete.consumo.lt(100).any():
        fig.add_hline(y=100,line_dash="dot",line_color="#C27B13",line_width=1.5,annotation_text="Umbral: 100 · mediciones inferiores excluidas",annotation_position="bottom left",annotation_font=dict(size=10,color="#94600C"))
        fig.data[0].marker.color = ["#C27B13" if pd.notna(value) and value < 100 else "#30598F" for value in complete.consumo]
    if complete.consumo.gt(1000).any():
        fig.add_hline(y=1000,line_dash="dot",line_color="#C34248",line_width=1.5,annotation_text="Consumo crítico: >1000",annotation_position="top left",annotation_font=dict(size=10,color="#A62D35"))
        fig.data[0].marker.color = ["#C34248" if pd.notna(value) and value > 1000 else "#C27B13" if pd.notna(value) and value < 100 else "#30598F" for value in complete.consumo]
    if not complete.empty:
        start = complete.periodo.min()
        end = complete.periodo.max() + pd.DateOffset(months=2)
        for year in range(start.year-1,end.year+1):
            for first,last,color,icon in [(pd.Timestamp(year,6,1),pd.Timestamp(year,9,1),"#FFFFFF","❄️"),(pd.Timestamp(year,12,1),pd.Timestamp(year+1,3,1),"#FFE16B","☀️")]:
                lower,upper = max(start,first),min(end,last)
                if lower >= upper:
                    continue
                fig.add_vrect(x0=lower,x1=upper,fillcolor=color,opacity=.9 if icon=="❄️" else .45,line_width=0,layer="below")
                fig.add_annotation(x=lower+(upper-lower)/2,y=1.025,yref="paper",text=icon,showarrow=False,font=dict(size=12),opacity=.4)
        fig.update_xaxes(range=[start-pd.Timedelta(days=12),end])
    ticks = complete.iloc[::max(1,(len(complete)+5)//6)]
    fig.update_xaxes(title="Período consumido",tickvals=ticks.periodo,ticktext=ticks.periodo.map(label_period).str.replace(" / ","<br>",regex=False),tickangle=0)
    fig.update_yaxes(title="Consumo registrado",rangemode="tozero")
    fig.update_layout(showlegend=True,legend=dict(orientation="h",x=0,y=1.16,yanchor="bottom"))
    return fig


def evolution_chart(summary):
    """Banda de distribución P25–P75, no intervalo de confianza."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=.25, row_heights=[.72,.28], subplot_titles=["Consumo por usuario y bimestre", "Usuarios incluidos en las estadísticas de consumo"])
    labels = summary.periodo.map(label_period)
    fig.add_trace(go.Scatter(x=summary.periodo,y=summary.p25,mode="lines",line=dict(width=0),showlegend=False,hoverinfo="skip"),row=1,col=1)
    fig.add_trace(go.Scatter(x=summary.periodo,y=summary.p75,mode="lines",line=dict(width=0),fill="tonexty",fillcolor="rgba(48,89,143,.15)",name="Consumo · 50% central (P25–P75)",showlegend=False,hoverinfo="skip"),row=1,col=1)
    custom = list(zip(labels,summary.usuarios,summary.variacion_mediana_pct,summary.p25,summary.p75,summary.cobertura))
    for col,name,color,dash in [("mediana","Consumo · mediana","#30598F","solid"),("promedio","Consumo · media","#EBAE00","dash")]:
        fig.add_trace(go.Scatter(x=summary.periodo,y=summary[col],name=name,mode="lines+markers",line=dict(color=color,width=3 if col=="mediana" else 2,dash=dash),customdata=custom,connectgaps=False,hovertemplate=f"%{{customdata[0]}}<br>{name}: %{{y:.1f}}<br>Variación de la mediana: %{{customdata[2]:.1f}}%<br>Usuarios con consumo ≥100: %{{customdata[1]}}<br>Cobertura: %{{customdata[5]:.1f}}%<br>P25: %{{customdata[3]:.1f}} · P75: %{{customdata[4]:.1f}}<extra></extra>"),row=1,col=1)
    fig.add_trace(go.Bar(x=summary.periodo,y=summary.usuarios,name="Usuarios · cantidad",marker_color="#91B2D6",customdata=custom,hovertemplate="%{customdata[0]}<br>Usuarios incluidos (consumo ≥100): %{y}<br>Cobertura: %{customdata[5]:.1f}%<extra></extra>"),row=2,col=1)
    ticks = summary.iloc[::max(1,(len(summary)+5)//6)]
    fig.update_xaxes(showticklabels=True,tickvals=ticks.periodo,ticktext=ticks.periodo.map(label_period).str.replace(" / ","<br>",regex=False),tickangle=0,row=1,col=1)
    fig.update_xaxes(title="Período consumido",tickvals=ticks.periodo,ticktext=ticks.periodo.map(label_period),tickangle=-30,row=2,col=1)
    fig.update_yaxes(title="Consumo bimestral · fuente",row=1,col=1)
    fig.update_yaxes(title="Cantidad de usuarios",rangemode="tozero",row=2,col=1)
    fig.update_layout(legend=dict(orientation="h", y=1.22, x=0), hovermode="x unified")
    return fig
