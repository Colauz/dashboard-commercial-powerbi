#!/usr/bin/env python3
"""
Planche d'indicateurs calculée sur le jeu de données généré.

Ce n'est pas une maquette du rapport Power BI : ce sont les mêmes indicateurs,
calculés en pandas depuis les CSV du schéma en étoile, et tracés avec la charte
du projet. Ils servent à deux choses — présenter le contenu du modèle, et
vérifier que les mesures DAX renvoient bien les mêmes valeurs.

    python apercu_visuel.py [--sortie docs/apercu-indicateurs.png]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

from apercu_kpi import charger

ENCRE = "#14181A"
ENCRE_DOUCE = "#4E565A"
ENCRE_TENUE = "#757E82"
TRAIT = "#D5D9D1"
SURFACE = "#FBFBF9"
ACCENT = "#15619E"
ACCENT_CLAIR = "#8FB6D4"
ALERTE = "#B3462F"

MOIS_COURTS = ["jan", "fév", "mar", "avr", "mai", "juin",
               "juil", "août", "sep", "oct", "nov", "déc"]


def charte() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "axes.edgecolor": TRAIT, "axes.labelcolor": ENCRE_DOUCE,
        "axes.titlecolor": ENCRE, "axes.titlesize": 12, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "axes.titlepad": 14,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": ENCRE_TENUE, "ytick.color": ENCRE_TENUE,
        "xtick.labelsize": 9, "ytick.labelsize": 9,
        "grid.color": TRAIT, "grid.linewidth": 0.7,
        "font.family": "DejaVu Sans", "legend.frameon": False,
        "legend.fontsize": 9.5,
    })


def preparer(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    ventes = (
        tables["fait_ventes"]
        .merge(tables["dim_date"][["cle_date", "date", "annee", "mois_numero"]], on="cle_date")
        .merge(tables["dim_client"][["cle_client", "raison_sociale"]], on="cle_client")
        .merge(tables["dim_produit"][["cle_produit", "famille"]], on="cle_produit")
        .merge(tables["dim_commercial"][["cle_commercial", "nom_commercial", "agence"]], on="cle_commercial")
    )
    ventes["marge"] = ventes["ca_ht"] - ventes["cout_achat_total_ht"]
    return ventes


def tracer_mensuel(ax, ventes: pd.DataFrame) -> None:
    """Deux exercices comparés. Le trait plein et le pointillé distinguent les
    séries autant que la couleur — lisible aussi en noir et blanc."""
    pivot = (ventes.groupby(["annee", "mois_numero"])["ca_ht"].sum()
             .unstack("annee").reindex(range(1, 13)))
    annees = sorted(a for a in pivot.columns if pivot[a].notna().sum() >= 6)[-2:]
    courante, precedente = annees[-1], annees[-2]

    ax.plot(pivot.index, pivot[precedente] / 1000, color=ACCENT_CLAIR, linewidth=2,
            linestyle="--", marker="o", markersize=4, label=str(precedente))
    ax.plot(pivot.index, pivot[courante] / 1000, color=ACCENT, linewidth=2.4,
            marker="o", markersize=5, label=str(courante))

    dernier = pivot[courante].last_valid_index()
    ax.annotate(f"{pivot.loc[dernier, courante] / 1000:.0f} k€",
                xy=(dernier, pivot.loc[dernier, courante] / 1000),
                xytext=(6, 4), textcoords="offset points",
                fontsize=9, fontweight="bold", color=ACCENT)

    ax.set_title("Chiffre d'affaires mensuel, deux exercices comparés")
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(MOIS_COURTS)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:,.0f} k€".replace(",", " ")))
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.legend(loc="lower left", ncol=2)


def tracer_pareto(ax, ventes: pd.DataFrame) -> None:
    par_client = ventes.groupby("cle_client")["ca_ht"].sum().sort_values(ascending=False)
    cumul = par_client.cumsum() / par_client.sum() * 100
    rangs = np.arange(1, len(cumul) + 1) / len(cumul) * 100
    seuil = int((cumul <= 80).sum() + 1)
    part_clients = seuil / len(cumul) * 100

    ax.fill_between(rangs, cumul, color=ACCENT, alpha=0.10)
    ax.plot(rangs, cumul, color=ACCENT, linewidth=2.2)
    ax.axhline(80, color=ALERTE, linestyle="--", linewidth=1.4)
    ax.axvline(part_clients, color=ALERTE, linestyle="--", linewidth=1.4)
    ax.plot([part_clients], [80], marker="o", markersize=8, color=ALERTE, zorder=5)

    ax.annotate(f"{seuil} clients sur {len(cumul)} ({part_clients:.0f} %)\nfont 80 % du chiffre",
                xy=(part_clients, 80), xytext=(part_clients + 6, 46),
                fontsize=9.5, color=ENCRE, fontweight="bold",
                arrowprops=dict(arrowstyle="-", color=ENCRE_TENUE, lw=1))

    ax.set_title("Concentration du portefeuille client")
    ax.set_xlabel("part du portefeuille, du plus gros client au plus petit")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 103)
    ax.xaxis.set_major_formatter(ticker.PercentFormatter())
    ax.yaxis.set_major_formatter(ticker.PercentFormatter())
    ax.grid(axis="y")
    ax.set_axisbelow(True)


def tracer_familles(ax, ventes: pd.DataFrame) -> None:
    """CA en longueur de barre, taux de marge en étiquette : une seule échelle,
    jamais deux axes superposés."""
    table = ventes.groupby("famille").agg(ca=("ca_ht", "sum"), marge=("marge", "sum"))
    table["taux"] = table["marge"] / table["ca"]
    table = table.sort_values("ca")

    ax.barh(table.index, table["ca"] / 1e6, color=ACCENT, height=0.6)
    for y, (_, ligne) in enumerate(table.iterrows()):
        ax.text(ligne["ca"] / 1e6 + 0.08, y, f"{ligne['ca'] / 1e6:.1f} M€   marge {ligne['taux']:.0%}",
                va="center", fontsize=9, color=ENCRE_DOUCE)

    ax.set_title("Chiffre d'affaires et taux de marge par famille")
    ax.set_xlim(0, table["ca"].max() / 1e6 * 1.62)
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.grid(False)
    ax.tick_params(axis="y", labelsize=9.5)


def tracer_objectifs(ax, ventes: pd.DataFrame, objectifs: pd.DataFrame,
                     dim_commercial: pd.DataFrame) -> None:
    ventes = ventes.copy()
    ventes["annee_mois"] = pd.to_datetime(ventes["date"]).dt.strftime("%Y-%m")
    reel = ventes.groupby(["cle_commercial", "annee_mois"], as_index=False)["ca_ht"].sum()
    suivi = objectifs.merge(reel, on=["cle_commercial", "annee_mois"], how="left").fillna({"ca_ht": 0})

    # Part des mois où l'objectif est tenu, plutôt que le cumul annuel : sur
    # 33 mois le cumul lisse tout et place chacun à 103 %, ce qui ne dit rien.
    suivi["tenu"] = suivi["ca_ht"] >= suivi["objectif_ca_ht"]
    par_vendeur = (suivi.groupby("cle_commercial", as_index=False)["tenu"].mean()
                   .rename(columns={"tenu": "atteinte"})
                   .merge(dim_commercial[["cle_commercial", "nom_commercial", "agence"]], on="cle_commercial")
                   .sort_values("atteinte"))

    etiquettes = [f"{n.split()[0][0]}. {n.split()[-1]}" for n in par_vendeur["nom_commercial"]]
    ax.barh(etiquettes, par_vendeur["atteinte"] * 100, color=ACCENT, height=0.62)
    moyenne = par_vendeur["atteinte"].mean() * 100
    ax.axvline(moyenne, color=ALERTE, linestyle="--", linewidth=1.4)
    ax.text(moyenne, len(etiquettes) - 0.3, f" moyenne {moyenne:.0f} %",
            fontsize=8.5, color=ALERTE, fontweight="bold")

    for y, valeur in enumerate(par_vendeur["atteinte"]):
        ax.text(valeur * 100 + 1.2, y, f"{valeur:.0%}", va="center", fontsize=9, color=ENCRE_DOUCE)

    ax.set_title("Part des mois où l'objectif mensuel est tenu")
    ax.set_xlim(0, max(par_vendeur["atteinte"].max() * 100 * 1.22, 100))
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.grid(False)
    ax.tick_params(axis="y", labelsize=9.5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sortie", type=Path,
                        default=Path(__file__).parent / "docs" / "apercu-indicateurs.png")
    args = parser.parse_args()

    charte()
    tables = charger()
    ventes = preparer(tables)

    figure, axes = plt.subplots(2, 2, figsize=(14.5, 9.2))
    figure.subplots_adjust(hspace=0.42, wspace=0.26, left=0.06, right=0.97, top=0.88, bottom=0.07)

    tracer_mensuel(axes[0, 0], ventes)
    tracer_pareto(axes[0, 1], ventes)
    tracer_familles(axes[1, 0], ventes)
    tracer_objectifs(axes[1, 1], ventes, tables["fait_objectifs"], tables["dim_commercial"])

    ca = ventes["ca_ht"].sum()
    marge = ventes["marge"].sum()
    figure.suptitle("Voltéa Distribution — indicateurs commerciaux", x=0.06, y=0.965,
                    ha="left", fontsize=16, fontweight="bold", color=ENCRE)
    figure.text(0.06, 0.925,
                f"{len(ventes):,} lignes de commande  ·  {ca / 1e6:.1f} M€ HT  ·  "
                f"marge brute {marge / 1e6:.2f} M€ ({marge / ca:.1%})  ·  "
                f"{ventes['cle_client'].nunique()} clients  ·  janvier 2024 – septembre 2026"
                .replace(",", " "),
                ha="left", fontsize=10, color=ENCRE_TENUE)

    args.sortie.parent.mkdir(exist_ok=True)
    figure.savefig(args.sortie, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    print(f"{args.sortie}")


if __name__ == "__main__":
    main()
