"""Figuras para el informe de avance en LaTeX (docs/6_presentacion/avance_latex/figuras/). Uso: python herramientas/figuras/figuras_avance.py"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

R = Path(__file__).resolve().parents[2]
F = R / "docs" / "6_presentacion" / "avance_latex" / "figuras"
F.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 9, "font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})
AZ, NAR, GR = "#0b5d8f", "#e8710a", "#8a99a6"

# 1. Mapa: zona 1/100, distritos coloreados por prioridad
dist = json.load(open(R / "dashboard/data/distritos_tumbes_piura.geojson", encoding="utf-8"))
capa = json.load(open(R / "dashboard/data/capa_rp100.geojson", encoding="utf-8"))
panel = pd.read_csv(R / "dashboard/data/descargas/panel_distritos.csv")
prio = {(r.provincia, r.distrito): r.prioridad_revision for r in panel.itertuples()}
COL = {"Alta": "#d4145a", "Media": "#f2b134", "Baja": "#cfe3ec", "Sin dato suficiente": "#eeeeee"}
fig, ax = plt.subplots(figsize=(6.2, 7.4))
def poligonos(geom):
    cs = geom["coordinates"]
    return [p[0] for p in cs] if geom["type"] == "MultiPolygon" else [cs[0]]
for f in dist["features"]:
    c = COL[prio.get((f["properties"]["provincia"], f["properties"]["distrito"]), "Sin dato suficiente")]
    for anillo in poligonos(f["geometry"]):
        a = np.array(anillo); ax.fill(a[:, 0], a[:, 1], color=c, ec="#55606a", lw=0.3, zorder=1)
for f in capa["features"]:
    for anillo in poligonos(f["geometry"]):
        a = np.array(anillo); ax.fill(a[:, 0], a[:, 1], color="#08519c", alpha=0.55, lw=0, zorder=2)
ax.set_aspect(1 / np.cos(np.radians(5))); ax.set_xlabel("Longitud"); ax.set_ylabel("Latitud")
ax.legend(handles=[Patch(color="#08519c", alpha=.55, label="Zona inundable 1 en 100 años (JRC)")] +
          [Patch(color=COL[k], label=f"Prioridad de revisión: {k}") for k in ("Alta", "Media", "Baja")], loc="lower left", fontsize=7.5, frameon=True)
ax.set_title("Tumbes y Piura: zona inundable y prioridad relativa por distrito", fontsize=10)
fig.tight_layout(); fig.savefig(F / "mapa_prioridad.png", dpi=220); plt.close(fig)

# 2. Antes / después de la corrección de población
d = pd.read_csv(R / "docs/evidencia/cifras_antes_despues.csv")
p = d[d.indicador == "personas (dentro)"].set_index("escenario")
orden = ["rp10", "rp100", "2017", "2023", "vivo"]
fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.8), gridspec_kw={"width_ratios": [1, 1.4]})
for ax, ks in zip(axs, (["rp10", "rp100"], ["2017", "2023", "vivo"])):
    x = np.arange(len(ks)); w = .38
    ax.bar(x - w / 2, p.loc[ks, "publicado_antes"], w, color=GR, label="publicado antes")
    ax.bar(x + w / 2, p.loc[ks, "corregido"], w, color=AZ, label="corregido")
    for i, k in enumerate(ks):
        ax.text(i + w / 2, p.loc[k, "corregido"], f"{p.loc[k, 'corregido']:,.0f}".replace(",", " "), ha="center", va="bottom", fontsize=7)
        ax.text(i - w / 2, p.loc[k, "publicado_antes"], f"{p.loc[k, 'publicado_antes']:,.0f}".replace(",", " "), ha="center", va="bottom", fontsize=7, color="#555")
    ax.set_xticks(x, [{"rp10": "1 en 10", "rp100": "1 en 100", "2017": "Radar 2017", "2023": "Radar 2023", "vivo": "Radar 24 días"}[k] for k in ks])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " ")))
axs[0].set_ylabel("Personas dentro de la mancha"); axs[0].legend(fontsize=7, frameon=False, loc="upper left", bbox_to_anchor=(0, 1.18), ncol=2)
fig.suptitle("Población potencialmente expuesta antes y después de corregir la alineación de WorldPop", fontsize=9.5)
fig.tight_layout(); fig.savefig(F / "antes_despues_poblacion.png", dpi=220); plt.close(fig)

# 3. Métricas ML con IC 90 %
m = json.load(open(R / "docs/evidencia/ml_evaluacion.json", encoding="utf-8"))["incertidumbre"]
mods = ["climatologia", "logistica_simple", "logistica_completa", "lightgbm"]
nom = ["Climatología\n(línea base)", "Logística\nsimple", "Logística\ncompleta", "LightGBM"]
v = np.array([m[k]["pr_auc"] for k in mods]); lo = np.array([m[k]["pr_auc_ic90"][0] for k in mods]); hi = np.array([m[k]["pr_auc_ic90"][1] for k in mods])
fig, ax = plt.subplots(figsize=(5.6, 2.8))
ax.errorbar(range(4), v, yerr=[v - lo, hi - v], fmt="o", color=AZ, ecolor=AZ, capsize=4)
ax.axhline(m["climatologia"]["pr_auc"], color=NAR, ls="--", lw=1, label="climatología")
ax.axhline(0.010, color=GR, ls=":", lw=1, label="azar (tasa base 1 %)")
for i, x in enumerate(v): ax.text(i + .08, x, f"{x:.3f}", va="center", fontsize=7.5)
ax.set_xticks(range(4), nom); ax.set_ylabel("PR-AUC (IC 90 %, bootstrap por años)"); ax.legend(fontsize=7, frameon=False)
ax.set_title("Caso C: emergencia en 4 semanas, validación 2008-2015", fontsize=9.5)
fig.tight_layout(); fig.savefig(F / "ml_pr_auc.png", dpi=220); plt.close(fig)

# 4. Alineación de la población: correlación vs desplazamiento
import rasterio, sys
sys.path.insert(0, str(R / "src"))
from reparar_poblacion import desplazamiento_optimo  # noqa: E402
with rasterio.open(R / "data/exposicion/poblacion_100m.tif") as s:
    pob, t = s.read(1).astype("float64"), s.transform
edif = pd.read_parquet(R / "data/exposicion/viviendas.parquet")
xs, rs = [], []
for dx in sorted(set(list(range(-102, 23, 4)) + [-86, 0])):
    _, r = desplazamiento_optimo(pob, t, edif, [dx]); xs.append(dx); rs.append(r)
o = np.argsort(xs); xs = [xs[i] for i in o]; rs = [rs[i] for i in o]
fig, ax = plt.subplots(figsize=(5.6, 2.5))
ax.plot(xs, rs, color=AZ, marker="o", ms=3)
r_pub = rs[xs.index(-86)] if -86 in xs else None
ax.axvline(-86, color=NAR, ls="--", lw=1); ax.text(-84, max(rs) * .55, f"ráster publicado\n(r = {r_pub:.2f})", fontsize=7, color=NAR)
ax.axvline(0, color="#1b7f4b", ls="--", lw=1); ax.text(-24, max(rs) * .9, f"corregido (r = {max(rs):.2f})", fontsize=7, color="#1b7f4b")
ax.set_xlabel("Desplazamiento este-oeste respecto del ráster corregido (columnas de ~92 m)"); ax.set_ylabel("Correlación con edificaciones")
ax.set_title("Prueba independiente de alineación: WorldPop frente a Open Buildings", fontsize=9.5)
fig.tight_layout(); fig.savefig(F / "alineacion_poblacion.png", dpi=220); plt.close(fig)
print("figuras:", sorted(x.name for x in F.glob("*.png")))
