# Niveau d'eau - Puech des Ouilhes

Outil de surveillance du niveau d'eau de la mise à l'eau du **Puech des Ouilhes** sur le lac de barrage de **Saint-Étienne-Cantalès** (Cantal, France).

## Fonctionnalités

- Récupération automatique des niveaux d'eau depuis l'API Niv'eau d'EDF
- Historisation dans une base SQLite locale
- Agrégation multi-échelle (24h, 7j, 30j, 1 an)
- Dashboard GitHub Pages avec graphique interactif (zoom/pan type Grafana)
- Alertes email si le niveau dépasse 498 mNGF ou descend sous 501 mNGF

## Installation

```bash
git clone <repo>
cd niveau-puech-ouilhes
python scripts/fetch_levels.py --backfill
```

## Utilisation

### Exécution manuelle
```bash
python scripts/fetch_levels.py
```

### Backfill initial (30 et 365 jours)
```bash
python scripts/fetch_levels.py --backfill
```

### Configuration des alertes email
Définissez les variables d'environnement :
- `SMTP_HOST` (défaut: smtp.gmail.com)
- `SMTP_PORT` (défaut: 587)
- `SMTP_USER`
- `SMTP_PASS`
- `ALERT_EMAIL`

## GitHub Actions

- **fetch.yml** : exécution toutes les heures, commit des données, envoi d'email si alerte
- **pages.yml** : déploiement du dashboard sur GitHub Pages

### Secrets requis
Dans les paramètres du repo GitHub, ajoutez les secrets :
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `ALERT_EMAIL`

## Structure

```
.
├── .github/workflows/
├── data/levels.db          # Base SQLite (historique)
├── docs/                   # GitHub Pages
│   ├── index.html
│   └── data/               # JSON exports
├── scripts/fetch_levels.py
├── config.py
└── requirements.txt
```

## Dashboard

Le dashboard est accessible via GitHub Pages. Il permet de naviguer entre les périodes (24h, 7j, 30j, 1 an) et de zoomer/panner sur le graphique.