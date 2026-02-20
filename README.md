# GovSense

**Intelligence operationnelle sur les donnees publiques gouvernementales.**

GovSense transforme les open data de [data.gouv.fr](https://www.data.gouv.fr) en dashboards decisionnels interactifs. Il ingere, nettoie, croise et visualise les donnees publiques pour faciliter la prise de decision.

---

## Cas d'usage

- **Collectivites territoriales** : comparer les budgets regionaux et identifier les ecarts de depenses par habitant.
- **Analystes politiques** : croiser budget et demographie pour mesurer l'effort financier par region.
- **Journalistes data** : explorer les finances publiques regionales avec des visualisations interactives.
- **Chercheurs** : acceder a des donnees normalisees via une API REST structuree.

---

## Architecture pipeline

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌──────────────┐
│   data.gouv.fr  │────▸│    Ingestion    │────▸│   Processing    │────▸│  PostgreSQL  │
│   (Open Data)   │     │  (HTTP + CSV)   │     │ Clean+Transform │     │   Storage    │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └──────┬───────┘
                                                                               │
                                                         ┌─────────────────────┼──────────────────┐
                                                         │                     │                  │
                                                    ┌────▸────┐          ┌─────▸─────┐     ┌─────▸─────┐
                                                    │ FastAPI │          │ Streamlit │     │   SQL     │
                                                    │ REST API│          │ Dashboard │     │  Queries  │
                                                    └─────────┘          └───────────┘     └───────────┘
```

### Datasets utilises

| Dataset | Source | Description |
|---------|--------|-------------|
| Comptes individuels des regions | Ministere de l'Economie | Budget regional (recettes, depenses, dette) |
| Communes de France | data.gouv.fr | Demographie communale (population, superficie, densite) |

### Pipeline ETL

1. **Ingestion** : telechargement des CSV via l'API data.gouv.fr
2. **Nettoyage** : normalisation des colonnes, deduplication, gestion des valeurs manquantes
3. **Transformation** : agregation par region, calcul des totaux, croisement budget x demographie
4. **Stockage** : insertion dans PostgreSQL (tables: `region_budgets`, `communes`, `region_stats`)

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| API REST | FastAPI |
| Base de donnees | PostgreSQL 16 |
| Traitement de donnees | Pandas |
| Dashboard | Streamlit + Plotly |
| Deploiement | Docker + Docker Compose |
| Tests | Pytest |

---

## Installation

### Prerequis

- Docker et Docker Compose
- (Optionnel) Python 3.11+ pour le developpement local

### Demarrage rapide avec Docker

```bash
# Cloner le projet
git clone https://github.com/nicovlr/project-03.git
cd project-03

# Demarrer la base de donnees, l'API et le dashboard
docker compose up -d

# Lancer le pipeline d'ingestion (telechargement + traitement + stockage)
docker compose --profile ingest run --rm pipeline

# Acceder aux services
# API REST     : http://localhost:8000
# API Docs     : http://localhost:8000/docs
# Dashboard    : http://localhost:8501
```

### Developpement local (sans Docker)

```bash
# Installer les dependances
pip install -r requirements.txt

# Configurer la base de donnees
export DATABASE_URL=postgresql://govsense:govsense@localhost:5432/govsense

# Lancer le pipeline
python -m app.pipeline

# Demarrer l'API
uvicorn app.main:app --reload

# Demarrer le dashboard (dans un autre terminal)
streamlit run dashboard/app.py
```

### Lancer les tests

```bash
pytest tests/ -v
```

---

## Endpoints API

| Methode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/` | Info du service |
| `GET` | `/api/v1/health` | Health check + status DB |
| `GET` | `/api/v1/datasets` | Liste des datasets ingeres |
| `GET` | `/api/v1/budgets` | Budgets regionaux (filtres: `year`, `region_code`) |
| `GET` | `/api/v1/communes` | Communes (filtres: `region_code`, `department_code`, `search`) |
| `GET` | `/api/v1/stats/regions` | KPIs par region (budget x demographie) |
| `GET` | `/api/v1/kpis` | KPIs globaux |

Documentation interactive : [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Dashboard

Le dashboard Streamlit propose 4 vues :

- **Vue d'ensemble** : KPIs globaux, recettes vs depenses par annee, top regions
- **Budgets regionaux** : detail par annee avec graphiques interactifs
- **Demographie** : treemap population, top communes, filtrage par region
- **Analyse par habitant** : scatter plot recette/depense per capita, evolution temporelle

<!-- Screenshots -->
<!-- ![Vue d'ensemble](docs/screenshots/overview.png) -->
<!-- ![Budgets](docs/screenshots/budgets.png) -->
<!-- ![Analyse par habitant](docs/screenshots/per_capita.png) -->

---

## Structure du projet

```
GovSense/
├── README.md
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── pipeline.py          # Pipeline ETL complet
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── data_gouv.py     # Client API data.gouv.fr
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── cleaner.py       # Nettoyage et normalisation
│   │   └── transformer.py   # Croisement et agregation
│   ├── storage/
│   │   ├── __init__.py
│   │   └── database.py      # Models SQLAlchemy + config DB
│   └── api/
│       ├── __init__.py
│       └── routes.py         # Endpoints REST
├── dashboard/
│   └── app.py                # Dashboard Streamlit
└── tests/
    └── test_pipeline.py      # Tests unitaires pipeline
```

---

## Licence

MIT
