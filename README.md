# GovSense

**Intelligence operationnelle sur les donnees publiques gouvernementales.**

GovSense transforme les open data de [data.gouv.fr](https://www.data.gouv.fr) en dashboards decisionnels interactifs. Il ingere, nettoie, croise et visualise les donnees publiques pour faciliter la prise de decision.

---

## Cas d'usage

- **Collectivites territoriales** : comparer les budgets regionaux et identifier les ecarts de depenses par habitant.
- **Analystes politiques** : croiser budget, demographie et emploi pour mesurer l'effort financier par region.
- **Journalistes data** : explorer les finances publiques regionales avec des visualisations interactives et des cartes.
- **Chercheurs** : acceder a des donnees normalisees via une API REST structuree avec export CSV/Excel.

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
                                                    │ FastAPI │          │ Streamlit │     │  Export   │
                                                    │ REST API│          │ Dashboard │     │ CSV/Excel │
                                                    └─────────┘          └───────────┘     └───────────┘
```

### Datasets utilises

| Dataset | Source | Description |
|---------|--------|-------------|
| Comptes individuels des regions | Ministere de l'Economie | Budget regional (recettes, depenses, dette) |
| Communes de France | data.gouv.fr | Demographie communale (population, superficie, densite) |
| Masse salariale et chomage partiel | Urssaf | Emploi regional (masse salariale, chomage partiel) |

### Pipeline ETL

1. **Ingestion** : telechargement des CSV via l'API data.gouv.fr
2. **Nettoyage** : normalisation des colonnes, deduplication, gestion des valeurs manquantes
3. **Transformation** : agregation par region, calcul des totaux, croisement budget x demographie
4. **Stockage** : insertion dans PostgreSQL (tables: `region_budgets`, `communes`, `region_stats`, `region_employment`)

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| API REST | FastAPI + Pydantic |
| Base de donnees | PostgreSQL 16 |
| Migrations | Alembic |
| Traitement de donnees | Pandas |
| Dashboard | Streamlit + Plotly |
| Carte interactive | Plotly Choropleth (GeoJSON) |
| Authentification | API Key (optionnelle) |
| Cache | In-memory TTL cache |
| Scheduler | APScheduler (rafraichissement auto) |
| CI/CD | GitHub Actions |
| Linting | Ruff + pre-commit |
| Deploiement | Docker + Docker Compose |
| Tests | Pytest (unitaires + integration) |

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
# API REST       : http://localhost:8000
# API Docs       : http://localhost:8000/docs
# Dashboard      : http://localhost:8501
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
# Tous les tests
pytest tests/ -v

# Ou via Make
make test
```

### Commandes Make disponibles

```bash
make help        # Afficher toutes les commandes
make install     # Installer les dependances
make api         # Demarrer l'API FastAPI
make dashboard   # Demarrer le dashboard Streamlit
make pipeline    # Lancer le pipeline ETL
make test        # Lancer les tests
make lint        # Linter avec ruff
make format      # Formater avec ruff
make up          # Docker compose up
make down        # Docker compose down
make ingest      # Lancer le pipeline via Docker
make db-migrate  # Appliquer les migrations Alembic
```

---

## Configuration

| Variable d'environnement | Description | Defaut |
|--------------------------|-------------|--------|
| `DATABASE_URL` | URL de connexion PostgreSQL | `postgresql://govsense:govsense@localhost:5432/govsense` |
| `GOVSENSE_API_KEY` | Cle API (si vide, mode ouvert) | _(non defini)_ |
| `GOVSENSE_SCHEDULE_INTERVAL` | Intervalle de rafraichissement en heures | _(non defini)_ |

---

## Endpoints API

| Methode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/` | Info du service |
| `GET` | `/api/v1/health` | Health check + status DB |
| `GET` | `/api/v1/datasets` | Liste des datasets ingeres |
| `GET` | `/api/v1/budgets` | Budgets regionaux (filtres: `year`, `region_code`) |
| `GET` | `/api/v1/communes` | Communes (filtres: `region_code`, `department_code`, `search`) |
| `GET` | `/api/v1/employment` | Emploi regional (filtres: `region_code`, `month`) |
| `GET` | `/api/v1/stats/regions` | KPIs par region (budget x demographie) |
| `GET` | `/api/v1/kpis` | KPIs globaux |
| `GET` | `/api/v1/metrics` | Metriques applicatives (uptime, requetes) |
| `GET` | `/api/v1/export/budgets` | Export CSV des budgets |
| `GET` | `/api/v1/export/stats` | Export CSV des stats regionales |
| `POST` | `/api/v1/cache/clear` | Vider le cache |

Documentation interactive : [http://localhost:8000/docs](http://localhost:8000/docs)

### Authentification API

Par defaut, l'API est ouverte. Pour activer l'authentification par cle API :

```bash
export GOVSENSE_API_KEY=your-secret-key
```

Puis ajoutez le header `X-API-Key: your-secret-key` a vos requetes.

---

## Dashboard

Le dashboard Streamlit propose 5 vues :

- **Vue d'ensemble** : KPIs globaux, recettes vs depenses par annee, top regions
- **Carte de France** : choropleth interactif avec selection d'indicateur
- **Budgets regionaux** : detail par annee, sunburst fonctionnement/investissement
- **Demographie** : treemap population, densite, top communes
- **Analyse par habitant** : scatter plot, radar chart, evolution temporelle

Chaque vue inclut des boutons d'export CSV et Excel.

<!-- Screenshots -->
<!-- ![Vue d'ensemble](docs/screenshots/overview.png) -->
<!-- ![Carte de France](docs/screenshots/map.png) -->
<!-- ![Analyse par habitant](docs/screenshots/per_capita.png) -->

---

## Structure du projet

```
GovSense/
├── README.md
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── ruff.toml
├── alembic.ini
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── pipeline.py             # Pipeline ETL complet
│   ├── scheduler.py            # Rafraichissement automatique
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── data_gouv.py        # Client API data.gouv.fr
│   │   └── datasets.py         # Registre des datasets
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── cleaner.py          # Nettoyage et normalisation
│   │   └── transformer.py      # Croisement et agregation
│   ├── storage/
│   │   ├── __init__.py
│   │   └── database.py         # Models SQLAlchemy + config DB
│   └── api/
│       ├── __init__.py
│       ├── auth.py             # Authentification API key
│       ├── cache.py            # Cache in-memory TTL
│       ├── schemas.py          # Schemas Pydantic
│       └── routes.py           # Endpoints REST
├── dashboard/
│   ├── __init__.py
│   ├── app.py                  # Dashboard Streamlit
│   └── geo.py                  # GeoJSON et mapping regions
└── tests/
    ├── __init__.py
    ├── test_pipeline.py        # Tests unitaires pipeline
    ├── test_api.py             # Tests integration API
    └── test_auth_cache.py      # Tests auth + cache
```

---

## Licence

MIT
