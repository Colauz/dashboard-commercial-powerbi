"""
Recalcule en pandas les mesures clés du rapport Power BI.

Double usage :
  - vérifier que les mesures DAX renvoient bien les mêmes chiffres (test de non-régression) ;
  - alimenter la fiche projet du portfolio avec des chiffres réels, pas approximatifs.

Usage :
    python apercu_kpi.py [--json docs/kpi.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

DOSSIER_DATA = Path(__file__).parent / "data"


def charger() -> dict[str, pd.DataFrame]:
    tables = {}
    for nom in ("dim_date", "dim_client", "dim_produit", "dim_commercial", "fait_ventes", "fait_objectifs"):
        tables[nom] = pd.read_csv(DOSSIER_DATA / f"{nom}.csv")
    tables["dim_date"]["date"] = pd.to_datetime(tables["dim_date"]["date"])
    return tables


def calculer(tables: dict[str, pd.DataFrame]) -> dict:
    ventes = (
        tables["fait_ventes"]
        .merge(tables["dim_date"][["cle_date", "date", "annee", "annee_mois"]], on="cle_date")
        .merge(tables["dim_client"][["cle_client", "raison_sociale", "segment"]], on="cle_client")
        .merge(tables["dim_produit"][["cle_produit", "libelle_produit", "famille"]], on="cle_produit")
        .merge(tables["dim_commercial"][["cle_commercial", "nom_commercial", "agence"]], on="cle_commercial")
    )
    ventes["marge"] = ventes["ca_ht"] - ventes["cout_achat_total_ht"]

    ca_total = ventes["ca_ht"].sum()
    marge_totale = ventes["marge"].sum()

    # Pareto client : combien de clients font 80 % du chiffre ?
    # On groupe sur la clé, pas sur la raison sociale : deux clients distincts
    # peuvent porter le même nom, et le numérateur doit compter comme le dénominateur.
    par_client = ventes.groupby("cle_client")["ca_ht"].sum().sort_values(ascending=False)
    part_cumulee = par_client.cumsum() / ca_total
    clients_80 = int((part_cumulee <= 0.80).sum() + 1)

    # Croissance sur les 12 derniers mois glissants contre les 12 précédents.
    fin = ventes["date"].max()
    recents = ventes[ventes["date"] > fin - pd.DateOffset(months=12)]["ca_ht"].sum()
    precedents = ventes[
        (ventes["date"] > fin - pd.DateOffset(months=24)) & (ventes["date"] <= fin - pd.DateOffset(months=12))
    ]["ca_ht"].sum()

    # Atteinte des objectifs sur les mois clos uniquement.
    objectifs = tables["fait_objectifs"]
    reel_mois = ventes.groupby(["cle_commercial", "annee_mois"], as_index=False)["ca_ht"].sum()
    suivi = objectifs.merge(reel_mois, on=["cle_commercial", "annee_mois"], how="left").fillna({"ca_ht": 0})
    suivi["atteint"] = suivi["ca_ht"] >= suivi["objectif_ca_ht"]

    par_famille = ventes.groupby("famille").agg(ca=("ca_ht", "sum"), marge=("marge", "sum"))
    par_famille["taux_marge"] = par_famille["marge"] / par_famille["ca"]

    return {
        "periode": {"debut": str(ventes["date"].min().date()), "fin": str(fin.date())},
        "ca_ht": round(float(ca_total), 2),
        "marge_brute": round(float(marge_totale), 2),
        "taux_marge": round(float(marge_totale / ca_total), 4),
        "nb_lignes_ventes": int(len(ventes)),
        "nb_commandes": int(ventes["numero_commande"].nunique()),
        "panier_moyen": round(float(ca_total / ventes["numero_commande"].nunique()), 2),
        "nb_clients_actifs": int(ventes["cle_client"].nunique()),
        "clients_faisant_80pct_du_ca": clients_80,
        "part_clients_faisant_80pct": round(clients_80 / ventes["cle_client"].nunique(), 4),
        "croissance_12m": round(float(recents / precedents - 1), 4),
        "taux_atteinte_objectifs": round(float(suivi["atteint"].mean()), 4),
        "remise_moyenne_ponderee": round(
            float(1 - ca_total / (ventes["ca_ht"] / (1 - ventes["taux_remise"])).sum()), 4
        ),
        "familles": {
            nom: {"ca": round(float(r.ca), 2), "taux_marge": round(float(r.taux_marge), 4)}
            for nom, r in par_famille.sort_values("ca", ascending=False).iterrows()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", type=Path, default=Path(__file__).parent / "docs" / "kpi.json")
    args = parser.parse_args()

    kpi = calculer(charger())
    args.json.parent.mkdir(exist_ok=True)
    args.json.write_text(json.dumps(kpi, indent=2, ensure_ascii=False), encoding="utf-8")

    euro = lambda v: f"{v:,.0f} €".replace(",", " ")
    print(f"Période                : {kpi['periode']['debut']} → {kpi['periode']['fin']}")
    print(f"CA HT                  : {euro(kpi['ca_ht'])}")
    print(f"Marge brute            : {euro(kpi['marge_brute'])} ({kpi['taux_marge']:.1%})")
    print(f"Commandes              : {kpi['nb_commandes']:,}".replace(",", " "))
    print(f"Panier moyen           : {euro(kpi['panier_moyen'])}")
    print(f"Croissance 12 mois     : {kpi['croissance_12m']:+.1%}")
    print(f"Concentration          : {kpi['clients_faisant_80pct_du_ca']} clients "
          f"({kpi['part_clients_faisant_80pct']:.0%}) font 80 % du CA")
    print(f"Objectifs mensuels tenus: {kpi['taux_atteinte_objectifs']:.0%}")
    print(f"\nFiche écrite : {args.json}")


if __name__ == "__main__":
    main()
