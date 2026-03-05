# Methodologie - Analyse des votes de l'Assemblee Nationale

## Table des matieres

1. [Pipeline de donnees](#1-pipeline-de-donnees)
2. [Classification thematique](#2-classification-thematique)
3. [Classification de l'impact social](#3-classification-de-limpact-social)
4. [Classification economique](#4-classification-economique)
5. [Extraction de la loi parente](#5-extraction-de-la-loi-parente)
6. [Enrichissement par les amendements](#6-enrichissement-par-les-amendements)
7. [Pages du dashboard et formules](#7-pages-du-dashboard-et-formules)

---

## 1. Pipeline de donnees

### Sources

Toutes les donnees proviennent de l'Open Data de l'Assemblee Nationale (17e legislature) :
- **Scrutins** : tous les votes publics en hemicycle
- **Acteurs / Organes** : deputes, groupes politiques, commissions
- **Amendements** : textes des amendements avec leurs auteurs et exposes des motifs

### Etapes du pipeline

```
[download_data.py]  Telecharge les ZIP depuis data.assemblee-nationale.fr
        |
[parse_data.py]     Parse les JSON -> 4 CSV :
        |              - scrutins.csv (1 ligne par scrutin)
        |              - votes_par_groupe.csv (1 ligne par scrutin x groupe)
        |              - votes_nominatifs.csv (1 ligne par scrutin x depute)
        |              - acteurs.csv (mapping depute -> nom)
        |
[enrich_amendements.py]  Match scrutins <-> amendements -> scrutins_amendements.csv
        |
[classify_themes.py]     Classifie chaque scrutin -> themes.csv
        |                   (theme, impact, doctrine_eco, classe_sociale, loi_parente)
        |
[app.py]                 Dashboard Streamlit
```

### Colonnes principales

| CSV | Colonnes cles |
|-----|---------------|
| scrutins.csv | scrutin_uid, titre, date, sort, nb_votants, total_pour/contre/abstentions |
| votes_par_groupe.csv | scrutin_uid, groupe_abrege, position_majoritaire, pour, contre, abstentions |
| scrutins_amendements.csv | scrutin_uid, amdt_numero, amdt_groupe_abrege, amdt_expose, amdt_signataires |
| themes.csv | scrutin_uid, theme, impact, confiance, doctrine_eco, classe_sociale, loi_parente |

---

## 2. Classification thematique

### Methode
Classification par **mots-cles dans le titre** du scrutin. Le titre est compare a 18 listes de patterns regex. Le theme avec le plus de correspondances l'emporte.

### Themes (18 categories)

| Theme | Exemples de mots-cles | Nb patterns |
|-------|----------------------|-------------|
| Emploi / Travail | emploi, travail, chomage, retraite, licenciement | 18 |
| Sante | sante, hopital, medecin, PLFSS, assurance maladie | 13 |
| Securite / Justice | securite, justice, police, terrorisme, narcotrafic | 13 |
| Education / Recherche | education, scolaire, universite, lycee | 11 |
| Environnement / Energie | climat, energie, nucleaire, biodiversite | 14 |
| Budget / Finances | budget, fiscal, impot, PLF, dette, TVA | 11 |
| Immigration | immigration, asile, etranger, frontiere | 8 |
| Europe / International | europeen, international, OTAN, Ukraine | 10 |
| Agriculture / Alimentation | agricole, PAC, elevage, viticole | 9 |
| Logement / Urbanisme | logement, loyer, HLM, APL, locataire | 11 |
| Culture / Medias | culture, audiovisuel, patrimoine, cinema | 10 |
| Numerique / Donnees | numerique, internet, IA, cyber | 8 |
| Transports / Infrastructures | transport, SNCF, autoroute, mobilite | 9 |
| Defense / Armee | defense, armee, militaire, LPM | 7 |
| Institutions / Constitution | constitution, referendum, 49.3, motion de censure | 12 |
| Social / Solidarite | solidarite, handicap, pauvrete, RSA, egalite | 13 |
| Outre-mer | Mayotte, Guadeloupe, Nouvelle-Caledonie | 10 |
| Procedure parlementaire | motion de rejet, question prealable, irrecevabilite | 10 |

**Score** : nombre de patterns qui matchent dans le titre. Le theme avec le score le plus eleve gagne. Si aucun match : "Autre".

---

## 3. Classification de l'impact social

### Objectif
Determiner si un scrutin est **Progressif** (etend des droits, augmente des aides, protege) ou **Restrictif** (reduit des droits, durcit, coupe des aides).

### Systeme a 2 signaux textuels

La classification combine 2 sources d'information **purement textuelles**. Le groupe politique de l'auteur n'est volontairement pas utilise comme signal, afin d'eviter un biais circulaire (on ne peut pas presupposer que gauche = progressif et droite = restrictif alors que c'est ce qu'on cherche a mesurer).

#### Signal 1 : Titre du scrutin
- ~24 patterns progressistes : "visant a proteger", "revalorisation", "pouvoir d'achat", "acces aux soins", etc.
- ~22 patterns restrictifs : "durcir", "reduction deficit", "maitrise depense", "surveillance", etc.
- **Inversion** : si le titre contient "amendement de suppression" ou "motion de rejet", le sens est inverse (supprimer un article progressiste = geste restrictif)
- **Filtrage du nom de la loi parente** : pour les amendements ordinaires (hors suppressions), le nom de la loi parente est retire du titre avant le matching. Cela evite de deduire l'impact d'un amendement a partir du nom de la loi (ex: "amendement n° X de la proposition de loi relative au **droit** a l'aide a mourir" ne doit pas etre classe Progressif juste parce que le nom de la loi contient "droit"). Pour les amendements de suppression, le nom est conserve car il est necessaire a la logique d'inversion.
- Score : nombre de patterns qui matchent. La categorie avec le plus haut score gagne.

#### Signal 2 : Expose des motifs + dispositif de l'amendement
- ~60 patterns progressistes : "justice sociale", "solidarite", "droit fondamental", "taxe superprofits", "vise a garantir", "vise a renforcer", "plus vulnerables", "classes populaires", "dignite", "conditions de travail", etc.
- ~45 patterns restrictifs : "maitrise depense", "competitivite", "liberalisation", "flexibilite travail", "depense publique", "effort budgetaire", "rationalisation", "vise a restreindre", "vise a limiter", etc.
- Le texte analyse est la concatenation de l'expose des motifs et du dispositif (texte juridique de l'amendement), ce qui augmente les chances de capter un signal.
- Meme logique de score que le signal 1.

### Fusion des signaux

```
Collecter les signaux non-neutres (titre et expose).

Si les 2 concordent (ex: 2x Progressif) :
  -> Impact = ce signal, Confiance = haute

Si les 2 divergent (1 Progressif, 1 Restrictif) :
  -> Impact = expose (contenu reel priorise), Confiance = moyenne

Si un seul signal non-neutre :
  -> Impact = ce signal, Confiance = basse

Si aucun signal :
  -> Impact = Neutre, Confiance = basse
```

### Niveaux de confiance

| Confiance | Condition |
|-----------|-----------|
| **Haute** | 2 signaux et tous concordent |
| **Moyenne** | 2 signaux mais divergents (expose priorise) |
| **Basse** | Un seul signal disponible |

---

## 4. Classification economique

### 4a. Doctrine economique

Chaque scrutin est classe parmi : **Liberal**, **Interventionniste**, **Social**, **Austerite**, **Mixte** ou **Non economique**.

#### Filtrage prealable du titre

Comme pour l'impact social (section 3), le **nom de la loi parente est retire du titre** des amendements avant le matching des mots-cles. Cela evite que tous les amendements d'une loi heritent de la doctrine de son nom (ex: "loi de simplification de la vie economique" classait 431 amendements comme Liberal, meme ceux qui ajoutaient des protections).

#### Mots-cles par doctrine

| Doctrine | Mots-cles principaux | Nb patterns |
|----------|---------------------|-------------|
| **Liberal** | simplification (administrative/normes/demarches), allegement charges, competitivite, privatisation, liberalisation, flexibilite travail, attractivite, reduction cotisation, baisse impot, dereglementation, suppression taxe/impot, defiscalisation, libre-echange, ouverture/libre/mise en concurrence | ~20 |
| **Interventionniste** | nationalisation, regulation, encadrement prix, controle/intervention Etat, service public, secteur strategique, planification, bien commun, taxe superprofits, **+ contre-signaux** : supprimer exoneration/credit impot/niche, augmenter/hausser impot/taxe, creation taxe, contribution exceptionnelle, progressivite impot, justice fiscale | ~30 |
| **Social** | revalorisation SMIC, pouvoir d'achat, protection locataire, allocation chomage, justice sociale, solidarite, gratuite, minima sociaux, securite sociale, droit a l'(education/logement/...) | ~21 |
| **Austerite** | maitrise depense, reduction deficit, equilibre budgetaire, discipline, reduction dette, economies budgetaires, trajectoire finances publiques | ~14 |

#### Mots-cles retires (trop ambigus)

- **`exoneration`** et **`credit d'impot`** : retires de la liste Liberal car **bidirectionnels**. Un amendement de gauche qui propose de "supprimer l'exoneration de cotisations patronales" mentionne "exoneration" dans l'expose, mais son intention est interventionniste, pas liberale. Ces termes apparaissent autant dans les textes qui creent un mecanisme fiscal que dans ceux qui le suppriment.
- **`concurrence`** (seul) : remplace par des formes contextuelles (`ouverture a la concurrence`, `libre concurrence`, `mise en concurrence`). Le mot seul matchait 524 exposes dont 89% n'etaient pas dans un contexte liberal (ex: "lutte contre la concurrence deloyale" = interventionniste).
- **`dereglement`** : remplace par `dereglementation` car "dereglement" matchait "dereglement climatique".
- **`simplification`** (seul) : remplace par des formes contextuelles (simplification administrative/normes/demarches/reglementation/bureaucratie).

#### Mecanisme de negation Liberal

Quand l'expose mentionne la **suppression ou limitation** d'un mecanisme liberal, le score Liberal est penalise :

```
Patterns de negation detectes :
  "supprimer/abroger/plafonner/mettre fin/reduire/limiter/encadrer"
  suivi de (dans les 30 caracteres) :
  "exoneration / credit d'impot / niche / allegement / avantage fiscal"

Pour chaque negation trouvee :
  score_Liberal -= 2
  score_Interventionniste += 2

Effet : un amendement qui dit "supprimer l'exoneration de cotisations
patronales" ne sera plus classe Liberal.
```

#### Scoring

```
Pour chaque doctrine :
  score = 0
  Pour chaque mot-cle :
    Si match dans le TITRE (sans nom de loi) -> score += 2 (titre compte double)
    Si match dans l'EXPOSE+DISPOSITIF        -> score += 1

Appliquer les penalites de negation (Liberal -> Interventionniste)

Si aucun score > 0 -> "Non economique"
Si une seule doctrine a le max -> cette doctrine
Si 2+ doctrines ex aequo au max -> "Mixte"
```

#### Resultats

| Doctrine | Nb scrutins | Nb initial (avant corrections) |
|----------|-------------|-------------------------------|
| Non economique | ~3500 | ~2400 |
| Interventionniste | ~980 | ~410 |
| Social | ~660 | ~1420 |
| Mixte | ~375 | ~330 |
| Liberal | ~220 | ~1130 |
| Austerite | ~50 | ~40 |

### 4b. Classe sociale visee

Chaque scrutin est classe selon la population visee : **Populaires**, **Moyennes**, **Aisees/Entreprises**, **Universel** ou **Non determine**.

Le **nom de la loi parente est retire du titre** avant matching (meme filtre que pour la doctrine).

| Classe | Mots-cles principaux | Nb patterns |
|--------|---------------------|-------------|
| **Populaires** | precaire, chomeur, travailleur pauvre, bas salaire, handicap, RSA, sans-abri, CDD, saisonnier | 19 |
| **Moyennes** | PME, artisan, commercant, profession liberale, auto-entrepreneur, TPE | 14 |
| **Aisees/Entreprises** | grande entreprise, multinationale, investisseur, actionnaire, fortune, haut revenu, superprofits | 16 |
| **Universel** | tous les citoyens, universalite, egalite des droits, droits fondamentaux, bien commun | 10 |

**Scoring** : identique a la doctrine (titre sans nom de loi x2 + expose x1). La classe avec le score max gagne.

---

## 5. Extraction de la loi parente

### Methode
5 expressions regulieres testees dans l'ordre sur le titre du scrutin :

1. `projet de loi de/d'/portant/relatif/organique...`
2. `proposition de loi visant a/relative a/portant...`
3. `projet de loi X` (sans qualificatif)
4. `proposition de loi X` (sans qualificatif)
5. `proposition de resolution X`

### Post-traitement
- Suppression des parentheses et contenu apres
- Suppression des mentions "premiere/deuxieme/troisieme lecture"
- Seuil minimum de 10 caracteres (evite les faux positifs)

---

## 6. Enrichissement par les amendements

### Matching scrutin <-> amendement

Le titre d'un scrutin mentionne souvent "l'amendement n° X de M./Mme Y". Le matching procede ainsi :

1. **Extraction du numero** : regex `amendement.*?n[°o\s]+(\d+)` dans le titre
2. **Extraction de l'auteur** : regex pour "de M. Nom", "de Mme Nom", "du Gouvernement"
3. **Recherche dans l'index** : tous les amendements avec ce numero

### Priorite seance vs commission

Un meme numero d'amendement peut exister en commission (CL37, CF37...) et en hemicycle (37). Les scrutins etant des votes en seance, on priorise :

```
1. Amendements de seance (prefixeOrganeExamen = "AN") -> prioritaires
2. Amendements de commission (CL, CF, AS, CS...) -> fallback

Parmi les amendements de seance :
  -> Si le nom de l'auteur du titre correspond a un acteur -> match par auteur
  -> Sinon -> premier amendement de seance disponible
```

### Donnees recuperees par amendement
- `amdt_numero` : numero long (ex: "37", "CL37")
- `amdt_groupe_abrege` : groupe politique de l'auteur (ex: "LFI-NFP", "UDR")
- `amdt_expose` : expose des motifs (texte brut complet, sans troncature)
- `amdt_dispositif` : texte du dispositif (complet, sans troncature)
- `amdt_signataires` : libelle des signataires (complet, sans troncature)

---

## 7. Pages du dashboard et formules

### Position gauche-droite des partis

Les calculs utilisent des poids fixes pour chaque parti :

| Parti | Position | Interpretation |
|-------|----------|----------------|
| LFI-NFP | -1.0 | Gauche |
| GDR | -0.85 | Gauche |
| EcoS | -0.7 | Gauche |
| SOC | -0.6 | Gauche |
| LIOT | 0.0 | Transversal |
| Dem | +0.3 | Centre-droit |
| EPR | +0.4 | Droite |
| HOR | +0.5 | Droite |
| AD | +0.7 | Droite |
| UDR | +0.75 | Droite |
| DR | +0.8 | Droite |
| RN | +0.9 | Droite |
| NI | 0.0 | Non classe |

### Formule commune : % vote POUR

Utilisee dans presque toutes les pages :

```
pct_pour = votes_pour / (votes_pour + votes_contre + abstentions) * 100
```

Quand on groupe par (parti, dimension) :

```
pct_pour = SUM(pour) / MAX(SUM(pour) + SUM(contre) + SUM(abstentions), 1) * 100
```

---

### Page "Vue d'ensemble"

| Element | Calcul |
|---------|--------|
| Nombre de scrutins | `len(scrutins)` |
| Adoptes | `(sort == "adopte").sum()` |
| Rejetes | `(sort in ["rejete", "rejeté"]).sum()` |
| Timeline par mois | Regroupement par mois, comptage |
| Repartition par theme | Camembert des `theme.value_counts()` |
| Types de votes | Bar chart des `libelle_type_vote.value_counts()` |

---

### Page "Par parti"

| Element | Calcul |
|---------|--------|
| Barres empilees | Pour chaque parti : `pct_pour`, `pct_contre`, `pct_abstentions` (somme = 100%) |
| Heatmap theme x parti | Pour chaque (theme, parti) : `pct_pour` = SUM(pour) / SUM(pour+contre+abstentions) * 100 |

**Heatmap** : echelle de couleur RdYlGn (rouge = faible % pour, vert = eleve).

---

### Page "Impact social"

| Element | Calcul |
|---------|--------|
| Filtre confiance | Multiselect parmi [haute, moyenne, basse] |
| Filtre groupe auteur | Multiselect parmi les `amdt_groupe_abrege` non vides |
| Exclusion | On exclut les scrutins "Neutre", on ne garde que Progressif et Restrictif |
| Bar chart | Pour chaque (parti, impact) : `pct_pour` en barres groupees |
| **Indice de justice sociale** | `ecart = pct_pour(Progressif) - pct_pour(Restrictif)` par parti |
| Detail par theme | Selectbox theme, meme bar chart filtre par theme |

**Interpretation de l'indice** :
- Positif = le parti vote davantage POUR les mesures progressives que restrictives
- Negatif = le parti vote davantage POUR les mesures restrictives

---

### Page "Economie"

#### Section 1 : Repartition
- Camembert des doctrines economiques
- Camembert des classes sociales visees

#### Section 2 : Vote par doctrine
Pour chaque (parti, doctrine) : `pct_pour` en barres groupees.

#### Section 3 : Score pro-populaire par classe sociale (normalise)

**Probleme initial** : le croisement `impact x classe_sociale` brut (ancienne methode "effet reel") donnait des resultats incoherents car :
1. Le croisement etait equivalent a Progressif/Restrictif (redondant avec la page Impact Social)
2. Les **% POUR bruts** etaient biaises par la dynamique majorite/opposition (la majorite vote CONTRE les amendements d'opposition quel que soit le contenu)
3. Resultat : Dem apparaissait a +12.8% (1er) sur l'indice social, ce qui est politiquement incoherent

**Solution actuelle** : un **score pro-populaire normalise par scrutin**.

##### Etape 1 : Score pro-populaire

Pour chaque scrutin avec `classe_sociale` et `impact` determines :
```
Si le texte est PROGRESSIF :
  score_pro_populaire = % vote POUR du parti
  (voter POUR un texte progressif = position pro-populaire)

Si le texte est RESTRICTIF :
  score_pro_populaire = % vote CONTRE du parti
  (voter CONTRE un texte restrictif = position pro-populaire)
```

##### Etape 2 : Normalisation per-scrutin

Pour chaque scrutin, on calcule la **moyenne chambre** du score pro-populaire, puis la **deviation** de chaque parti :
```
chamber_avg = moyenne des scores pro-populaire de tous les partis sur ce scrutin
deviation_parti = score_parti - chamber_avg
```

Cette normalisation neutralise le biais majorite/opposition : si tous les partis votent CONTRE un amendement d'opposition, la moyenne chambre est basse et les deviations sont proches de zero.

##### Heatmap

La heatmap montre la **deviation pro-populaire moyenne** par `(parti, classe_sociale_visee)` :
- **Vert** = le parti prend systematiquement plus de positions favorables aux populaires que la moyenne
- **Rouge** = moins que la moyenne

| Lecture | Signification |
|---------|--------------|
| Aisees : gauche verte, droite rouge | La gauche vote plus pour taxer/reguler les riches |
| Populaires : RN vert | Le RN vote plus pour les mesures ciblant les populaires (populisme social) |
| Populaires : EPR rouge | La majorite vote moins que la moyenne sur ces textes |

##### Indice pro-populaire

```
indice = moyenne(deviation_pro_populaire) sur tous les scrutins avec classe determinee
```

- Positif = le parti vote systematiquement plus en faveur des classes populaires que la moyenne
- Negatif = moins que la moyenne

Resultats typiques : LFI (+16.6) > EcoS (+16.1) > SOC (+10.8) > ... > Dem (-7.2) > EPR (-9.7) > HOR (-10.5)

#### Section 4 : Detail par doctrine
Selectbox pour choisir une doctrine, liste des 20 derniers scrutins avec votes par parti.

---

### Page "Par loi"

| Element | Calcul |
|---------|--------|
| Filtres | Recherche texte, theme, doctrine, groupe auteur |
| Aggregation par loi | nb_scrutins (nunique), date_debut (min), date_fin (max), nb_adoptes, nb_rejetes |
| Theme/doctrine/impact principaux | Mode (valeur la plus frequente) |
| Detail | Selectbox pour choisir une loi, expanders pour chaque scrutin avec votes par parti |

---

### Page "Axe politique"

#### Score gauche-droite (calcule dans load_data)

Pour chaque scrutin, on calcule un score entre -1 et +1 :

```
score_gd = SUM(position_parti * pct_pour_parti * votes_exprimes_parti) / SUM(votes_exprimes)
```

Ou :
- `position_parti` = poids fixe du parti (voir tableau ci-dessus, -1 a +1)
- `pct_pour_parti` = pour / (pour + contre + abstentions) du parti sur ce scrutin
- `votes_exprimes` = pour + contre + abstentions du parti

**Interpretation** : un parti de droite qui vote massivement POUR tire le score vers la droite. Un parti de gauche qui vote massivement POUR tire le score vers la gauche.

#### Seuils d'orientation

| Score | Label |
|-------|-------|
| < -0.15 | Gauche |
| [-0.15, -0.05[ | Centre-gauche |
| [-0.05, +0.05] | Centre / Transversal |
| ]+0.05, +0.15] | Centre-droit |
| > +0.15 | Droite |

#### Contre-courant

Pour chaque parti (sauf NI et partis avec |position| < 0.1) :
```
Si parti de gauche (pos < 0) :
  textes_camp_oppose = scrutins ou score_gd > 0.05 (textes de droite)
  pct_contre_courant = moyenne du pct_pour sur ces textes

Si parti de droite (pos > 0) :
  textes_camp_oppose = scrutins ou score_gd < -0.05 (textes de gauche)
  pct_contre_courant = moyenne du pct_pour sur ces textes
```

---

### Page "Par scrutin"

| Element | Calcul |
|---------|--------|
| Filtres | Theme (selectbox), recherche titre (text_input), groupe auteur (multiselect) |
| Affichage | 50 derniers scrutins, tries par date decroissante |
| Detail | Impact + confiance, methode, amendement (numero, groupe, expose), votes par parti (bar chart) |

---

### Page "Comparaison"

#### Matrice d'alignement

Pour chaque paire de partis (P1, P2) :
```
alignement = nombre de scrutins ou position_majoritaire(P1) == position_majoritaire(P2)
             / nombre de scrutins ou les deux partis ont vote
             * 100
```

#### Evolution temporelle
Regroupement mensuel, pour chaque (mois, parti) : `pct_pour`.

---

## Limites et biais connus

### Classification par mots-cles
- Les mots-cles ne capturent pas toutes les nuances. Un texte peut etre classe "Social" sans l'etre reellement si le titre contient les bons termes.
- Les amendements sans expose des motifs n'ont qu'un signal (titre) -> confiance basse.
- Le groupe politique de l'auteur de l'amendement n'est **pas** utilise comme signal pour la classification de l'impact, afin d'eviter un biais circulaire (presupposer gauche=progressif, droite=restrictif biaiserait les indicateurs qui mesurent justement les positions des partis).
- **Vocabulaire fiscal bidirectionnel** : des termes comme "baisse d'impot", "suppression de taxe", "reduction de cotisation" sont utilises autant par la gauche (baisser les impots des menages modestes) que par la droite (baisser l'impot sur les societes). Le matching par mots-cles ne peut pas distinguer ces contextes. Cela explique un bruit residuel dans la classification doctrinale (ex: LFI a ~47% de vote POUR sur les textes classes "Liberal").

### Biais majorite/opposition
- La majorite gouvernementale vote systematiquement POUR les textes du gouvernement, independamment du contenu. L'opposition vote systematiquement CONTRE.
- Ce biais est neutralise par la **normalisation per-scrutin** (deviation par rapport a la moyenne de la chambre) utilisee dans l'indice pro-populaire de la page Economie.
- La page Impact Social utilise les % POUR bruts, ou ce biais est visible mais moins problematique car l'echantillon est plus large.

### Matching amendements
- ~85% des scrutins sont matches a un amendement. Les 15% restants n'ont pas de numero d'amendement dans le titre.
- Certains scrutins portent sur l'ensemble d'un texte, pas sur un amendement specifique.

### Doctrine economique
- Seuls ~40% des scrutins sont classes avec une doctrine (les autres sont "Non economique"). La classification ne s'applique qu'aux textes dont le titre ou l'expose contient des signaux economiques.
- La categorie Liberal est la plus bruitee : le vocabulaire fiscal (exoneration, credit d'impot) a ete retire car trop ambigu. Les patterns restants (suppression de taxe, baisse d'impot, reduction cotisation) sont encore bidirectionnels mais en moindre mesure.

### Classe sociale
- ~28% des scrutins ont une classe sociale identifiee. Le reste est "Non determine".
- Le score pro-populaire normalise est calcule sur ce sous-ensemble (~1000 scrutins avec classe ET impact determines).
