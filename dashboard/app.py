"""GovSense — Streamlit interactive dashboard."""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine, text

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


def query_df(sql: str) -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("🏛️ GovSense")
st.sidebar.markdown("**Intelligence operationnelle**  \nDonnees publiques → Decisions")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["Vue d'ensemble", "Budgets regionaux", "Demographie", "Analyse par habitant"],
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "Source: [data.gouv.fr](https://www.data.gouv.fr)  \n"
    "Donnees ouvertes du gouvernement francais."
)


# ---------------------------------------------------------------------------
# Helper: safe query
# ---------------------------------------------------------------------------

def safe_query(sql: str) -> pd.DataFrame | None:
    try:
        df = query_df(sql)
        return df if not df.empty else None
    except Exception as exc:
        st.error(f"Erreur de connexion a la base de donnees : {exc}")
        return None


# ---------------------------------------------------------------------------
# Page: Vue d'ensemble
# ---------------------------------------------------------------------------

def page_overview():
    st.title("🏛️ GovSense — Vue d'ensemble")
    st.markdown(
        "Tableau de bord operationnel construit a partir des donnees ouvertes de "
        "**data.gouv.fr**. Croisement budget regional × demographie pour une "
        "analyse decisionnelle par habitant."
    )

    # KPIs
    kpi_data = safe_query("""
        SELECT
            (SELECT COUNT(*) FROM communes) AS total_communes,
            (SELECT COUNT(DISTINCT region_code) FROM region_budgets) AS total_regions,
            (SELECT COALESCE(SUM(population), 0) FROM communes) AS total_population,
            (SELECT MIN(year) FROM region_budgets) AS min_year,
            (SELECT MAX(year) FROM region_budgets) AS max_year
    """)

    if kpi_data is not None:
        row = kpi_data.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Communes", f"{int(row['total_communes']):,}")
        c2.metric("Regions", int(row["total_regions"]))
        c3.metric("Population totale", f"{int(row['total_population']):,}")
        c4.metric("Annees couvertes", f"{row['min_year']} – {row['max_year']}")
    else:
        st.warning("Aucune donnee disponible. Lancez le pipeline d'ingestion.")
        return

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

    st.dataframe(data, use_container_width=True, hide_index=True)

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

        fig = px.treemap(
            stats,
            path=["region_name"],
            values="population",
            title="Population par region",
            color="population",
            color_continuous_scale="Viridis",
        )
        st.plotly_chart(fig, use_container_width=True)

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

    # Evolution over time for selected region
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
    "Budgets regionaux": page_budgets,
    "Demographie": page_demographics,
    "Analyse par habitant": page_per_capita,
}

PAGES[page]()
