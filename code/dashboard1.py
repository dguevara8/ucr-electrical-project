# dashboard.py
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import numpy as np

st.set_page_config(page_title="Dashboard KPI", layout="wide")

# ==========================================================
# UMBRALES DEL SEMÁFORO
# ==========================================================
UMBRALES = {
    "Disponibilidad": {"verde": 99.0, "rojo": 90},
    "Accesibilidad": {"verde": 99.2, "rojo": 90},
    "Retenibilidad_Promedio": {"verde": 98.9, "rojo": 90},
    "Retenibilidad_Tecnica": {"verde": 99.0, "rojo": 90},
    "Retenibilidad_Usuario": {"verde": 98.8, "rojo": 90},
}

COLOR_MAP = {"Verde": "#00FF00", "Amarillo": "#FFFF00", "Rojo": "#FF0000"}
CATEGORY_ORDER = {"Estado": ["Rojo", "Amarillo", "Verde"]}

# ==========================================================
# Funciones auxiliares
# ==========================================================
def safe_div(num, den):
    den = den.replace(0, np.nan)
    result = (num / den)
    return result.fillna(0)

def obtener_estado_kpi(df, kpi_col, umbral_verde, umbral_rojo):
    df_out = df.copy()
    df_out["Estado"] = np.select(
        [
            df_out[kpi_col] < umbral_rojo,
            df_out[kpi_col] >= umbral_verde
        ],
        [
            "Rojo",
            "Verde"
        ],
        default="Amarillo"
    )
    return df_out

@st.cache_data
def load_kpi_data():
    conn = sqlite3.connect("kpi_data.db")
    df = pd.read_sql("SELECT * FROM kpi_data", conn)
    conn.close()
    return df

@st.cache_data
def load_site_data():
    conn = sqlite3.connect("kpi_data.db")
    df = pd.read_sql("SELECT * FROM site_data", conn)
    conn.close()
    df["Site_id"] = df["Site_id"].astype(str)
    return df

df = load_kpi_data()
sites_df = load_site_data()

# ==========================================================
# Merge para obtener el nombre del sitio
# ==========================================================
df["Site Id"] = df["Site Id"].astype(str)
sites_df = sites_df.rename(columns={"Site_id": "Site Id", "Nombre": "Site Name"})
df = pd.merge(df, sites_df[["Site Id", "Site Name"]], on="Site Id", how="left")
df["Site Name"] = df["Site Name"].fillna("Sin Nombre Site")

# ==========================================================
# Cálculo de KPIs
# ==========================================================
def calcular_kpis(df):
    df = df.copy()

    df["Disponibilidad"] = 100 * safe_div(df["SAMPLES_CELL_AVAIL"], df["DENOM_CELL_AVAIL"])

    num_t1 = df["NRRCC_RRC_STPSUCC_TOT"]
    den_t1 = (
        df["NRRCC_RRC_STPREQ_MO_SIGNALLING"] + df["NRRCC_RRC_STPREQ_MO_DATA"] +
        df["NRRCC_RRC_STPREQ_MT_ACCESS"] + df["NRRCC_RRC_STPREQ_EMERGENCY"] +
        df["NRRCC_RRC_STPREQ_HIPRIO_ACCESS"] + df["NRRCC_RRC_STPREQ_MO_VOICECALL"] +
        df["NRRCC_RRC_STPREQ_MO_SMS"] + df["NRRCC_RRC_STPREQ_MPS"] +
        df["NRRCC_RRC_STPREQ_MCS"] + df["NRRCC_RRC_STPREQ_MO_VIDEOCAL"]
    )
    t1 = safe_div(num_t1, den_t1)

    num_t2 = df["NNGCC_INIT_UE_MSG_SENT"]
    den_t2 = df["NRRCC_RRC_STPSUCC_TOT"] + df["REESTAB_ACC_FALLBACK"] + df["NRRCC_RRC_RESUME_FALLBACK_SUCC"]
    t2 = safe_div(num_t2, den_t2)

    t3 = safe_div(df["NNGCC_UE_LOGICAL_CONN_ESTAB"], df["NNGCC_INIT_UE_MSG_SENT"])
    t4 = safe_div(df["NNGCC_UE_CTXT_STP_RESP_SENT"], df["NNGCC_UE_CTXT_STP_REQ_RECD"])

    df["Accesibilidad"] = 100 * (t1 * t2 * t3 * t4)

    df["Retenibilidad_Tecnica"] = (
        100 - 100 * safe_div(df["NG_FLOW_REL"] - df["NG_FLOW_REL_NORMAL"], df["NG_FLOW_REL"])
    ).fillna(0)

    df["Retenibilidad_Usuario"] = (
        100 - 100 * safe_div(
            df["NG_FLOW_REL"] - df["NG_FLOW_REL_NORMAL"] - df["NG_FLOW_REL_AMF_UE_LOST"],
            df["NG_FLOW_REL"]
        )
    ).fillna(0)

    df["Retenibilidad_Promedio"] = (df["Retenibilidad_Tecnica"] + df["Retenibilidad_Usuario"]) / 2

    return df

df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
df = calcular_kpis(df)

sitios_names = sorted(df["Site Name"].unique())
site_id_to_name = sites_df.set_index("Site Id")["Site Name"].to_dict()
site_name_to_id = {v: k for k, v in site_id_to_name.items()}

# Sidebar
st.sidebar.title("Panel de Control")
rango_fechas = st.sidebar.date_input("Rango de fechas", [df["Date"].min(), df["Date"].max()], key="rango_fechas")
sitio_sel_names = st.sidebar.multiselect("Filtrar Sites", sitios_names, default=sitios_names, key="sitio_sel_names")

sitio_sel_ids = [site_name_to_id.get(name) for name in sitio_sel_names if site_name_to_id.get(name) is not None]

df_filtrado = df[
    (df["Date"] >= pd.to_datetime(rango_fechas[0])) &
    (df["Date"] <= pd.to_datetime(rango_fechas[1])) &
    (df["Site Id"].isin(sitio_sel_ids))
].copy()

# ==========================================================
# KPI DIARIO
# ==========================================================
def kpi_diario(df):
    cols_sum = [
        "DENOM_CELL_AVAIL","SAMPLES_CELL_AVAIL","NG_FLOW_REL_AMF_UE_LOST",
        "NG_FLOW_REL_NORMAL","NG_FLOW_REL","REESTAB_ACC_FALLBACK",
        "NRRCC_RRC_STPREQ_MO_SIGNALLING","NRRCC_RRC_STPREQ_MO_DATA",
        "NRRCC_RRC_STPREQ_MT_ACCESS","NRRCC_RRC_STPREQ_EMERGENCY",
        "NRRCC_RRC_STPREQ_HIPRIO_ACCESS","NRRCC_RRC_STPREQ_MO_VOICECALL",
        "NRRCC_RRC_STPREQ_MO_SMS", "NRRCC_RRC_STPREQ_MPS",
        "NRRCC_RRC_STPREQ_MCS","NRRCC_RRC_STPREQ_MO_VIDEOCAL",
        "NRRCC_RRC_STPSUCC_TOT","NRRCC_RRC_RESUME_FALLBACK_SUCC",
        "NNGCC_INIT_UE_MSG_SENT","NNGCC_UE_LOGICAL_CONN_ESTAB",
        "NNGCC_UE_CTXT_STP_REQ_RECD","NNGCC_UE_CTXT_STP_RESP_SENT"
    ]

    agg = df.groupby(["Date","Site Id", "Site Name"], as_index=False)[cols_sum].sum(numeric_only=True)
    return calcular_kpis(agg)

df_diario = kpi_diario(df_filtrado)

# ==========================================================
# TABS PRINCIPALES
# ==========================================================
tab1, tab_cluster, tab2 = st.tabs(["📊 Vista General", "🗂 Clusters", "📈 KPI Individual"])

# ==========================================================
# VISTA GENERAL
# ==========================================================
with tab1:
    st.header("KPIs – Vista General (Mapa único)")

    opciones_vg = ["Disponibilidad", "Accesibilidad", "Retenibilidad_Promedio"]
    kpi_sel = st.multiselect("Seleccione KPIs para gráficos:", opciones_vg, default=opciones_vg, key="kpi_sel_vg")

    df_general = df_diario.groupby("Date", as_index=False)[opciones_vg].mean()
    df_chart = pd.melt(df_general, id_vars="Date", value_vars=kpi_sel, var_name="KPI", value_name="Valor")
    fig_lines = px.line(df_chart, x="Date", y="Valor", color="KPI", title="KPIs Promedio Diarios")
    st.plotly_chart(fig_lines, use_container_width=True, key="chart_general")

    st.subheader("Valores Promedio Seleccionados:")
    for k in kpi_sel:
        valor = df_general[k].mean()
        st.markdown(f"<div style='font-size:22px; margin-top:15px;'>Promedio de {k.replace('_', ' ')}:</div>"
                    f"<div style='font-size:40px; font-weight:bold; margin-bottom:20px;'>{valor:.2f}%</div>",
                    unsafe_allow_html=True)

    # Mapa
    mapa_base_vg = sites_df[["Site Id", "Site Name", "Latitud", "Longitud"]].copy()

    agg_map = df_filtrado.groupby("Site Id", as_index=False).sum(numeric_only=True)
    if "Site Id" not in agg_map.columns:
        agg_map = agg_map.reset_index().rename(columns={"index":"Site Id"})
    agg_map["Site Id"] = agg_map["Site Id"].astype(str)
    agg_map = calcular_kpis(agg_map)
    
    mapa = mapa_base_vg.merge(agg_map[["Site Id"] + opciones_vg], on="Site Id", how="left")

    mapa["Latitud"] = pd.to_numeric(mapa.get("Latitud"), errors="coerce")
    mapa["Longitud"] = pd.to_numeric(mapa.get("Longitud"), errors="coerce")
    df_map = mapa[mapa["Site Id"].isin(sitio_sel_ids)].dropna(subset=["Latitud", "Longitud"]).copy()

    st.subheader("Mapa (seleccione KPI a mostrar)")
    kpi_map = st.selectbox("KPI para mapa", opciones_vg, index=0, key="kpi_map_vg")

    if df_map.empty:
        st.warning("No hay coordenadas válidas para los sites seleccionados.")
    else:
        umbral_v = UMBRALES[kpi_map]["verde"]
        umbral_r = UMBRALES[kpi_map]["rojo"]
        df_map_sem = obtener_estado_kpi(df_map, kpi_map, umbral_v, umbral_r)
        
        fig_map = px.scatter_mapbox(
            df_map_sem,
            lat="Latitud",
            lon="Longitud",
            color="Estado",
            hover_name="Site Name",
            hover_data={
                kpi_map: ":.2f",
                "Estado": True,
                "Site Id": True
            },
            color_discrete_map=COLOR_MAP,
            category_orders=CATEGORY_ORDER,
            zoom=6,
            height=800,
            title=f"Mapa de {kpi_map.replace('_', ' ')}"
        )
        fig_map.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":30,"l":0,"b":0}, mapbox=dict(
            center=dict(lat=9.9333, lon=-84.0833),
            zoom=8.5))
        fig_map.update_traces(marker=dict(size=20, opacity=0.85))
        st.plotly_chart(fig_map, use_container_width=True, key=f"single_map_{kpi_map}")

# ==========================================================
# CLUSTERS 
# ==========================================================
with tab_cluster:
    st.header("KPIs por Clusters")

    clusters = {
        "Zona Sur": [1,2,3,4,5,6],
        "Alajuela": [7,8,9,10,11,12,13,14,15,16,17],
        "San Ramon": [18,19,20,21,22,48,49],
        "Cartago": [23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,46,47],
        "Atlántico": [38,39,40,41,42,43,44,45]
    }

    cluster_sel = st.multiselect("Seleccione Clusters:", list(clusters.keys()), default=list(clusters.keys()), key="cluster_sel")

    def clusterizar(df_in, clusters):
        registros = []
        df_local = df_in.copy()
        df_local["SectorID"] = df_local["Site Id"].astype(int)

        for cname, sectors in clusters.items():
            tmp = df_local[df_local["SectorID"].isin(sectors)]
            if tmp.empty:
                continue

            agg = tmp.groupby("Date", as_index=False).sum(numeric_only=True)
            agg["Cluster"] = cname
            registros.append(agg)

        if not registros:
            return pd.DataFrame()

        df_cluster = pd.concat(registros, ignore_index=True)
        return calcular_kpis(df_cluster)

    df_cluster = clusterizar(df_filtrado, clusters)

    if df_cluster.empty:
        st.warning("No hay datos disponibles para los clusters seleccionados.")
        st.stop()

    df_cluster = df_cluster[df_cluster["Cluster"].isin(cluster_sel)]

    kpi_cluster = ["Disponibilidad", "Accesibilidad", "Retenibilidad_Promedio"]
    k_sel = st.multiselect("Seleccione KPIs (para cálculos y listados):", kpi_cluster, default=kpi_cluster, key="kpi_sel_cluster")

    st.subheader("Gráficas y Promedios por Cluster")
    
    for cname in cluster_sel:
        st.markdown(f"### {cname}")
        
        # Gráfica para este cluster específico
        df_temp = df_cluster[df_cluster["Cluster"] == cname]
        df_plot_cluster = pd.melt(df_temp, id_vars=["Date", "Cluster"], value_vars=k_sel, var_name="KPI", value_name="Valor")
        fig_cluster = px.line(df_plot_cluster, x="Date", y="Valor", color="KPI", title=f"KPIs en {cname}")
        st.plotly_chart(fig_cluster, use_container_width=True, key=f"chart_cluster_{cname.replace(' ', '_')}")
        
        # Promedios para este cluster
        for k in k_sel:
            st.markdown(f"<b>{k.replace('_',' ')}:</b> {df_temp[k].mean():.2f}%", unsafe_allow_html=True)
        st.markdown("---")

    st.subheader("Mapas por Cluster (mapa único por cluster)")

    mapa_base_cluster = sites_df[["Site Id", "Site Name", "Latitud", "Longitud"]].copy()

    for cname, sectors in clusters.items():
        if cname not in cluster_sel:
            continue

        cname_key = cname.replace(" ", "_").replace("á","a").replace("í","i")
        st.markdown(f"### 🗺 {cname}")

        df_tmp = df_filtrado[df_filtrado["Site Id"].astype(int).isin(sectors)].copy()
        if df_tmp.empty:
            st.info(f"No hay datos para {cname}.")
            continue

        agg = df_tmp.groupby("Site Id", as_index=False).sum(numeric_only=True)
        if "Site Id" not in agg.columns:
            agg = agg.reset_index().rename(columns={"index":"Site Id"})
        agg["Site Id"] = agg["Site Id"].astype(str)
        agg = calcular_kpis(agg)

        mapa_cluster = mapa_base_cluster.merge(agg[["Site Id"] + kpi_cluster], on="Site Id", how="left")
        
        mapa_cluster = mapa_cluster[
            mapa_cluster["Site Id"].astype(int).isin(sectors) &
            mapa_cluster["Site Id"].isin(sitio_sel_ids)
        ].copy()

        mapa_cluster["Latitud"] = pd.to_numeric(mapa_cluster.get("Latitud"), errors="coerce")
        mapa_cluster["Longitud"] = pd.to_numeric(mapa_cluster.get("Longitud"), errors="coerce")
        df_map_cluster = mapa_cluster.dropna(subset=["Latitud", "Longitud"]).copy()

        if df_map_cluster.empty:
            st.info(f"No hay coordenadas válidas para {cname}.")
            continue

        kpi_for_cluster = st.selectbox(f"KPI a mostrar en mapa – {cname}", kpi_cluster,
                                       index=0, key=f"cluster_kpi_{cname_key}")
        
        umbral_v = UMBRALES[kpi_for_cluster]["verde"]
        umbral_r = UMBRALES[kpi_for_cluster]["rojo"]
        df_map_cluster_sem = obtener_estado_kpi(df_map_cluster, kpi_for_cluster, umbral_v, umbral_r)

        fig_cluster_map = px.scatter_mapbox(
            df_map_cluster_sem,
            lat="Latitud",
            lon="Longitud",
            color="Estado",
            hover_name="Site Name",
            hover_data={
                kpi_for_cluster: ":.2f",
                "Estado": True,
                "Site Id": True
            },
            color_discrete_map=COLOR_MAP,
            category_orders=CATEGORY_ORDER,
            zoom=7,
            height=800,
            title=f"Mapa de {kpi_for_cluster.replace('_', ' ')} en {cname}"
        )
        fig_cluster_map.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":30,"l":0,"b":0}, mapbox=dict(
            center=dict(lat=9.9333, lon=-84.0833),
            zoom=8.5))
        fig_cluster_map.update_traces(marker=dict(size=20, opacity=0.9))
        st.plotly_chart(fig_cluster_map, use_container_width=True, key=f"cluster_single_map_{cname_key}")

# ==========================================================
# KPI INDIVIDUAL
# ==========================================================
with tab2:
    st.header("KPI Individual")

    opcion = st.selectbox("Seleccione KPI", ["Disponibilidad","Accesibilidad","Retenibilidad"], key="select_kpi_ind")

    mapa_base_indiv = sites_df[["Site Id", "Site Name", "Latitud", "Longitud"]].copy()
    mapa_base_indiv = mapa_base_indiv[mapa_base_indiv["Site Id"].isin(sitio_sel_ids)]

    # DISPONIBILIDAD
    if opcion == "Disponibilidad":
        kpi_col = "Disponibilidad"
        st.subheader("Disponibilidad")
        
        fig = px.line(df_diario, x="Date", y=kpi_col, color="Site Name", title="Disponibilidad diaria")
        st.plotly_chart(fig, use_container_width=True, key="indiv_disponibilidad_line")

        agg = df_filtrado.groupby("Site Id", as_index=False)[["SAMPLES_CELL_AVAIL","DENOM_CELL_AVAIL"]].sum(numeric_only=True)
        if "Site Id" not in agg.columns:
            agg = agg.reset_index().rename(columns={"index":"Site Id"})
        agg["Site Id"] = agg["Site Id"].astype(str)
        agg[kpi_col] = 100 * safe_div(agg["SAMPLES_CELL_AVAIL"], agg["DENOM_CELL_AVAIL"])

        mapa = mapa_base_indiv.merge(agg[["Site Id", kpi_col]], on="Site Id", how="left")
        
        umbral_v = UMBRALES[kpi_col]["verde"]
        umbral_r = UMBRALES[kpi_col]["rojo"]
        mapa_sem = obtener_estado_kpi(mapa, kpi_col, umbral_v, umbral_r)

        fig = px.scatter_mapbox(mapa_sem, lat="Latitud", lon="Longitud", color="Estado",
                                 hover_name="Site Name",
                                 hover_data={kpi_col: ":.2f", "Site Id": True}, 
                                 color_discrete_map=COLOR_MAP,
                                 category_orders=CATEGORY_ORDER,
                                 zoom=6, height=800, title="Mapa de Disponibilidad (Período Total)")
        fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":30,"l":0,"b":0}, mapbox=dict(
            center=dict(lat=9.9333, lon=-84.0833),
            zoom=8.5))
        fig.update_traces(marker=dict(size=20, opacity=0.85))
        st.plotly_chart(fig, use_container_width=True, key="indiv_disponibilidad_map")

    # ACCESIBILIDAD
    if opcion == "Accesibilidad":
        kpi_col = "Accesibilidad"
        st.subheader("Accesibilidad")
        
        fig = px.line(df_diario, x="Date", y=kpi_col, color="Site Name", title="Accesibilidad diaria")
        st.plotly_chart(fig, use_container_width=True, key="indiv_accesibilidad_line")

        agg = df_filtrado.groupby("Site Id", as_index=False).sum(numeric_only=True)
        if "Site Id" not in agg.columns:
            agg = agg.reset_index().rename(columns={"index":"Site Id"})
        agg["Site Id"] = agg["Site Id"].astype(str)
        agg = calcular_kpis(agg)
        
        mapa = mapa_base_indiv.merge(agg[["Site Id", kpi_col]], on="Site Id", how="left")
        
        umbral_v = UMBRALES[kpi_col]["verde"]
        umbral_r = UMBRALES[kpi_col]["rojo"]
        mapa_sem = obtener_estado_kpi(mapa, kpi_col, umbral_v, umbral_r)

        fig = px.scatter_mapbox(mapa_sem, lat="Latitud", lon="Longitud", color="Estado",
                                 hover_name="Site Name",
                                 hover_data={kpi_col: ":.2f", "Site Id": True},
                                 color_discrete_map=COLOR_MAP,
                                 category_orders=CATEGORY_ORDER,
                                 zoom=6, height=800, title="Mapa de Accesibilidad (Período Total)")
        fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":30,"l":0,"b":0}, mapbox=dict(
            center=dict(lat=9.9333, lon=-84.0833),
            zoom=8.5))
        fig.update_traces(marker=dict(size=20, opacity=0.85))
        st.plotly_chart(fig, use_container_width=True, key="indiv_accesibilidad_map")

    # RETENIBILIDAD
    if opcion == "Retenibilidad":
        st.subheader("Retenibilidad")
        tabs = st.tabs(["Técnica","Usuario"])

        # Retenibilidad Técnica
        with tabs[0]:
            kpi_col = "Retenibilidad_Tecnica"
            
            fig = px.line(df_diario, x="Date", y=kpi_col, color="Site Name", title="Retenibilidad Técnica")
            st.plotly_chart(fig, use_container_width=True, key="indiv_ret_tec_line")

            agg = df_filtrado.groupby("Site Id", as_index=False)[["NG_FLOW_REL","NG_FLOW_REL_NORMAL"]].sum(numeric_only=True)
            if "Site Id" not in agg.columns:
                agg = agg.reset_index().rename(columns={"index":"Site Id"})
            agg["Site Id"] = agg["Site Id"].astype(str)

            agg[kpi_col] = 100 - 100 * safe_div(
                agg["NG_FLOW_REL"] - agg["NG_FLOW_REL_NORMAL"],
                agg["NG_FLOW_REL"]
            )

            mapa = mapa_base_indiv.merge(agg[["Site Id", kpi_col]], on="Site Id", how="left")
            
            umbral_v = UMBRALES[kpi_col]["verde"]
            umbral_r = UMBRALES[kpi_col]["rojo"]
            mapa_sem = obtener_estado_kpi(mapa, kpi_col, umbral_v, umbral_r)

            fig = px.scatter_mapbox(mapa_sem, lat="Latitud", lon="Longitud", color="Estado",
                                     hover_name="Site Name",
                                     hover_data={kpi_col: ":.2f", "Site Id": True},
                                     color_discrete_map=COLOR_MAP,
                                     category_orders=CATEGORY_ORDER,
                                     zoom=6, height=800, title="Mapa de Retenibilidad Técnica (Período Total)")
            fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":30,"l":0,"b":0}, mapbox=dict(
                center=dict(lat=9.9333, lon=-84.0833),
                zoom=8.5))
            fig.update_traces(marker=dict(size=20, opacity=0.85))
            st.plotly_chart(fig, use_container_width=True, key="indiv_ret_tec_map")

       # Retenibilidad Usuario
        with tabs[1]:
            kpi_col = "Retenibilidad_Usuario"

            fig = px.line(df_diario, x="Date", y=kpi_col, color="Site Name", title="Retenibilidad Usuario")
            st.plotly_chart(fig, use_container_width=True, key="indiv_ret_usr_line")

            agg = df_filtrado.groupby("Site Id", as_index=False)[["NG_FLOW_REL","NG_FLOW_REL_NORMAL","NG_FLOW_REL_AMF_UE_LOST"]].sum(numeric_only=True)
            if "Site Id" not in agg.columns:
                agg = agg.reset_index().rename(columns={"index":"Site Id"})
            agg["Site Id"] = agg["Site Id"].astype(str)

            agg[kpi_col] = 100 - 100 * safe_div(
                agg["NG_FLOW_REL"] - agg["NG_FLOW_REL_NORMAL"] - agg["NG_FLOW_REL_AMF_UE_LOST"],
                agg["NG_FLOW_REL"]
            )

            mapa = mapa_base_indiv.merge(agg[["Site Id", kpi_col]], on="Site Id", how="left")
            
            umbral_v = UMBRALES[kpi_col]["verde"]
            umbral_r = UMBRALES[kpi_col]["rojo"]
            mapa_sem = obtener_estado_kpi(mapa, kpi_col, umbral_v, umbral_r)

            fig = px.scatter_mapbox(mapa_sem, lat="Latitud", lon="Longitud", color="Estado",
                                     hover_name="Site Name",
                                     hover_data={kpi_col: ":.2f", "Site Id": True},
                                     color_discrete_map=COLOR_MAP,
                                     category_orders=CATEGORY_ORDER,
                                     zoom=6, height=800, title="Mapa de Retenibilidad Usuario (Período Total)")
            fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":30,"l":0,"b":0}, mapbox=dict(
                center=dict(lat=9.9333, lon=-84.0833),
                zoom=8.5))
            fig.update_traces(marker=dict(size=20, opacity=0.85))
            st.plotly_chart(fig, use_container_width=True, key="indiv_ret_usr_map")

st.markdown("---")
st.caption("Dashboard KPI · Proyecto Eléctrico UCR")