# Contexte projet - Analyse des votes Assemblee Nationale

## Description
Dashboard Streamlit d'analyse des votes publics de l'Assemblee Nationale (17e legislature).
Repo GitHub : https://github.com/piouscott/assemblee

## Architecture / Pipeline

```
download_data.py  ->  Telecharge les ZIP depuis data.assemblee-nationale.fr
parse_data.py     ->  Parse JSON -> 4 CSV (scrutins, votes_par_groupe, votes_nominatifs, acteurs)
enrich_amendements.py -> Match scrutins <-> amendements -> scrutins_amendements.csv
classify_themes.py    -> Classifie chaque scrutin -> themes.csv
                         (theme, impact, confiance, doctrine_eco, classe_sociale, loi_parente)
app.py                -> Dashboard Streamlit (7 pages)
```

## Fichiers principaux

- **`classify_themes.py`** (~700 lignes) : moteur de classification par mots-cles
  - `classify_theme()` : 18 themes
  - `classify_impact()` : Progressif/Restrictif/Neutre + confiance
  - `classify_doctrine_eco()` : Liberal/Interventionniste/Social/Austerite/Mixte/Non economique
  - `classify_classe_sociale()` : Populaires/Moyennes/Aisees-Entreprises/Universel/Non determine
  - `extract_loi_parente()` : extrait le nom de la loi depuis le titre
  - `_strip_loi_from_titre()` : fonction partagee qui retire le nom de la loi parente du titre des amendements avant matching

- **`app.py`** (~1200+ lignes) : dashboard Streamlit, 7 pages :
  1. Vue d'ensemble
  2. Par parti
  3. Impact social
  4. Economie (doctrines + score pro-populaire normalise)
  5. Par loi (vue hierarchique)
  6. Axe politique (score gauche-droite)
  7. Comparaison (matrice d'alignement)
  + Page "Par scrutin" (detail)

- **`METHODOLOGIE.md`** : documentation complete de toutes les methodes, formules et biais

## Decisions techniques importantes

### Filtrage du nom de la loi dans le titre
Pour les amendements, le nom de la loi parente est retire du titre avant le matching des mots-cles (impact, doctrine, classe sociale). Sans ca, tous les amendements d'une loi heritent de la classification de son nom.

### Mecanisme de negation Liberal
`_LIBERAL_NEGATION_RE` detecte les patterns "supprimer/abroger/plafonner... exoneration/credit d'impot/niche..."
-> penalise le score Liberal et bonifie Interventionniste. Evite que les amendements de gauche qui veulent supprimer des avantages fiscaux soient classes Liberal.

### Score pro-populaire normalise (page Economie)
- Probleme : les % POUR bruts sont biaises par la dynamique majorite/opposition
- Solution : score directionnel (POUR si Progressif, CONTRE si Restrictif) normalise par scrutin (deviation vs moyenne chambre)
- Resultats coherents : LFI (+16.6) > EcoS (+16.1) > ... > EPR (-9.7) > HOR (-10.5)

### Mots-cles retires de Liberal
- `exoneration`, `credit d'impot` : bidirectionnels (creation ET suppression)
- `concurrence` seul : trop large, remplace par formes contextuelles
- `dereglement` : matchait "dereglement climatique"
- `simplification` seul : matchait le nom de la loi "simplification de la vie economique"

## Donnees

Repertoire `data/` (gitignore). Pour regenerer :
```bash
python download_data.py
python parse_data.py
python enrich_amendements.py
python classify_themes.py
streamlit run app.py
```

CSV generes dans `data/` :
- `scrutins.csv`, `votes_par_groupe.csv`, `votes_nominatifs.csv`, `acteurs.csv`
- `scrutins_amendements.csv`
- `themes.csv`

## Limitations connues

- LFI a ~47% sur Liberal (bruit residuel du vocabulaire fiscal bidirectionnel)
- ~15% des scrutins ne matchent pas un amendement
- ~60% des scrutins sont "Non economique"
- ~72% des scrutins ont classe_sociale = "Non determine"
- Le groupe de l'auteur n'est PAS utilise pour la classification (eviter biais circulaire)

## Etat actuel (5 mars 2026)

- Toutes les pages du dashboard sont implementees et fonctionnelles
- Definitions/explications ajoutees dans le dashboard (st.expander)
- METHODOLOGIE.md a jour
- 2 commits pushes sur main
- Pas de taches en cours
