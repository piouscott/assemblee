"""Dashboard Streamlit - Analyse des votes de l'Assemblee Nationale."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

PROCESSED_DIR = Path(__file__).parent / "data" / "processed"

# -- Couleurs des partis (17e legislature) --
COULEURS_PARTIS = {
    "RN": "#0D378A",
    "EPR": "#FFD600",
    "LFI-NFP": "#CC2443",
    "SOC": "#FF8080",
    "DR": "#0066CC",
    "EcoS": "#00C000",
    "Dem": "#FF9900",
    "HOR": "#00BFFF",
    "LIOT": "#AAAAAA",
    "GDR": "#DD0000",
    "NI": "#CCCCCC",
    "AD": "#2B4593",
    "UDR": "#5B8CCC",
}

# -- Position gauche-droite des partis (poids pour le score) --
# -1 = gauche, +1 = droite, 0 = centre
POSITION_GD = {
    "LFI-NFP": -1.0,
    "GDR":     -0.85,
    "EcoS":    -0.7,
    "SOC":     -0.6,
    "LIOT":     0.0,   # transversal
    "Dem":      0.3,
    "EPR":      0.4,
    "HOR":      0.5,
    "AD":       0.7,
    "UDR":      0.75,
    "DR":       0.8,
    "RN":       0.9,
    "NI":       0.0,   # neutre
}


@st.cache_data
def load_data():
    scrutins = pd.read_csv(PROCESSED_DIR / "scrutins.csv", encoding="utf-8")
    scrutins["date"] = pd.to_datetime(scrutins["date"])

    votes = pd.read_csv(PROCESSED_DIR / "votes_par_groupe.csv", encoding="utf-8")
    votes["date"] = pd.to_datetime(votes["date"])

    acteurs = pd.read_csv(PROCESSED_DIR / "acteurs.csv", encoding="utf-8")

    themes_path = PROCESSED_DIR / "themes.csv"
    if themes_path.exists():
        themes = pd.read_csv(themes_path, encoding="utf-8")
        scrutins = scrutins.merge(themes, on="scrutin_uid", how="left")
        scrutins["theme"] = scrutins["theme"].fillna("Non classifie")
        if "impact" not in scrutins.columns:
            scrutins["impact"] = "Neutre"
        scrutins["impact"] = scrutins["impact"].fillna("Neutre")
        if "confiance" not in scrutins.columns:
            scrutins["confiance"] = "basse"
        scrutins["confiance"] = scrutins["confiance"].fillna("basse")
        if "methode_impact" not in scrutins.columns:
            scrutins["methode_impact"] = ""
        scrutins["methode_impact"] = scrutins["methode_impact"].fillna("")
        if "loi_parente" not in scrutins.columns:
            scrutins["loi_parente"] = ""
        scrutins["loi_parente"] = scrutins["loi_parente"].fillna("")
        if "doctrine_eco" not in scrutins.columns:
            scrutins["doctrine_eco"] = "Non economique"
        scrutins["doctrine_eco"] = scrutins["doctrine_eco"].fillna("Non economique")
        if "classe_sociale" not in scrutins.columns:
            scrutins["classe_sociale"] = "Non determine"
        scrutins["classe_sociale"] = scrutins["classe_sociale"].fillna("Non determine")
    else:
        scrutins["theme"] = "Non classifie"
        scrutins["impact"] = "Neutre"
        scrutins["confiance"] = "basse"
        scrutins["methode_impact"] = ""
        scrutins["loi_parente"] = ""
        scrutins["doctrine_eco"] = "Non economique"
        scrutins["classe_sociale"] = "Non determine"

    # Charger les donnees d'amendements si disponibles
    amdt_path = PROCESSED_DIR / "scrutins_amendements.csv"
    if amdt_path.exists():
        amdt_df = pd.read_csv(amdt_path, encoding="utf-8")
        scrutins = scrutins.merge(amdt_df, on="scrutin_uid", how="left")
        for col in ["amdt_numero", "amdt_groupe_abrege", "amdt_expose",
                     "amdt_dispositif", "amdt_signataires"]:
            if col in scrutins.columns:
                scrutins[col] = scrutins[col].fillna("")

    # Filtrer uniquement 17e legislature
    votes_17 = votes[votes["groupe_abrege"].isin(COULEURS_PARTIS.keys())].copy()

    # Joindre le theme et l'impact aux votes
    merge_cols = ["scrutin_uid", "theme", "impact", "titre", "sort", "libelle_type_vote"]
    for extra_col in ["confiance", "doctrine_eco", "classe_sociale", "loi_parente",
                       "amdt_groupe_abrege"]:
        if extra_col in scrutins.columns:
            merge_cols.append(extra_col)
    votes_17 = votes_17.merge(
        scrutins[merge_cols],
        on="scrutin_uid",
        how="left",
    )

    # -- Calculer le score gauche-droite par scrutin --
    # Methode : pour chaque scrutin, on regarde le % de votes POUR de chaque parti,
    # pondere par sa position sur l'axe gauche-droite.
    # Score negatif = texte soutenu par la gauche, positif = soutenu par la droite.
    def compute_score_gd(group):
        total_score = 0.0
        total_weight = 0.0
        for _, row in group.iterrows():
            parti = row["groupe_abrege"]
            pos = POSITION_GD.get(parti, 0.0)
            if parti == "NI":
                continue
            votes_exprimes = row["pour"] + row["contre"] + row["abstentions"]
            if votes_exprimes == 0:
                continue
            pct_pour = row["pour"] / votes_exprimes
            # Un parti de droite qui vote POUR tire le score vers la droite
            total_score += pos * pct_pour * votes_exprimes
            total_weight += votes_exprimes
        if total_weight == 0:
            return 0.0
        return total_score / total_weight

    scores_gd = votes_17.groupby("scrutin_uid").apply(compute_score_gd, include_groups=False).reset_index()
    scores_gd.columns = ["scrutin_uid", "score_gd"]
    scrutins = scrutins.merge(scores_gd, on="scrutin_uid", how="left")
    scrutins["score_gd"] = scrutins["score_gd"].fillna(0.0)

    # Label lisible
    def label_gd(score):
        if score < -0.15:
            return "Gauche"
        elif score < -0.05:
            return "Centre-gauche"
        elif score <= 0.05:
            return "Centre / Transversal"
        elif score <= 0.15:
            return "Centre-droit"
        else:
            return "Droite"

    scrutins["orientation"] = scrutins["score_gd"].apply(label_gd)

    # Joindre score_gd et orientation aux votes
    votes_17 = votes_17.merge(
        scrutins[["scrutin_uid", "score_gd", "orientation"]],
        on="scrutin_uid",
        how="left",
    )

    return scrutins, votes_17, acteurs


def page_vue_ensemble(scrutins: pd.DataFrame, votes: pd.DataFrame):
    st.header("Vue d'ensemble")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Scrutins", f"{len(scrutins):,}")
    col2.metric("Adoptes", f"{(scrutins['sort'].isin(['adopte', 'adopt\u00e9'])).sum():,}")
    col3.metric("Rejetes", f"{(scrutins['sort'].isin(['rejete', 'rejet\u00e9'])).sum():,}")
    date_range = f"{scrutins['date'].min().strftime('%d/%m/%Y')} - {scrutins['date'].max().strftime('%d/%m/%Y')}"
    col4.metric("Periode", date_range)

    # Timeline des scrutins par mois
    scrutins_monthly = scrutins.set_index("date").resample("M").size().reset_index(name="nb_scrutins")
    fig_timeline = px.bar(
        scrutins_monthly, x="date", y="nb_scrutins",
        title="Nombre de scrutins par mois",
        labels={"date": "Mois", "nb_scrutins": "Nombre de scrutins"},
    )
    st.plotly_chart(fig_timeline, use_container_width=True)

    # Repartition par theme
    if "theme" in scrutins.columns:
        theme_counts = scrutins["theme"].value_counts().reset_index()
        theme_counts.columns = ["theme", "count"]
        fig_themes = px.pie(
            theme_counts, values="count", names="theme",
            title="Repartition des scrutins par theme",
        )
        fig_themes.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_themes, use_container_width=True)

    # Repartition par type de vote
    type_counts = scrutins["libelle_type_vote"].value_counts().reset_index()
    type_counts.columns = ["type", "count"]
    fig_types = px.bar(
        type_counts, x="type", y="count",
        title="Types de votes",
        labels={"type": "Type", "count": "Nombre"},
    )
    st.plotly_chart(fig_types, use_container_width=True)


def page_par_parti(votes: pd.DataFrame):
    st.header("Analyse par parti politique")

    # Participation et positions par parti
    partis_stats = votes.groupby("groupe_abrege").agg(
        nb_scrutins=("scrutin_uid", "nunique"),
        total_pour=("pour", "sum"),
        total_contre=("contre", "sum"),
        total_abstentions=("abstentions", "sum"),
    ).reset_index()

    partis_stats["total_votes"] = partis_stats["total_pour"] + partis_stats["total_contre"] + partis_stats["total_abstentions"]
    partis_stats["pct_pour"] = (partis_stats["total_pour"] / partis_stats["total_votes"] * 100).round(1)
    partis_stats["pct_contre"] = (partis_stats["total_contre"] / partis_stats["total_votes"] * 100).round(1)
    partis_stats["pct_abstentions"] = (partis_stats["total_abstentions"] / partis_stats["total_votes"] * 100).round(1)
    partis_stats = partis_stats.sort_values("total_votes", ascending=False)

    # Barres empilees : % pour/contre/abstention par parti
    fig_partis = go.Figure()
    colors = {"Pour": "#2ecc71", "Contre": "#e74c3c", "Abstention": "#f39c12"}
    for label, col in [("Pour", "pct_pour"), ("Contre", "pct_contre"), ("Abstention", "pct_abstentions")]:
        fig_partis.add_trace(go.Bar(
            name=label,
            x=partis_stats["groupe_abrege"],
            y=partis_stats[col],
            marker_color=colors[label],
        ))
    fig_partis.update_layout(
        barmode="stack",
        title="Position de vote par parti (% des votes exprimes)",
        xaxis_title="Parti",
        yaxis_title="%",
    )
    st.plotly_chart(fig_partis, use_container_width=True)

    # Heatmap : theme x parti -> % pour
    if "theme" in votes.columns:
        st.subheader("Taux de vote POUR par theme et par parti")
        theme_parti = votes.groupby(["theme", "groupe_abrege"]).agg(
            total_pour=("pour", "sum"),
            total_votes=("pour", "sum"),
        ).reset_index()
        # Recalculer total_votes correctement
        theme_parti_agg = votes.groupby(["theme", "groupe_abrege"]).apply(
            lambda g: pd.Series({
                "total_pour": g["pour"].sum(),
                "total_votes": g["pour"].sum() + g["contre"].sum() + g["abstentions"].sum(),
            }),
            include_groups=False,
        ).reset_index()
        theme_parti_agg["pct_pour"] = (theme_parti_agg["total_pour"] / theme_parti_agg["total_votes"] * 100).round(1)
        theme_parti_agg["pct_pour"] = theme_parti_agg["pct_pour"].fillna(0)

        pivot = theme_parti_agg.pivot_table(
            index="theme", columns="groupe_abrege", values="pct_pour", fill_value=0,
        )
        # Trier les partis par ordre politique approximatif
        ordre = ["LFI-NFP", "GDR", "EcoS", "SOC", "LIOT", "Dem", "EPR", "HOR", "AD", "UDR", "DR", "RN", "NI"]
        cols_ordered = [c for c in ordre if c in pivot.columns]
        pivot = pivot[cols_ordered]

        fig_heatmap = px.imshow(
            pivot,
            color_continuous_scale="RdYlGn",
            aspect="auto",
            title="% de votes POUR par theme et parti",
            labels={"color": "% Pour"},
        )
        fig_heatmap.update_layout(height=600)
        st.plotly_chart(fig_heatmap, use_container_width=True)


def page_par_scrutin(scrutins: pd.DataFrame, votes: pd.DataFrame):
    st.header("Detail par scrutin")

    # Filtres
    col1, col2 = st.columns(2)
    with col1:
        themes_dispo = sorted(scrutins["theme"].dropna().unique())
        theme_filter = st.selectbox("Filtrer par theme", ["Tous"] + themes_dispo)
    with col2:
        search = st.text_input("Rechercher dans le titre")

    # Filtre par groupe auteur de l'amendement
    if "amdt_groupe_abrege" in scrutins.columns:
        groupes_auteur = sorted(scrutins["amdt_groupe_abrege"].dropna().replace("", pd.NA).dropna().unique())
        if groupes_auteur:
            selected_groupes = st.multiselect(
                "Filtrer par groupe auteur de l'amendement",
                groupes_auteur,
                default=[],
                key="scrutin_groupe_auteur",
            )
        else:
            selected_groupes = []
    else:
        selected_groupes = []

    filtered = scrutins.copy()
    if theme_filter != "Tous":
        filtered = filtered[filtered["theme"] == theme_filter]
    if search:
        filtered = filtered[filtered["titre"].str.contains(search, case=False, na=False)]
    if selected_groupes:
        filtered = filtered[filtered["amdt_groupe_abrege"].isin(selected_groupes)]

    filtered = filtered.sort_values("date", ascending=False)
    st.write(f"{len(filtered)} scrutins trouves")

    # Afficher les 50 derniers
    for _, row in filtered.head(50).iterrows():
        # Prefix avec indicateur impact
        impact = row.get("impact", "Neutre")
        icon_map = {"Progressif": "🟢", "Restrictif": "🔴", "Neutre": "⚪"}
        icon = icon_map.get(impact, "⚪")
        with st.expander(f"{icon} [{row['date'].strftime('%d/%m/%Y')}] {row['titre'][:300]}"):
            # Ligne 1 : metadonnees
            st.write(f"**Type**: {row['libelle_type_vote']} | **Resultat**: {row['sort']} | **Theme**: {row.get('theme', '?')}")

            # Ligne 2 : impact et confiance
            confiance = row.get("confiance", "")
            methode = row.get("methode_impact", "")
            conf_badge = {"haute": "🟢 haute", "moyenne": "🟡 moyenne", "basse": "🔴 basse"}.get(confiance, confiance)
            st.write(f"**Impact**: {impact} | **Confiance**: {conf_badge}")
            if methode:
                st.caption(f"Methode : {methode}")

            st.write(f"**Votants**: {row['nb_votants']} | Pour: {row['total_pour']} | Contre: {row['total_contre']} | Abstentions: {row['total_abstentions']}")

            # Amendement : expose des motifs et auteur
            amdt_expose = row.get("amdt_expose", "")
            amdt_groupe = row.get("amdt_groupe_abrege", "")
            amdt_signataires = row.get("amdt_signataires", "")
            amdt_numero = row.get("amdt_numero", "")
            if amdt_numero and isinstance(amdt_numero, str) and amdt_numero.strip():
                st.markdown("---")
                st.markdown(f"**Amendement n{amdt_numero}** - Groupe auteur : **{amdt_groupe}**")
                if amdt_signataires:
                    st.caption(f"Signataires : {amdt_signataires[:200]}")
                if amdt_expose and isinstance(amdt_expose, str) and amdt_expose.strip():
                    st.markdown("**Expose des motifs :**")
                    st.info(amdt_expose)

            # Votes par groupe pour ce scrutin
            scrutin_votes = votes[votes["scrutin_uid"] == row["scrutin_uid"]].copy()
            if not scrutin_votes.empty:
                fig = go.Figure()
                scrutin_votes = scrutin_votes.sort_values("pour", ascending=True)
                for label, col, color in [("Pour", "pour", "#2ecc71"), ("Contre", "contre", "#e74c3c"), ("Abstention", "abstentions", "#f39c12")]:
                    fig.add_trace(go.Bar(
                        name=label,
                        y=scrutin_votes["groupe_abrege"],
                        x=scrutin_votes[col],
                        orientation="h",
                        marker_color=color,
                    ))
                fig.update_layout(barmode="stack", height=300, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)


def page_comparaison(votes: pd.DataFrame):
    st.header("Comparaison entre partis")

    partis = sorted(votes["groupe_abrege"].unique())
    selected = st.multiselect("Selectionner des partis a comparer", partis, default=partis[:3])

    if len(selected) < 2:
        st.warning("Selectionne au moins 2 partis.")
        return

    filtered = votes[votes["groupe_abrege"].isin(selected)]

    if "theme" in filtered.columns:
        theme_filter = st.selectbox("Filtrer par theme", ["Tous"] + sorted(filtered["theme"].dropna().unique()))
        if theme_filter != "Tous":
            filtered = filtered[filtered["theme"] == theme_filter]

    # Calculer l'alignement entre partis (% de fois ou ils votent pareil)
    st.subheader("Alignement entre partis")
    st.caption("% de scrutins ou la position majoritaire est identique")

    # Pivot: scrutin x parti -> position majoritaire
    pivot_pos = filtered.pivot_table(
        index="scrutin_uid", columns="groupe_abrege", values="position_majoritaire", aggfunc="first",
    )
    pivot_pos = pivot_pos[selected]

    alignment = pd.DataFrame(index=selected, columns=selected, dtype=float)
    for p1 in selected:
        for p2 in selected:
            if p1 == p2:
                alignment.loc[p1, p2] = 100.0
            else:
                mask = pivot_pos[p1].notna() & pivot_pos[p2].notna()
                if mask.sum() > 0:
                    alignment.loc[p1, p2] = round((pivot_pos.loc[mask, p1] == pivot_pos.loc[mask, p2]).mean() * 100, 1)
                else:
                    alignment.loc[p1, p2] = 0.0

    fig_align = px.imshow(
        alignment.astype(float),
        color_continuous_scale="Blues",
        text_auto=True,
        title="Matrice d'alignement (% de positions identiques)",
    )
    st.plotly_chart(fig_align, use_container_width=True)

    # Evolution temporelle du taux de vote Pour
    st.subheader("Evolution du taux de vote POUR dans le temps")
    monthly = filtered.copy()
    monthly["mois"] = monthly["date"].dt.to_period("M").astype(str)
    monthly_agg = monthly.groupby(["mois", "groupe_abrege"]).apply(
        lambda g: pd.Series({
            "pct_pour": g["pour"].sum() / max(g["pour"].sum() + g["contre"].sum() + g["abstentions"].sum(), 1) * 100,
        }),
        include_groups=False,
    ).reset_index()

    fig_evol = px.line(
        monthly_agg, x="mois", y="pct_pour", color="groupe_abrege",
        color_discrete_map=COULEURS_PARTIS,
        title="Evolution mensuelle du % de votes POUR",
        labels={"mois": "Mois", "pct_pour": "% Pour", "groupe_abrege": "Parti"},
    )
    fig_evol.update_layout(height=500)
    st.plotly_chart(fig_evol, use_container_width=True)


def page_axe_politique(scrutins: pd.DataFrame, votes: pd.DataFrame):
    st.header("Axe gauche-droite des scrutins")
    st.caption(
        "Chaque scrutin recoit un score base sur les votes ponderes par la position "
        "politique de chaque parti. Score negatif = soutenu par la gauche, positif = par la droite."
    )

    # Distribution des scores
    fig_dist = px.histogram(
        scrutins, x="score_gd", nbins=60,
        color="orientation",
        color_discrete_map={
            "Gauche": "#CC2443",
            "Centre-gauche": "#FF8080",
            "Centre / Transversal": "#AAAAAA",
            "Centre-droit": "#87CEEB",
            "Droite": "#0D378A",
        },
        title="Distribution des scrutins sur l'axe gauche-droite",
        labels={"score_gd": "Score (gauche < 0 < droite)", "count": "Nombre"},
    )
    fig_dist.update_layout(height=400)
    st.plotly_chart(fig_dist, use_container_width=True)

    # Repartition par orientation
    col1, col2 = st.columns(2)
    with col1:
        orient_counts = scrutins["orientation"].value_counts().reset_index()
        orient_counts.columns = ["orientation", "count"]
        fig_pie = px.pie(
            orient_counts, values="count", names="orientation",
            color="orientation",
            color_discrete_map={
                "Gauche": "#CC2443",
                "Centre-gauche": "#FF8080",
                "Centre / Transversal": "#AAAAAA",
                "Centre-droit": "#87CEEB",
                "Droite": "#0D378A",
            },
            title="Repartition des scrutins par orientation",
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        # Orientation par theme
        if "theme" in scrutins.columns:
            theme_orient = scrutins.groupby("theme")["score_gd"].mean().sort_values().reset_index()
            theme_orient.columns = ["theme", "score_moyen"]
            theme_orient["couleur"] = theme_orient["score_moyen"].apply(
                lambda x: "#CC2443" if x < -0.05 else ("#0D378A" if x > 0.05 else "#AAAAAA")
            )
            fig_theme_gd = px.bar(
                theme_orient, x="score_moyen", y="theme", orientation="h",
                color="couleur",
                color_discrete_map="identity",
                title="Orientation moyenne par theme",
                labels={"score_moyen": "Score gauche-droite", "theme": ""},
            )
            fig_theme_gd.update_layout(showlegend=False, height=500)
            st.plotly_chart(fig_theme_gd, use_container_width=True)

    # Scatter : score GD x date, colore par orientation
    st.subheader("Chronologie des scrutins sur l'axe politique")
    fig_chrono = px.scatter(
        scrutins, x="date", y="score_gd",
        color="orientation",
        color_discrete_map={
            "Gauche": "#CC2443",
            "Centre-gauche": "#FF8080",
            "Centre / Transversal": "#AAAAAA",
            "Centre-droit": "#87CEEB",
            "Droite": "#0D378A",
        },
        hover_data=["titre", "theme", "sort"],
        title="Score politique de chaque scrutin dans le temps",
        labels={"date": "Date", "score_gd": "Score (gauche < 0 < droite)"},
        opacity=0.6,
    )
    fig_chrono.add_hline(y=0, line_dash="dash", line_color="gray")
    fig_chrono.update_layout(height=500)
    st.plotly_chart(fig_chrono, use_container_width=True)

    # Top scrutins les plus "a gauche" et "a droite"
    col_g, col_d = st.columns(2)
    with col_g:
        st.subheader("Top 10 scrutins les plus a gauche")
        top_gauche = scrutins.nsmallest(10, "score_gd")[["date", "titre", "score_gd", "theme", "sort"]]
        for _, row in top_gauche.iterrows():
            st.markdown(f"**{row['score_gd']:.3f}** | {row['date'].strftime('%d/%m/%Y')} | {row['titre'][:200]}...")

    with col_d:
        st.subheader("Top 10 scrutins les plus a droite")
        top_droite = scrutins.nlargest(10, "score_gd")[["date", "titre", "score_gd", "theme", "sort"]]
        for _, row in top_droite.iterrows():
            st.markdown(f"**+{row['score_gd']:.3f}** | {row['date'].strftime('%d/%m/%Y')} | {row['titre'][:200]}...")

    # Quel parti vote le plus souvent "a contre-courant" de son camp ?
    st.subheader("Qui vote a contre-courant ?")
    st.caption("% de fois ou un parti vote POUR un texte du camp oppose")

    rows = []
    for parti, pos in POSITION_GD.items():
        if parti == "NI" or abs(pos) < 0.1:
            continue
        parti_votes = votes[votes["groupe_abrege"] == parti].copy()
        if parti_votes.empty:
            continue
        parti_votes["total_expr"] = parti_votes["pour"] + parti_votes["contre"] + parti_votes["abstentions"]
        parti_votes = parti_votes[parti_votes["total_expr"] > 0]
        parti_votes["pct_pour"] = parti_votes["pour"] / parti_votes["total_expr"]
        if pos < 0:  # parti de gauche
            # Textes de droite (score > 0.05)
            contre_courant = parti_votes[parti_votes["score_gd"] > 0.05]
            camp_oppose = "droite"
        else:  # parti de droite
            contre_courant = parti_votes[parti_votes["score_gd"] < -0.05]
            camp_oppose = "gauche"
        if not contre_courant.empty:
            pct = contre_courant["pct_pour"].mean() * 100
            rows.append({"parti": parti, "camp": "gauche" if pos < 0 else "droite",
                         "vote_pour_camp_oppose": round(pct, 1), "nb_scrutins": len(contre_courant)})

    if rows:
        cc_df = pd.DataFrame(rows).sort_values("vote_pour_camp_oppose", ascending=False)
        fig_cc = px.bar(
            cc_df, x="parti", y="vote_pour_camp_oppose",
            color="camp",
            color_discrete_map={"gauche": "#CC2443", "droite": "#0D378A"},
            title="% de vote POUR sur les textes du camp oppose",
            labels={"parti": "Parti", "vote_pour_camp_oppose": "% Pour", "camp": "Camp"},
        )
        st.plotly_chart(fig_cc, use_container_width=True)


COULEURS_IMPACT = {
    "Progressif": "#2ecc71",
    "Restrictif": "#e74c3c",
    "Neutre": "#95a5a6",
}


def page_impact_social(scrutins: pd.DataFrame, votes: pd.DataFrame):
    st.header("Impact social : qui vote quoi vraiment ?")
    st.caption(
        "Les scrutins sont classes selon leur impact : **Progressif** (etend des droits, "
        "augmente des aides, protege) vs **Restrictif** (reduit des droits, durcit, coupe). "
        "On regarde ensuite quel parti vote POUR chaque type de mesure."
    )

    # Filtre par groupe auteur de l'amendement
    if "amdt_groupe_abrege" in scrutins.columns:
        groupes_auteur = sorted(scrutins["amdt_groupe_abrege"].dropna().replace("", pd.NA).dropna().unique())
        if groupes_auteur:
            selected_groupes = st.multiselect(
                "Filtrer par groupe auteur de l'amendement",
                groupes_auteur,
                default=[],
                key="impact_groupe_auteur",
            )
            if selected_groupes:
                uids = set(scrutins[scrutins["amdt_groupe_abrege"].isin(selected_groupes)]["scrutin_uid"])
                scrutins = scrutins[scrutins["scrutin_uid"].isin(uids)]
                votes = votes[votes["scrutin_uid"].isin(uids)]
                st.info(f"Filtre actif : {len(uids)} scrutins avec amendements de {', '.join(selected_groupes)}")

    # Filtre par confiance
    if "confiance" in scrutins.columns:
        conf_filter = st.multiselect(
            "Filtrer par niveau de confiance",
            ["haute", "moyenne", "basse"],
            default=["haute", "moyenne", "basse"],
        )
        scrutins_filtered = scrutins[scrutins["confiance"].isin(conf_filter)]
        votes_filtered = votes.copy()
        uids_ok = set(scrutins_filtered["scrutin_uid"])
        votes_filtered = votes_filtered[votes_filtered["scrutin_uid"].isin(uids_ok)]
    else:
        scrutins_filtered = scrutins
        votes_filtered = votes

    # Exclure les Neutres pour l'analyse
    votes_impact = votes_filtered[votes_filtered["impact"].isin(["Progressif", "Restrictif"])].copy()
    scrutins_impact = scrutins_filtered[scrutins_filtered["impact"].isin(["Progressif", "Restrictif"])].copy()

    if votes_impact.empty:
        st.warning("Pas de scrutins classifies avec un impact. Lance classify_themes.py.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Scrutins Progressifs", f"{(scrutins_impact['impact'] == 'Progressif').sum():,}")
    col2.metric("Scrutins Restrictifs", f"{(scrutins_impact['impact'] == 'Restrictif').sum():,}")
    col3.metric("Scrutins Neutres (exclus)", f"{(scrutins['impact'] == 'Neutre').sum():,}")
    if "confiance" in scrutins.columns:
        nb_haute = (scrutins["confiance"] == "haute").sum()
        col4.metric("Confiance haute", f"{nb_haute:,}")

    # -- Taux de vote POUR par parti, selon l'impact --
    st.subheader("Taux de vote POUR par parti selon le type de mesure")
    st.caption("Compare : quand un texte est progressif, quel parti vote pour ? Et quand il est restrictif ?")

    ordre_partis = ["LFI-NFP", "GDR", "EcoS", "SOC", "LIOT", "Dem", "EPR", "HOR", "AD", "UDR", "DR", "RN"]

    parti_impact = votes_impact.groupby(["groupe_abrege", "impact"]).apply(
        lambda g: pd.Series({
            "pct_pour": g["pour"].sum() / max(g["pour"].sum() + g["contre"].sum() + g["abstentions"].sum(), 1) * 100,
            "nb_scrutins": g["scrutin_uid"].nunique(),
        }),
        include_groups=False,
    ).reset_index()

    fig_impact = px.bar(
        parti_impact[parti_impact["groupe_abrege"].isin(ordre_partis)],
        x="groupe_abrege", y="pct_pour", color="impact",
        color_discrete_map=COULEURS_IMPACT,
        barmode="group",
        category_orders={"groupe_abrege": ordre_partis},
        title="% de vote POUR sur les mesures Progressives vs Restrictives",
        labels={"groupe_abrege": "Parti", "pct_pour": "% Pour", "impact": "Impact"},
    )
    fig_impact.update_layout(height=500)
    st.plotly_chart(fig_impact, use_container_width=True)

    # -- Ecart Progressif - Restrictif par parti --
    st.subheader("Indice de justice sociale par parti")
    st.caption(
        "Ecart = % vote POUR mesures progressives - % vote POUR mesures restrictives. "
        "Positif = vote davantage pour les mesures progressives. Negatif = vote davantage pour les mesures restrictives."
    )
    pivot_impact = parti_impact.pivot_table(
        index="groupe_abrege", columns="impact", values="pct_pour",
    ).reindex(ordre_partis).dropna()

    if "Progressif" in pivot_impact.columns and "Restrictif" in pivot_impact.columns:
        pivot_impact["ecart"] = pivot_impact["Progressif"] - pivot_impact["Restrictif"]
        pivot_impact = pivot_impact.sort_values("ecart", ascending=True)

        fig_ecart = go.Figure()
        fig_ecart.add_trace(go.Bar(
            y=pivot_impact.index,
            x=pivot_impact["ecart"],
            orientation="h",
            marker_color=[
                "#2ecc71" if v > 0 else "#e74c3c" for v in pivot_impact["ecart"]
            ],
            text=[f"{v:+.1f}%" for v in pivot_impact["ecart"]],
            textposition="outside",
        ))
        fig_ecart.update_layout(
            title="Indice de justice sociale (Progressif - Restrictif)",
            xaxis_title="Ecart en points de %",
            height=450,
        )
        fig_ecart.add_vline(x=0, line_dash="dash", line_color="gray")
        st.plotly_chart(fig_ecart, use_container_width=True)

    # -- Par theme : qui vote pour les mesures progressives dans chaque domaine --
    st.subheader("Detour par theme : qui soutient les mesures progressives ?")

    theme_filter = st.selectbox(
        "Choisir un theme",
        sorted(votes_impact["theme"].dropna().unique()),
    )

    theme_votes = votes_impact[votes_impact["theme"] == theme_filter]
    if theme_votes.empty:
        st.info("Pas assez de donnees pour ce theme.")
    else:
        theme_parti = theme_votes.groupby(["groupe_abrege", "impact"]).apply(
            lambda g: pd.Series({
                "pct_pour": g["pour"].sum() / max(g["pour"].sum() + g["contre"].sum() + g["abstentions"].sum(), 1) * 100,
            }),
            include_groups=False,
        ).reset_index()

        fig_theme = px.bar(
            theme_parti[theme_parti["groupe_abrege"].isin(ordre_partis)],
            x="groupe_abrege", y="pct_pour", color="impact",
            color_discrete_map=COULEURS_IMPACT,
            barmode="group",
            category_orders={"groupe_abrege": ordre_partis},
            title=f"Vote POUR par parti - {theme_filter}",
            labels={"groupe_abrege": "Parti", "pct_pour": "% Pour", "impact": "Impact"},
        )
        st.plotly_chart(fig_theme, use_container_width=True)

        # Lister les scrutins concernes
        scrutins_theme = scrutins_impact[
            (scrutins_impact["theme"] == theme_filter)
        ].sort_values("date", ascending=False)

        st.write(f"{len(scrutins_theme)} scrutins dans ce theme ({(scrutins_theme['impact']=='Progressif').sum()} progressifs, {(scrutins_theme['impact']=='Restrictif').sum()} restrictifs)")

        for _, row in scrutins_theme.head(20).iterrows():
            icon = "🟢" if row["impact"] == "Progressif" else "🔴"
            confiance = row.get("confiance", "")
            conf_badge = {"haute": "🟢", "moyenne": "🟡", "basse": "🔴"}.get(confiance, "")
            with st.expander(f"{icon} {conf_badge} [{row['date'].strftime('%d/%m/%Y')}] {row['titre'][:300]}"):
                methode = row.get("methode_impact", "")
                st.write(f"**Impact**: {row['impact']} | **Confiance**: {confiance} | **Resultat**: {row['sort']}")
                if methode:
                    st.caption(f"Methode : {methode}")

                # Amendement details
                amdt_expose = row.get("amdt_expose", "")
                amdt_groupe = row.get("amdt_groupe_abrege", "")
                amdt_numero = row.get("amdt_numero", "")
                amdt_signataires = row.get("amdt_signataires", "")
                if amdt_numero and isinstance(amdt_numero, str) and amdt_numero.strip():
                    st.markdown(f"**Amendement n{amdt_numero}** - Auteur : **{amdt_groupe}**")
                    if amdt_signataires and isinstance(amdt_signataires, str):
                        st.caption(f"Signataires : {amdt_signataires[:200]}")
                    if amdt_expose and isinstance(amdt_expose, str) and amdt_expose.strip():
                        st.info(amdt_expose)

                scrutin_votes = votes[votes["scrutin_uid"] == row["scrutin_uid"]].copy()
                if not scrutin_votes.empty:
                    scrutin_votes = scrutin_votes[scrutin_votes["groupe_abrege"].isin(ordre_partis)]
                    scrutin_votes["groupe_abrege"] = pd.Categorical(
                        scrutin_votes["groupe_abrege"], categories=ordre_partis, ordered=True,
                    )
                    scrutin_votes = scrutin_votes.sort_values("groupe_abrege")
                    fig = go.Figure()
                    for label, col, color in [("Pour", "pour", "#2ecc71"), ("Contre", "contre", "#e74c3c"), ("Abstention", "abstentions", "#f39c12")]:
                        fig.add_trace(go.Bar(
                            name=label, y=scrutin_votes["groupe_abrege"],
                            x=scrutin_votes[col], orientation="h", marker_color=color,
                        ))
                    fig.update_layout(barmode="stack", height=300, margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig, use_container_width=True)


COULEURS_DOCTRINE = {
    "Liberal": "#FF9900",
    "Interventionniste": "#9B59B6",
    "Social": "#2ecc71",
    "Austerite": "#e74c3c",
    "Mixte": "#95a5a6",
    "Non economique": "#D5D5D5",
}

COULEURS_CLASSE = {
    "Populaires": "#e74c3c",
    "Moyennes": "#f39c12",
    "Aisees/Entreprises": "#3498db",
    "Universel": "#2ecc71",
    "Non determine": "#D5D5D5",
}


def page_economie(scrutins: pd.DataFrame, votes: pd.DataFrame):
    st.header("Doctrine economique : qui vote quoi ?")
    st.caption(
        "Chaque scrutin est classe selon sa doctrine economique : **Liberal** (deregulation, allegement), "
        "**Interventionniste** (nationalisation, regulation), **Social** (redistribution, aides), "
        "**Austerite** (reduction deficit). On analyse ensuite quel parti vote POUR chaque type."
    )

    ordre_partis = ["LFI-NFP", "GDR", "EcoS", "SOC", "LIOT", "Dem", "EPR", "HOR", "AD", "UDR", "DR", "RN"]

    # Filtre par groupe auteur de l'amendement
    if "amdt_groupe_abrege" in scrutins.columns:
        groupes_auteur = sorted(scrutins["amdt_groupe_abrege"].dropna().replace("", pd.NA).dropna().unique())
        if groupes_auteur:
            selected_groupes = st.multiselect(
                "Filtrer par groupe auteur de l'amendement",
                groupes_auteur,
                default=[],
                key="eco_groupe_auteur",
            )
            if selected_groupes:
                uids = set(scrutins[scrutins["amdt_groupe_abrege"].isin(selected_groupes)]["scrutin_uid"])
                scrutins = scrutins[scrutins["scrutin_uid"].isin(uids)]
                votes = votes[votes["scrutin_uid"].isin(uids)]
                st.info(f"Filtre actif : {len(uids)} scrutins avec amendements de {', '.join(selected_groupes)}")

    # -- Section 1 : Repartition des doctrines --
    col1, col2 = st.columns(2)
    with col1:
        eco_counts = scrutins["doctrine_eco"].value_counts().reset_index()
        eco_counts.columns = ["doctrine", "count"]
        fig_pie = px.pie(
            eco_counts, values="count", names="doctrine",
            color="doctrine", color_discrete_map=COULEURS_DOCTRINE,
            title="Repartition des scrutins par doctrine economique",
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        classe_counts = scrutins["classe_sociale"].value_counts().reset_index()
        classe_counts.columns = ["classe", "count"]
        fig_pie2 = px.pie(
            classe_counts, values="count", names="classe",
            color="classe", color_discrete_map=COULEURS_CLASSE,
            title="Classe sociale visee par les scrutins",
        )
        fig_pie2.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_pie2, use_container_width=True)

    # -- Section 2 : % vote POUR par parti selon la doctrine --
    st.subheader("Taux de vote POUR par parti selon la doctrine economique")

    eco_filter = st.multiselect(
        "Doctrines a afficher",
        ["Liberal", "Interventionniste", "Social", "Austerite"],
        default=["Liberal", "Interventionniste", "Social"],
    )

    votes_eco = votes[votes["doctrine_eco"].isin(eco_filter)].copy()
    if not votes_eco.empty:
        parti_eco = votes_eco.groupby(["groupe_abrege", "doctrine_eco"]).apply(
            lambda g: pd.Series({
                "pct_pour": g["pour"].sum() / max(g["pour"].sum() + g["contre"].sum() + g["abstentions"].sum(), 1) * 100,
            }),
            include_groups=False,
        ).reset_index()

        fig_eco = px.bar(
            parti_eco[parti_eco["groupe_abrege"].isin(ordre_partis)],
            x="groupe_abrege", y="pct_pour", color="doctrine_eco",
            color_discrete_map=COULEURS_DOCTRINE,
            barmode="group",
            category_orders={"groupe_abrege": ordre_partis},
            title="% de vote POUR par doctrine economique",
            labels={"groupe_abrege": "Parti", "pct_pour": "% Pour", "doctrine_eco": "Doctrine"},
        )
        fig_eco.update_layout(height=500)
        st.plotly_chart(fig_eco, use_container_width=True)

    # -- Section 3 : Qui vote pour quelle classe sociale ? --
    st.subheader("Qui vote pour quelle classe sociale ?")
    st.caption(
        "On croise l'**impact** (Progressif/Restrictif) avec la **classe sociale** visee pour "
        "calculer un **score pro-populaire** : voter POUR un texte progressif = pro-populaire, "
        "voter CONTRE un texte restrictif = pro-populaire. "
        "Les scores sont **normalises par scrutin** (deviation par rapport a la moyenne de la chambre) "
        "pour neutraliser le biais majorite/opposition."
    )

    # Filtrer les scrutins avec classe_sociale et impact determines
    votes_croises = votes[
        (votes["classe_sociale"].isin(["Populaires", "Aisees/Entreprises", "Moyennes"])) &
        (votes["impact"].isin(["Progressif", "Restrictif"]))
    ].copy()

    if not votes_croises.empty:
        # Calculer les composantes de vote
        votes_croises["total_votes"] = (
            votes_croises["pour"] + votes_croises["contre"] + votes_croises["abstentions"]
        )
        votes_croises["pct_pour"] = (
            votes_croises["pour"] / votes_croises["total_votes"].clip(lower=1) * 100
        )
        votes_croises["pct_contre"] = (
            votes_croises["contre"] / votes_croises["total_votes"].clip(lower=1) * 100
        )

        # Score pro-populaire :
        # - Texte Progressif : voter POUR = pro-populaire (etendre droits, taxer riches)
        # - Texte Restrictif : voter CONTRE = pro-populaire (rejeter les coupes)
        votes_croises["score_propop"] = np.where(
            votes_croises["impact"] == "Progressif",
            votes_croises["pct_pour"],
            votes_croises["pct_contre"],
        )

        # Normalisation per-scrutin (deviation par rapport a la moyenne chambre)
        chamber_avg = votes_croises.groupby("scrutin_uid")["score_propop"].mean()
        chamber_avg.name = "chamber_propop"
        votes_croises = votes_croises.merge(
            chamber_avg.reset_index(), on="scrutin_uid", how="left",
        )
        votes_croises["dev_propop"] = (
            votes_croises["score_propop"] - votes_croises["chamber_propop"]
        )

        # Comptage
        nb_pop = votes_croises[votes_croises["classe_sociale"] == "Populaires"]["scrutin_uid"].nunique()
        nb_ais = votes_croises[votes_croises["classe_sociale"] == "Aisees/Entreprises"]["scrutin_uid"].nunique()
        nb_moy = votes_croises[votes_croises["classe_sociale"] == "Moyennes"]["scrutin_uid"].nunique()
        st.write(
            f"**{nb_pop}** scrutins visant les populaires, "
            f"**{nb_ais}** visant les aises/entreprises, "
            f"**{nb_moy}** visant les classes moyennes"
        )

        # --- Heatmap : score pro-populaire normalise par classe sociale ---
        hm_data = (
            votes_croises[votes_croises["groupe_abrege"].isin(ordre_partis)]
            .groupby(["groupe_abrege", "classe_sociale"])["dev_propop"]
            .mean()
            .unstack()
        )
        classes_order = ["Populaires", "Moyennes", "Aisees/Entreprises"]
        cols_ordered = [c for c in ordre_partis if c in hm_data.index]
        hm_data = hm_data.reindex(cols_ordered).reindex(columns=classes_order).dropna(how="all")

        fig_hm = px.imshow(
            hm_data.T, color_continuous_scale="RdYlGn", aspect="auto",
            title="Score pro-populaire normalise par classe sociale visee",
            labels={"color": "Deviation (pts)"},
            zmin=-30, zmax=30,
        )
        fig_hm.update_layout(height=350)
        st.plotly_chart(fig_hm, use_container_width=True)
        st.caption(
            "Vert = le parti prend plus de positions favorables aux populaires que la moyenne. "
            "Rouge = moins. Chaque scrutin est normalise par rapport a la moyenne de la chambre."
        )

        # --- Indice pro-populaire global ---
        st.subheader("Indice de justice sociale par classe visee")
        st.caption(
            "Score pro-populaire moyen normalise : positif = le parti vote systematiquement "
            "plus en faveur des classes populaires que la moyenne de la chambre."
        )

        indice = (
            votes_croises[votes_croises["groupe_abrege"].isin(ordre_partis)]
            .groupby("groupe_abrege")["dev_propop"]
            .mean()
            .reindex(ordre_partis)
            .dropna()
            .sort_values(ascending=True)
        )

        fig_ecart = go.Figure()
        fig_ecart.add_trace(go.Bar(
            y=indice.index,
            x=indice.values,
            orientation="h",
            marker_color=["#2ecc71" if v > 0 else "#e74c3c" for v in indice.values],
            text=[f"{v:+.1f}" for v in indice.values],
            textposition="outside",
        ))
        fig_ecart.update_layout(
            title="Indice pro-populaire normalise (tous scrutins avec classe sociale determinee)",
            xaxis_title="Deviation moyenne (pts)",
            height=450,
        )
        fig_ecart.add_vline(x=0, line_dash="dash", line_color="gray")
        st.plotly_chart(fig_ecart, use_container_width=True)

    # -- Section 4 : Detail par doctrine --
    st.subheader("Explorer les scrutins par doctrine")
    doctrine_detail = st.selectbox(
        "Choisir une doctrine",
        ["Liberal", "Interventionniste", "Social", "Austerite", "Mixte"],
    )
    scrutins_doc = scrutins[scrutins["doctrine_eco"] == doctrine_detail].sort_values("date", ascending=False)
    st.write(f"{len(scrutins_doc)} scrutins classes '{doctrine_detail}'")

    for _, row in scrutins_doc.head(20).iterrows():
        impact_icon = {"Progressif": "🟢", "Restrictif": "🔴", "Neutre": "⚪"}.get(row.get("impact", ""), "⚪")
        with st.expander(f"{impact_icon} [{row['date'].strftime('%d/%m/%Y')}] {row['titre'][:300]}"):
            st.write(f"**Impact**: {row.get('impact', '?')} | **Classe visee**: {row.get('classe_sociale', '?')} | **Resultat**: {row['sort']}")
            amdt_numero = row.get("amdt_numero", "")
            if amdt_numero and isinstance(amdt_numero, str) and amdt_numero.strip():
                st.markdown(f"**Amendement n{amdt_numero}** - Auteur : **{row.get('amdt_groupe_abrege', '')}**")
                amdt_expose = row.get("amdt_expose", "")
                if amdt_expose and isinstance(amdt_expose, str) and amdt_expose.strip():
                    st.info(amdt_expose)
            scrutin_votes = votes[votes["scrutin_uid"] == row["scrutin_uid"]].copy()
            if not scrutin_votes.empty:
                scrutin_votes = scrutin_votes[scrutin_votes["groupe_abrege"].isin(ordre_partis)]
                scrutin_votes["groupe_abrege"] = pd.Categorical(
                    scrutin_votes["groupe_abrege"], categories=ordre_partis, ordered=True,
                )
                scrutin_votes = scrutin_votes.sort_values("groupe_abrege")
                fig = go.Figure()
                for label, col, color in [("Pour", "pour", "#2ecc71"), ("Contre", "contre", "#e74c3c"), ("Abstention", "abstentions", "#f39c12")]:
                    fig.add_trace(go.Bar(
                        name=label, y=scrutin_votes["groupe_abrege"],
                        x=scrutin_votes[col], orientation="h", marker_color=color,
                    ))
                fig.update_layout(barmode="stack", height=300, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)


def page_par_loi(scrutins: pd.DataFrame, votes: pd.DataFrame):
    st.header("Vue par loi")
    st.caption("Les scrutins regroupes par loi parente, avec leurs amendements.")

    ordre_partis = ["LFI-NFP", "GDR", "EcoS", "SOC", "LIOT", "Dem", "EPR", "HOR", "AD", "UDR", "DR", "RN"]

    # Filtres
    col1, col2, col3 = st.columns(3)
    with col1:
        search_loi = st.text_input("Rechercher une loi", "")
    with col2:
        themes_dispo = sorted(scrutins["theme"].dropna().unique())
        theme_filter = st.selectbox("Filtrer par theme", ["Tous"] + themes_dispo, key="loi_theme")
    with col3:
        doctrines_dispo = ["Tous", "Liberal", "Interventionniste", "Social", "Austerite", "Mixte"]
        doctrine_filter = st.selectbox("Filtrer par doctrine eco", doctrines_dispo, key="loi_doctrine")

    # Filtre par groupe auteur de l'amendement
    selected_groupes = []
    if "amdt_groupe_abrege" in scrutins.columns:
        groupes_auteur = sorted(scrutins["amdt_groupe_abrege"].dropna().replace("", pd.NA).dropna().unique())
        if groupes_auteur:
            selected_groupes = st.multiselect(
                "Filtrer par groupe auteur de l'amendement",
                groupes_auteur,
                default=[],
                key="loi_groupe_auteur",
            )

    # Filtrer les scrutins avec une loi parente
    lois_df = scrutins[scrutins["loi_parente"] != ""].copy()
    if search_loi:
        lois_df = lois_df[lois_df["loi_parente"].str.contains(search_loi, case=False, na=False)]
    if theme_filter != "Tous":
        lois_df = lois_df[lois_df["theme"] == theme_filter]
    if doctrine_filter != "Tous":
        lois_df = lois_df[lois_df["doctrine_eco"] == doctrine_filter]
    if selected_groupes:
        lois_df = lois_df[lois_df["amdt_groupe_abrege"].isin(selected_groupes)]

    # Grouper par loi
    loi_stats = lois_df.groupby("loi_parente").agg(
        nb_scrutins=("scrutin_uid", "nunique"),
        date_debut=("date", "min"),
        date_fin=("date", "max"),
        nb_adoptes=("sort", lambda x: x.isin(["adopté", "adopte"]).sum()),
        nb_rejetes=("sort", lambda x: x.isin(["rejeté", "rejete"]).sum()),
        theme_principal=("theme", lambda x: x.mode().iloc[0] if not x.mode().empty else "?"),
        doctrine_principale=("doctrine_eco", lambda x: x.mode().iloc[0] if not x.mode().empty else "?"),
        impact_principal=("impact", lambda x: x.mode().iloc[0] if not x.mode().empty else "?"),
    ).sort_values("nb_scrutins", ascending=False).reset_index()

    st.write(f"{len(loi_stats)} lois trouvees ({lois_df['scrutin_uid'].nunique()} scrutins)")

    # Selecteur de loi
    loi_options = [
        f"{row['loi_parente'][:90]} ({row['nb_scrutins']} scrutins)"
        for _, row in loi_stats.head(50).iterrows()
    ]
    loi_names = [row["loi_parente"] for _, row in loi_stats.head(50).iterrows()]

    if not loi_options:
        st.info("Aucune loi trouvee avec ces filtres.")
        return

    selected_idx = st.selectbox(
        "Selectionner une loi",
        range(len(loi_options)),
        format_func=lambda i: loi_options[i],
        key="loi_select",
    )

    loi_name = loi_names[selected_idx]
    loi_row = loi_stats[loi_stats["loi_parente"] == loi_name].iloc[0]

    # Resume de la loi
    st.subheader(loi_name[:300])
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Scrutins", loi_row["nb_scrutins"])
    col_b.metric("Adoptes", loi_row["nb_adoptes"])
    col_c.metric("Rejetes", loi_row["nb_rejetes"])
    col_d.metric("Theme", loi_row["theme_principal"])

    dates = f"{loi_row['date_debut'].strftime('%d/%m/%Y')} - {loi_row['date_fin'].strftime('%d/%m/%Y')}"
    st.write(f"**Periode**: {dates} | **Doctrine**: {loi_row['doctrine_principale']} | **Impact dominant**: {loi_row['impact_principal']}")

    st.markdown("---")
    st.subheader("Scrutins et amendements")

    # Liste des scrutins de cette loi (comme des expanders normaux, pas imbriques)
    scrutins_loi = lois_df[lois_df["loi_parente"] == loi_name].sort_values("date", ascending=True)

    for _, srow in scrutins_loi.head(50).iterrows():
        s_impact = srow.get("impact", "Neutre")
        s_icon = {"Progressif": "🟢", "Restrictif": "🔴", "Neutre": "⚪"}.get(s_impact, "⚪")
        s_titre = srow["titre"][:300]
        s_date = srow["date"].strftime("%d/%m")
        s_sort = srow["sort"]
        amdt_num = srow.get("amdt_numero", "")
        amdt_grp = srow.get("amdt_groupe_abrege", "")
        amdt_sig = srow.get("amdt_signataires", "")

        if amdt_num and isinstance(amdt_num, str) and amdt_num.strip():
            amdt_label = f" | Amdt n{amdt_num} ({amdt_grp})"
        else:
            amdt_label = ""

        with st.expander(f"{s_icon} {s_date} | {s_sort}{amdt_label} | {s_titre}"):
            st.write(f"**Impact**: {s_impact} | **Resultat**: {s_sort}")
            if amdt_num and isinstance(amdt_num, str) and amdt_num.strip():
                st.markdown(f"**Amendement n{amdt_num}** - Groupe : **{amdt_grp}**")
                if amdt_sig and isinstance(amdt_sig, str):
                    st.caption(f"Signataires : {amdt_sig[:200]}")
                amdt_expose = srow.get("amdt_expose", "")
                if amdt_expose and isinstance(amdt_expose, str) and amdt_expose.strip():
                    st.info(amdt_expose)

            # Votes par groupe
            s_votes = votes[votes["scrutin_uid"] == srow["scrutin_uid"]].copy()
            if not s_votes.empty:
                s_votes = s_votes[s_votes["groupe_abrege"].isin(ordre_partis)]
                s_votes["groupe_abrege"] = pd.Categorical(
                    s_votes["groupe_abrege"], categories=ordre_partis, ordered=True,
                )
                s_votes = s_votes.sort_values("groupe_abrege")
                fig = go.Figure()
                for label, col, color in [("Pour", "pour", "#2ecc71"), ("Contre", "contre", "#e74c3c"), ("Abstention", "abstentions", "#f39c12")]:
                    fig.add_trace(go.Bar(
                        name=label, y=s_votes["groupe_abrege"],
                        x=s_votes[col], orientation="h", marker_color=color,
                    ))
                fig.update_layout(barmode="stack", height=300, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)


def main():
    st.set_page_config(
        page_title="Assemblee Nationale - Analyse des votes",
        page_icon="🏛️",
        layout="wide",
    )

    st.title("Assemblee Nationale - Analyse des scrutins (17e legislature)")
    st.caption("Qui vote quoi ? Quel parti vote quel type de texte ?")

    # Verifier que les donnees existent
    if not (PROCESSED_DIR / "scrutins.csv").exists():
        st.error("Donnees non trouvees. Execute d'abord: python download_data.py && python parse_data.py")
        return

    scrutins, votes, acteurs = load_data()

    # Navigation
    page = st.sidebar.radio(
        "Navigation",
        ["Vue d'ensemble", "Par parti", "Impact social", "Economie", "Par loi", "Axe politique", "Par scrutin", "Comparaison"],
    )

    # Filtres globaux dans la sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("Filtres")
    date_min = scrutins["date"].min().date()
    date_max = scrutins["date"].max().date()
    date_range = st.sidebar.date_input(
        "Periode",
        value=(date_min, date_max),
        min_value=date_min,
        max_value=date_max,
    )
    if len(date_range) == 2:
        mask_s = (scrutins["date"].dt.date >= date_range[0]) & (scrutins["date"].dt.date <= date_range[1])
        mask_v = (votes["date"].dt.date >= date_range[0]) & (votes["date"].dt.date <= date_range[1])
        scrutins = scrutins[mask_s]
        votes = votes[mask_v]

    if page == "Vue d'ensemble":
        page_vue_ensemble(scrutins, votes)
    elif page == "Par parti":
        page_par_parti(votes)
    elif page == "Impact social":
        page_impact_social(scrutins, votes)
    elif page == "Economie":
        page_economie(scrutins, votes)
    elif page == "Par loi":
        page_par_loi(scrutins, votes)
    elif page == "Axe politique":
        page_axe_politique(scrutins, votes)
    elif page == "Par scrutin":
        page_par_scrutin(scrutins, votes)
    elif page == "Comparaison":
        page_comparaison(votes)

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "Source: [data.assemblee-nationale.fr](https://data.assemblee-nationale.fr/)"
    )


if __name__ == "__main__":
    main()
