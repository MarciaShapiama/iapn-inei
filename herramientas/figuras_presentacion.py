"""Figuras adicionales para la presentación (docs/presentacion/figuras/). Uso: python herramientas/figuras_presentacion.py"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
from shapely.geometry import shape

R = Path(__file__).resolve().parents[1]
F = R / "docs" / "presentacion" / "figuras"
F.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 10, "font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})
AZ, NAR, GR = "#0b5d8f", "#e8710a", "#8a99a6"

# 1. Validación externa: rho de Spearman por tipo de peligro
v = json.load(open(R / "docs/evidencia/validacion_indeci.json", encoding="utf-8"))["por_tipo_de_peligro_afectados"]
vars_ = [("edificaciones_rp100", "Edificaciones\nzona 1/100"), ("personas_rp100", "Población\nzona 1/100"),
         ("km2_radar_2017", "Agua radar\n2017"), ("pct_area_rp100", "% área\nzona 1/100"), ("poblacion_worldpop_distrito", "Población total\n(referencia)")]
x = np.arange(len(vars_)); w = .38
fig, ax = plt.subplots(figsize=(8.4, 3.6))
for k, (tipo, col, lab) in enumerate((("solo_inundacion", AZ, "Afectados por inundación"), ("solo_lluvia_intensa", NAR, "Afectados por lluvia intensa"))):
    vals = [v[tipo][a]["rho"] for a, _ in vars_]
    ps = [v[tipo][a]["p"] for a, _ in vars_]
    b = ax.bar(x + (k - .5) * w, vals, w, color=col, label=lab)
    for xi, val, p in zip(x + (k - .5) * w, vals, ps):
        ax.text(xi, val + (0.015 if val >= 0 else -0.05), f"{val:.2f}{'*' if p < 0.05 else ''}", ha="center", fontsize=8.5)
ax.axhline(0, color="#444", lw=.8)
ax.set_xticks(x, [b for _, b in vars_]); ax.set_ylabel("ρ de Spearman (76 distritos)")
ax.legend(frameon=False, fontsize=9, loc="upper right"); ax.set_ylim(-0.2, 0.62)
ax.set_title("Validación externa: orden de distritos frente a registros INDECI 2003-2024  (* p < 0,05)", fontsize=10)
fig.tight_layout(); fig.savefig(F / "validacion_indeci.png", dpi=220); plt.close(fig)

# 2. Mapa de fases de expansión
g = json.load(open(R / "data/departamentos.geojson", encoding="utf-8"))
FASE = {"TUMBES": 0, "PIURA": 0, "LAMBAYEQUE": 1, "LA LIBERTAD": 1, "CAJAMARCA": 2, "ANCASH": 2}
COL = {0: "#d4145a", 1: "#f2b134", 2: "#7fb4e0", 3: "#e7ecef"}
fig, ax = plt.subplots(figsize=(4.6, 6.2))
for f in g["features"]:
    gm = shape(f["geometry"]); fase = FASE.get(f["properties"]["NOMBDEP"], 3)
    for p in (gm.geoms if gm.geom_type == "MultiPolygon" else [gm]):
        a = np.array(p.exterior.coords); ax.fill(a[:, 0], a[:, 1], color=COL[fase], ec="#5b6770", lw=.4)
ax.set_aspect(1 / np.cos(np.radians(9))); ax.axis("off")
ax.legend(handles=[Patch(color=COL[0], label="Piloto (hecho): Tumbes, Piura"),
                   Patch(color=COL[1], label="Fase 1: Lambayeque, La Libertad"),
                   Patch(color=COL[2], label="Fase 2: Cajamarca, Áncash"),
                   Patch(color=COL[3], label="Fase 3: resto del Perú")], loc="lower left", fontsize=10, frameon=False)
fig.tight_layout(); fig.savefig(F / "fases_expansion.png", dpi=220); plt.close(fig)
print(sorted(p.name for p in F.glob("*.png")))
