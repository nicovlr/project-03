"""GovSense — Streamlit interactive dashboard."""

from __future__ import annotations

import io
import os

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine, text

from dashboard.geo import REGIONS_GEOJSON_URL

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://govsense:govsense@localhost:5432/govsense",
)

st.set_page_config(
    page_title="GovSense — Intelligence Operationnelle",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


@st.cache_data(ttl=600)
def load_geojson():
    """Fetch the GeoJSON of French regions (cached 10 min)."""
    resp = httpx.get(REGIONS_GEOJSON_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()


def query_df(sql: str) -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def safe_query(sql: str) -> pd.DataFrame | None:
    try:
        df = query_df(sql)
        return df if not df.empty else None
    except Exception as exc:
        st.error(f"Erreur base de donnees : {exc}")
        return None


def download_button_csv(df: pd.DataFrame, filename: str, label: str = "Telecharger CSV"):
    """Render a CSV download button."""
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    st.download_button(label, buf.getvalue(), file_name=filename, mime="text/csv")


def download_button_excel(df: pd.DataFrame, filename: str, label: str = "Telecharger Excel"):
    """Render an Excel download button."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="data")
    st.download_button(label, buf.getvalue(), file_name=filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("🏛️ GovSense")
st.sidebar.markdown("**Intelligence operationnelle**  \nDonnees publiques → Decisions")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    [
        "Vue d'ensemble",
        "Carte de France",
        "Budgets regionaux",
        "Demographie",
        "Analyse par habitant",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Source : [data.gouv.fr](https://www.data.gouv.fr)  \n"
    "Donnees ouvertes du gouvernement francais."
)


# ---------------------------------------------------------------------------
# Page: Vue d'ensemble
# ---------------------------------------------------------------------------

def page_overview():
    st.title("🏛️ GovSense — Vue d'ensemble")
    st.markdown(
        "Tableau de bord operationnel construit a partir des donnees ouvertes de "
        "**data.gouv.fr**. Croisement budget regional x demographie pour une "
        "analyse decisionnelle par habitant."
    )

    kpi_data = safe_query("""
        SELECT
            (SELECT COUNT(*) FROM communes) AS total_communes,
            (SELECT COUNT(DISTINCT region_code) FROM region_budgets) AS total_regions,
            (SELECT COALESCE(SUM(population), 0) FROM communes) AS total_population,
            (SELECT MIN(year) FROM region_budgets) AS min_year,
            (SELECT MAX(year) FROM region_budgets) AS max_year
    """)

    if kpi_data is None:
        st.warning("Aucune donnee disponible. Lancez le pipeline d'ingestion.")
        return

    row = kpi_data.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Communes", f"{int(row['total_communes']):,}")
    c2.metric("Regions", int(row["total_regions"]))
    c3.metric("Population totale", f"{int(row['total_population']):,}")
    c4.metric("Annees couvertes", f"{row['min_year']} – {row['max_year']}")

    st.markdown("---")

    # Revenue vs Expenditure by year
    ts = safe_query("""
        SELECT year,
               SUM(total_revenue) AS revenue,
               SUM(total_expenditure) AS expenditure
        FROM region_stats
        GROUP BY year ORDER BY year
    """)
    if ts is not None:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=ts["year"], y=ts["revenue"], name="Recettes", marker_color="#2563eb"))
        fig.add_trace(go.Bar(x=ts["year"], y=ts["expenditure"], name="Depenses", marker_color="#dc2626"))
        fig.update_layout(
            title="Recettes vs Depenses totales par annee (toutes regions)",
            barmode="group",
            xaxis_title="Annee",
            yaxis_title="Montant (EUR)",
            template="plotly_white",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Top 10 regions by revenue per capita (latest year)
    top = safe_query("""
        SELECT region_name, revenue_per_capita, expenditure_per_capita, total_population
        FROM region_stats
        WHERE year = (SELECT MAX(year) FROM region_stats)
        ORDER BY revenue_per_capita DESC
        LIMIT 10
    """)
    if top is not None:
        fig2 = px.bar(
            top,
            x="revenue_per_capita",
            y="region_name",
            orientation="h",
            title="Top 10 regions — Recette par habitant (annee la plus recente)",
            labels={"revenue_per_capita": "EUR / hab.", "region_name": ""},
            color="revenue_per_capita",
            color_continuous_scale="Blues",
        )
        fig2.update_layout(template="plotly_white", yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig2, use_container_width=True)


# ---------------------------------------------------------------------------
# Page: Carte de France
# ---------------------------------------------------------------------------

def page_map():
    st.title("🗺️ Carte de France — Donnees regionales")

    data = safe_query("""
        SELECT region_code, region_name,
               total_population, total_revenue, total_expenditure,
               revenue_per_capita, expenditure_per_capita, num_communes
        FROM region_stats
        WHERE year = (SELECT MAX(year) FROM region_stats)
    """)

    if data is None:
        st.warning("Aucune donnee de stats regionales. Lancez le pipeline.")
        return

    metric = st.selectbox("Indicateur", [
        "revenue_per_capita",
        "expenditure_per_capita",
        "total_population",
        "total_revenue",
        "total_expenditure",
        "num_communes",
    ], format_func=lambda x: {
        "revenue_per_capita": "Recette par habitant (EUR)",
        "expenditure_per_capita": "Depense par habitant (EUR)",
        "total_population": "Population totale",
        "total_revenue": "Recettes totales (EUR)",
        "total_expenditure": "Depenses totales (EUR)",
        "num_communes": "Nombre de communes",
    }.get(x, x))

    try:
        geojson = load_geojson()
    except Exception:
        st.error("Impossible de charger le GeoJSON des regions.")
        return

    fig = px.choropleth(
        data,
        geojson=geojson,
        locations="region_name",
        featureidkey="properties.nom",
        color=metric,
        hover_name="region_name",
        hover_data={
            "total_population": ":,",
            "revenue_per_capita": ":.0f",
            "expenditure_per_capita": ":.0f",
        },
        color_continuous_scale="Viridis",
        title=f"Carte des regions — {metric.replace('_', ' ').title()}",
    )
    fig.update_geos(
        fitbounds="locations",
        visible=False,
        projection_type="mercator",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=0),
        height=600,
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Data table + export
    st.subheader("Donnees")
    st.dataframe(data, use_container_width=True, hide_index=True)
    col1, col2 = st.columns(2)
    with col1:
        download_button_csv(data, "carte_regions.csv")
    with col2:
        download_button_excel(data, "carte_regions.xlsx")


# ---------------------------------------------------------------------------
# Page: Budgets regionaux
# ---------------------------------------------------------------------------

def page_budgets():
    st.title("💰 Budgets regionaux")

    years = safe_query("SELECT DISTINCT year FROM region_budgets ORDER BY year")
    if years is None:
        st.warning("Aucune donnee de budget. Lancez le pipeline.")
        return

    year_list = years["year"].tolist()
    selected_year = st.selectbox("Annee", year_list, index=len(year_list) - 1)

    data = safe_query(f"""
        SELECT region_code, region_name,
               total_revenue, total_expenditure,
               operating_revenue, operating_expenditure,
               investment_revenue, investment_expenditure, debt
        FROM region_budgets
        WHERE year = {int(selected_year)}
        ORDER BY total_revenue DESC
    """)

    if data is None or data.empty:
        st.info("Pas de donnees pour cette annee.")
        return

    # KPIs
    c1, c2, c3 = st.columns(3)
    c1.metric("Recettes totales", f"{data['total_revenue'].sum():,.0f} EUR")
    c2.metric("Depenses totales", f"{data['total_expenditure'].sum():,.0f} EUR")
    c3.metric("Dette totale", f"{data['debt'].sum():,.0f} EUR")

    st.dataframe(data, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        download_button_csv(data, f"budgets_{selected_year}.csv")
    with col2:
        download_button_excel(data, f"budgets_{selected_year}.xlsx")

    # Bar chart
    fig = px.bar(
        data,
        x="region_name",
        y=["total_revenue", "total_expenditure"],
        barmode="group",
        title=f"Recettes vs Depenses par region ({selected_year})",
        labels={"value": "EUR", "region_name": "", "variable": ""},
        color_discrete_map={
            "total_revenue": "#2563eb",
            "total_expenditure": "#dc2626",
        },
    )
    fig.update_layout(template="plotly_white", xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    # Debt chart
    if "debt" in data.columns:
        fig_debt = px.bar(
            data.sort_values("debt", ascending=False),
            x="region_name",
            y="debt",
            title=f"Encours de dette par region ({selected_year})",
            labels={"debt": "EUR", "region_name": ""},
            color="debt",
            color_continuous_scale="Reds",
        )
        fig_debt.update_layout(template="plotly_white", xaxis_tickangle=-45)
        st.plotly_chart(fig_debt, use_container_width=True)

    # Sunburst: operating vs investment
    sunburst_data = []
    for _, r in data.iterrows():
        for cat, val in [
            ("Fonctionnement", r.get("operating_expenditure", 0)),
            ("Investissement", r.get("investment_expenditure", 0)),
        ]:
            sunburst_data.append({
                "region": r["region_name"],
                "category": cat,
                "value": val or 0,
            })
    sdf = pd.DataFrame(sunburst_data)
    fig_sun = px.sunburst(
        sdf, path=["category", "region"], values="value",
        title=f"Repartition fonctionnement / investissement ({selected_year})",
    )
    st.plotly_chart(fig_sun, use_container_width=True)


# ---------------------------------------------------------------------------
# Page: Demographie
# ---------------------------------------------------------------------------

def page_demographics():
    st.title("👥 Demographie des communes")

    regions = safe_query("""
        SELECT DISTINCT region_code, region_name
        FROM communes
        WHERE region_name IS NOT NULL AND region_name != ''
        ORDER BY region_name
    """)

    if regions is None:
        st.warning("Aucune donnee de communes. Lancez le pipeline.")
        return

    region_options = ["Toutes les regions"] + regions["region_name"].tolist()
    selected = st.selectbox("Region", region_options)

    where = ""
    if selected != "Toutes les regions":
        safe_name = selected.replace("'", "''")
        where = f"WHERE region_name = '{safe_name}'"

    stats = safe_query(f"""
        SELECT region_name,
               COUNT(*) AS communes,
               SUM(population) AS population,
               ROUND(AVG(density)::numeric, 1) AS densite_moy
        FROM communes
        {where}
        GROUP BY region_name
        ORDER BY population DESC
    """)

    if stats is not None:
        st.dataframe(stats, use_container_width=True, hide_index=True)
        col1, col2 = st.columns(2)
        with col1:
            download_button_csv(stats, "demographie_regions.csv")
        with col2:
            download_button_excel(stats, "demographie_regions.xlsx")

        fig = px.treemap(
            stats,
            path=["region_name"],
            values="population",
            title="Population par region",
            color="population",
            color_continuous_scale="Viridis",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Density bar chart
        fig_dens = px.bar(
            stats.sort_values("densite_moy", ascending=False),
            x="region_name",
            y="densite_moy",
            title="Densite moyenne par region (hab/km2)",
            labels={"densite_moy": "hab/km2", "region_name": ""},
            color="densite_moy",
            color_continuous_scale="YlOrRd",
        )
        fig_dens.update_layout(template="plotly_white", xaxis_tickangle=-45)
        st.plotly_chart(fig_dens, use_container_width=True)

    # Top communes
    top_communes = safe_query(f"""
        SELECT name, region_name, department_name, population, density
        FROM communes
        {where}
        ORDER BY population DESC
        LIMIT 20
    """)
    if top_communes is not None:
        st.subheader("Top 20 communes par population")
        st.dataframe(top_communes, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Page: Analyse par habitant
# ---------------------------------------------------------------------------

def page_per_capita():
    st.title("📊 Analyse par habitant")
    st.markdown("Croisement des budgets regionaux avec la demographie communale.")

    data = safe_query("""
        SELECT year, region_code, region_name,
               total_population, total_revenue, total_expenditure,
               revenue_per_capita, expenditure_per_capita, num_communes
        FROM region_stats
        ORDER BY year, region_name
    """)

    if data is None:
        st.warning("Aucune statistique croisee. Lancez le pipeline.")
        return

    years = sorted(data["year"].unique())
    selected_year = st.selectbox("Annee", years, index=len(years) - 1)
    filtered = data[data["year"] == selected_year]

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Recette moy. par hab.",
        f"{filtered['revenue_per_capita'].mean():,.0f} EUR",
    )
    c2.metric(
        "Depense moy. par hab.",
        f"{filtered['expenditure_per_capita'].mean():,.0f} EUR",
    )
    c3.metric("Regions", len(filtered))

    st.dataframe(
        filtered.sort_values("revenue_per_capita", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
    col1, col2 = st.columns(2)
    with col1:
        download_button_csv(filtered, f"stats_par_habitant_{selected_year}.csv")
    with col2:
        download_button_excel(filtered, f"stats_par_habitant_{selected_year}.xlsx")

    # Scatter: revenue per capita vs expenditure per capita
    fig = px.scatter(
        filtered,
        x="revenue_per_capita",
        y="expenditure_per_capita",
        size="total_population",
        color="region_name",
        hover_name="region_name",
        title=f"Recette vs Depense par habitant ({selected_year})",
        labels={
            "revenue_per_capita": "Recette / hab. (EUR)",
            "expenditure_per_capita": "Depense / hab. (EUR)",
        },
    )
    fig.update_layout(template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

    # Radar chart for top 5 regions
    top5 = filtered.nlargest(5, "total_population")
    if len(top5) >= 3:
        categories = ["Recette/hab", "Depense/hab", "Population (M)", "Communes"]
        fig_radar = go.Figure()
        for _, r in top5.iterrows():
            fig_radar.add_trace(go.Scatterpolar(
                r=[
                    r["revenue_per_capita"],
                    r["expenditure_per_capita"],
                    r["total_population"] / 1_000_000,
                    r["num_communes"],
                ],
                theta=categories,
                fill="toself",
                name=r["region_name"],
            ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True)),
            title="Profil des 5 plus grandes regions",
            template="plotly_white",
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    # Evolution over time
    st.markdown("---")
    st.subheader("Evolution temporelle")
    region_list = sorted(data["region_name"].dropna().unique())
    if region_list:
        selected_region = st.selectbox("Region", region_list)
        region_data = data[data["region_name"] == selected_region]

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=region_data["year"], y=region_data["revenue_per_capita"],
            mode="lines+markers", name="Recette / hab.",
            line=dict(color="#2563eb"),
        ))
        fig2.add_trace(go.Scatter(
            x=region_data["year"], y=region_data["expenditure_per_capita"],
            mode="lines+markers", name="Depense / hab.",
            line=dict(color="#dc2626"),
        ))
        fig2.update_layout(
            title=f"Evolution — {selected_region}",
            xaxis_title="Annee",
            yaxis_title="EUR / habitant",
            template="plotly_white",
        )
        st.plotly_chart(fig2, use_container_width=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

PAGES = {
    "Vue d'ensemble": page_overview,
    "Carte de France": page_map,
    "Budgets regionaux": page_budgets,
    "Demographie": page_demographics,
    "Analyse par habitant": page_per_capita,
}

PAGES[page]()
