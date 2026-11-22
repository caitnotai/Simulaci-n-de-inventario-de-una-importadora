"""
MÓDULO 6 — GRÁFICAS DE RESULTADOS
=================================
Convierte los números en imágenes listas para las diapositivas (16:9).
Cada política tiene SIEMPRE el mismo color en todas las gráficas:
    A = azul · B = naranja · C = verde agua · D = amarillo
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # genera imágenes sin abrir ventanas
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from aleatoriedad import DIAS_POR_MES, generar_tiempos_entrega

# ---------------------------------------------------------------- ESTILO
FONDO = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
TINTA_SUAVE = "#898781"
GRILLA = "#e1e0d9"
EJE = "#c3c2b7"
CRITICO = "#d03b3b"            # solo para marcar faltantes (siempre con etiqueta)
COLORES_POLITICAS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
COLORES_COSTOS = {"Mantener": "#e87ba4", "Pedir": "#008300", "Faltantes": "#6250d6"}
COLOR_ENTRADAS = "#6250d6"
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
INICIO_MES = np.concatenate([[0], np.cumsum(DIAS_POR_MES)[:-1]])
TAMANO = (13.33, 7.5)

plt.rcParams.update({
    "figure.facecolor": FONDO, "axes.facecolor": FONDO, "savefig.facecolor": FONDO,
    "font.family": "sans-serif", "font.size": 12,
    "text.color": TINTA, "axes.labelcolor": TINTA_2,
    "xtick.color": TINTA_SUAVE, "ytick.color": TINTA_SUAVE,
    "axes.edgecolor": EJE, "axes.linewidth": 1,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRILLA, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "axes.titlesize": 14, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "legend.frameon": False,
})


def millones(x: float, decimales: int = 1) -> str:
    """72_030_000 -> '$72,0 M' (formato colombiano: coma decimal)."""
    return f"${x / 1e6:,.{decimales}f} M".replace(",", "X").replace(".", ",").replace("X", ".")


def numero(x: float, decimales: int = 0) -> str:
    return f"{x:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def porcentaje(n: float) -> str:
    """0.95 -> '95%' · 0.995 -> '99,5%' · 0.9999 -> '99,99%'."""
    return (f"{n * 100:.2f}".rstrip("0").rstrip(".") + "%").replace(".", ",")


NOMBRES_CORTOS = {"A": "Pedido fijo\ntrimestral", "B": "EOQ + ROP\nsin SS",
                  "C": "EOQ + ROP\n+ SS 95%", "D": "Revisión\ntrimestral (T,S)"}


def nombre_corto(nombre: str) -> str:
    letra = nombre[0]
    return f"{letra}. {NOMBRES_CORTOS.get(letra, nombre[3:])}"


CAJA_TEXTO = dict(boxstyle="round,pad=0.25", facecolor=FONDO, edgecolor="none", alpha=0.9)


def color_de(nombres: list) -> dict:
    return {n: COLORES_POLITICAS[i % len(COLORES_POLITICAS)] for i, n in enumerate(nombres)}


def _titulo(fig, titulo: str, subtitulo: str):
    fig.text(0.04, 0.955, titulo, fontsize=20, fontweight="bold", color=TINTA, ha="left")
    fig.text(0.04, 0.915, subtitulo, fontsize=12.5, color=TINTA_2, ha="left")


def _guardar(fig, carpeta: Path, nombre: str) -> Path:
    ruta = carpeta / nombre
    fig.savefig(ruta, dpi=150)
    plt.close(fig)
    return ruta


# ======================================================================
# 1. ENTRADAS ALEATORIAS DEL MODELO
# ======================================================================
def grafica_entradas(p, carpeta: Path) -> Path:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=TAMANO)
    fig.subplots_adjust(top=0.83, bottom=0.12, left=0.06, right=0.97, wspace=0.22)
    _titulo(fig, "Lo que el modelo NO controla: demanda y tiempo de entrega",
            "Dos variables aleatorias alimentan la simulación")

    # Demanda media por mes (estacionalidad)
    media_mes = [p.demanda_media_diaria * p.estacionalidad[m] for m in range(1, 13)]
    ax1.bar(MESES, media_mes, color=COLOR_ENTRADAS, width=0.62, edgecolor=FONDO, linewidth=2)
    ax1.axhline(p.demanda_media_diaria, color=TINTA_SUAVE, lw=1.2, ls="--")
    ax1.text(-0.45, p.demanda_media_diaria + 0.8, f"Promedio anual {numero(p.demanda_media_diaria)}",
             color=TINTA_2, fontsize=10.5, ha="left", va="bottom", bbox=CAJA_TEXTO)
    ax1.annotate(f"Diciembre: {numero(media_mes[11])}/día\n(primas y temporada)",
                 xy=(11, media_mes[11]), xytext=(7.3, media_mes[11] + 3),
                 fontsize=10.5, color=TINTA_2, arrowprops=dict(arrowstyle="-", color=TINTA_SUAVE))
    ax1.set_title("Demanda diaria promedio por mes (kits)", fontsize=12.5, pad=26)
    ax1.text(0, 1.015, f"Variación día a día: σ = {numero(p.demanda_desv_diaria)} kits · distribución normal",
             transform=ax1.transAxes, fontsize=10.5, color=TINTA_2, va="bottom")
    ax1.set_ylim(0, max(media_mes) * 1.25)
    ax1.grid(axis="x", visible=False)

    # Lead time
    rng = np.random.default_rng([p.semilla, 4242])
    lt = generar_tiempos_entrega(p, rng, 100_000)
    bins = np.arange(lt.min(), lt.max() + 2) - 0.5
    ax2.hist(lt, bins=bins, color=COLOR_ENTRADAS, edgecolor=FONDO, linewidth=1)
    ax2.axvline(lt.mean(), color=TINTA, lw=1.5)
    ax2.text(lt.mean() + 0.8, ax2.get_ylim()[1] * 0.92,
             f"Media {numero(lt.mean(), 1)} días\nσ = {numero(lt.std(), 1)} días",
             fontsize=10.5, color=TINTA, va="top")
    p95 = np.percentile(lt, 95)
    ax2.axvline(p95, color=TINTA_SUAVE, lw=1.2, ls="--")
    ax2.text(p95 + 0.8, ax2.get_ylim()[1] * 0.62, f"5 % de los pedidos\ntarda más de {numero(p95)} días",
             fontsize=10.5, color=TINTA_2, va="top")
    ax2.set_title("Tiempo de entrega de cada pedido (días)", fontsize=12.5, pad=26)
    ax2.text(0, 1.015, "Fabricación + barco + aduana + inspección (si toca)",
             transform=ax2.transAxes, fontsize=10.5, color=TINTA_2, va="bottom")
    ax2.set_xlabel("Días desde que se hace el pedido hasta que llega a bodega")
    ax2.set_ylabel("Frecuencia (100.000 pedidos simulados)")
    ax2.yaxis.set_major_formatter(lambda v, _: numero(v))
    ax2.grid(axis="x", visible=False)
    return _guardar(fig, carpeta, "01_entradas_aleatorias.png")


# ======================================================================
# 2. TRAYECTORIA DEL INVENTARIO (una réplica de ejemplo)
# ======================================================================
def grafica_trayectorias(ejemplos: dict, politicas: list, p, carpeta: Path) -> Path:
    colores = color_de([pol.nombre for pol in politicas])
    fig, ejes = plt.subplots(2, 2, figsize=TAMANO, sharex=True, sharey=True)
    fig.subplots_adjust(top=0.82, bottom=0.12, left=0.07, right=0.98, hspace=0.32, wspace=0.06)
    _titulo(fig, "Un año en la bodega con cada política",
            "Mismo año simulado (misma demanda y mismos tiempos de entrega) para las 4 políticas")
    inicio = p.dias_calentamiento
    dias = np.arange(p.dias_simulacion)
    ymax = max(ej.historia["posicion"][inicio:].max() for ej in ejemplos.values()) * 1.05

    for ax, pol in zip(ejes.flat, politicas):
        h = ejemplos[pol.nombre].historia
        inv = h["inventario"][inicio:]
        pos = h["posicion"][inicio:]
        faltante = (h["demanda"] - h["ventas"])[inicio:] > 0
        c = colores[pol.nombre]

        for d in dias[faltante]:
            ax.axvspan(d - 0.5, d + 0.5, color=CRITICO, alpha=0.25, lw=0)
        ax.plot(dias, pos, color=TINTA_SUAVE, lw=1.1, ls=(0, (4, 3)))
        ax.step(dias, inv, where="post", color=c, lw=2)
        if getattr(pol, "R", None):
            ax.axhline(pol.R, color=TINTA_2, lw=1, ls=":")
            ax.text(362, pol.R + ymax * 0.02, f"Punto de reorden {numero(pol.R)}",
                    fontsize=9.5, color=TINTA_2, ha="right", va="bottom", bbox=CAJA_TEXTO)
        pedidos = [d - inicio for d, _, _ in h["pedidos"] if d >= inicio]
        ax.plot(pedidos, [ymax * 0.03] * len(pedidos), ls="none", marker="^", ms=9,
                color=TINTA, markeredgecolor=FONDO, markeredgewidth=1.5)

        res = ejemplos[pol.nombre]
        ax.set_title(pol.nombre, fontsize=12.5)
        ax.text(0.99, 0.97, f"Costo {millones(res.costo_total)}  ·  perdió {numero(res.ventas_perdidas)} kits",
                transform=ax.transAxes, ha="right", va="top", fontsize=10, color=TINTA_2, bbox=CAJA_TEXTO)
        ax.set_ylim(0, ymax)
        ax.set_xlim(-2, 366)
        ax.yaxis.set_major_formatter(lambda v, _: numero(v))

    for ax in ejes[1]:
        ax.set_xticks(INICIO_MES + 15, MESES)
    for ax in ejes[:, 0]:
        ax.set_ylabel("Kits")
    leyenda = [
        Line2D([], [], color=TINTA_2, lw=2, label="Inventario en bodega (color de la política)"),
        Line2D([], [], color=TINTA_SUAVE, lw=1.1, ls=(0, (4, 3)), label="Posición = bodega + en camino"),
        Line2D([], [], ls="none", marker="^", color=TINTA, ms=9, label="Día en que se hace un pedido"),
        Patch(color=CRITICO, alpha=0.35, label="Día con ventas perdidas"),
    ]
    fig.legend(handles=leyenda, loc="lower center", ncol=4, fontsize=10.5, bbox_to_anchor=(0.5, 0.005))
    return _guardar(fig, carpeta, "02_trayectorias_inventario.png")


# ======================================================================
# 3. COSTO TOTAL DESGLOSADO POR POLÍTICA
# ======================================================================
def grafica_costos(resumen: pd.DataFrame, carpeta: Path, replicas: int) -> Path:
    fig, ax = plt.subplots(figsize=TAMANO)
    fig.subplots_adjust(top=0.80, bottom=0.14, left=0.25, right=0.93)
    mejor = resumen["Costo total (M COP)"].idxmin()
    _titulo(fig, f"La política {mejor[0]} es la más barata en condiciones normales",
            f"Costo anual promedio de {numero(replicas)} años simulados, en millones de pesos (intervalo de confianza 95 %)")

    politicas = list(resumen.index)[::-1]   # A arriba
    y = np.arange(len(politicas))
    izquierda = np.zeros(len(politicas))
    for comp, col in [("Mantener", "Mantener (M COP)"), ("Pedir", "Pedir (M COP)"), ("Faltantes", "Faltantes (M COP)")]:
        valores = resumen.loc[politicas, col].to_numpy()
        ax.barh(y, valores, left=izquierda, height=0.55, color=COLORES_COSTOS[comp],
                edgecolor=FONDO, linewidth=2, label=comp)
        for yi, (iz, v) in enumerate(zip(izquierda, valores)):
            if v > 6:
                ax.text(iz + v / 2, yi, numero(v, 1), ha="center", va="center", fontsize=10.5,
                        color="#ffffff", fontweight="bold")
        izquierda += valores

    for yi, pol in enumerate(politicas):
        tot = resumen.loc[pol, "Costo total (M COP)"]
        margen = resumen.loc[pol, "IC 95% sup (M COP)"] - tot
        peso = "bold" if pol == mejor else "normal"
        ax.text(izquierda[yi] + 1, yi, f"{millones(tot * 1e6)}  ± {numero(margen, 1)}",
                va="center", fontsize=12, fontweight=peso, color=TINTA)
    ax.set_yticks(y, politicas, fontsize=12)
    for etiqueta in ax.get_yticklabels():
        if etiqueta.get_text() == mejor:
            etiqueta.set_fontweight("bold")
        etiqueta.set_color(TINTA)
    ax.set_xlim(0, izquierda.max() * 1.2)
    ax.set_xlabel("Millones de COP por año")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower center", ncol=3, bbox_to_anchor=(0.4, -0.2), fontsize=11.5)
    return _guardar(fig, carpeta, "03_costo_por_politica.png")


# ======================================================================
# 4. DISTRIBUCIÓN DEL COSTO (RIESGO)
# ======================================================================
def grafica_distribucion(resultados: dict, carpeta: Path) -> Path:
    colores = color_de(list(resultados))
    fig, ax = plt.subplots(figsize=TAMANO)
    fig.subplots_adjust(top=0.80, bottom=0.12, left=0.25, right=0.95)
    _titulo(fig, "No solo importa el promedio: también el riesgo",
            "Distribución del costo anual en las réplicas · caja = 50 % central · bigotes = percentiles 5 y 95")
    nombres = list(resultados)[::-1]
    datos = [resultados[n]["costo_total"].to_numpy() / 1e6 for n in nombres]
    caja = ax.boxplot(datos, vert=False, widths=0.5, whis=(5, 95), patch_artist=True,
                      showfliers=True, medianprops=dict(color=FONDO, lw=2.5),
                      flierprops=dict(marker="o", ms=3, alpha=0.35, markeredgewidth=0))
    for i, n in enumerate(nombres):
        c = colores[n]
        caja["boxes"][i].set(facecolor=c, edgecolor=c)
        for parte in ("whiskers", "caps"):
            for linea in caja[parte][2 * i:2 * i + 2]:
                linea.set(color=c, lw=1.5)
        caja["fliers"][i].set(markerfacecolor=c)
        p95 = np.percentile(datos[i], 95)
        ax.text(np.max(datos[i]) + 0.6, i + 1, f"peor 5 %: más de {millones(p95 * 1e6)}",
                va="center", fontsize=10.5, color=TINTA_2)
    ax.set_yticks(range(1, len(nombres) + 1), nombres, fontsize=12, color=TINTA)
    ax.set_xlabel("Costo anual (millones de COP)")
    ax.set_xlim(right=max(d.max() for d in datos) * 1.18)
    ax.grid(axis="y", visible=False)
    return _guardar(fig, carpeta, "04_riesgo_distribucion_costos.png")


# ======================================================================
# 5. SENSIBILIDAD AL NIVEL DE SERVICIO
# ======================================================================
def grafica_sensibilidad(sens_normal: pd.DataFrame, sens_crisis: pd.DataFrame,
                         color_politica: str, carpeta: Path) -> Path:
    fig, ax = plt.subplots(figsize=TAMANO)
    fig.subplots_adjust(top=0.80, bottom=0.13, left=0.08, right=0.97)
    _titulo(fig, "¿Cuánto stock de seguridad conviene tener?",
            "Política EOQ + punto de reorden con distintos niveles de servicio objetivo · costo anual promedio")
    x = np.arange(len(sens_normal))
    etiquetas = [porcentaje(n) for n in sens_normal["nivel_servicio"]]

    for df, estilo, nombre in [(sens_normal, "-", "Condiciones normales"),
                               (sens_crisis, (0, (5, 3)), "Crisis logística")]:
        y = df["costo_total"].to_numpy() / 1e6
        ax.fill_between(x, df["ic_inf"] / 1e6, df["ic_sup"] / 1e6, color=color_politica, alpha=0.15, lw=0)
        ax.plot(x, y, color=color_politica, lw=2, ls=estilo, marker="o", ms=6,
                markeredgecolor=FONDO, markeredgewidth=2)
        i = int(np.argmin(y))
        ax.plot(x[i], y[i], marker="o", ms=13, color=color_politica, markeredgecolor=TINTA, markeredgewidth=2)
        normal = nombre.startswith("Cond")
        nota = "" if (normal or i < len(x) - 1) else "\n(sigue bajando: conviene recalcular la política)"
        ax.annotate(f"Mínimo {nombre.lower()}: {etiquetas[i]}\nSS = {numero(df['stock_seguridad'].iloc[i])} kits · "
                    f"{millones(df['costo_total'].iloc[i])}{nota}",
                    xy=(x[i], y[i]), xytext=(x[i] - 0.4, y[i] + (9 if normal else 17)),
                    fontsize=10.5, color=TINTA, ha="right", va="bottom", bbox=CAJA_TEXTO,
                    arrowprops=dict(arrowstyle="-", color=TINTA_SUAVE))
        ax.text(x[0] - 0.15, y[0], nombre, ha="right", va="center", fontsize=11, color=TINTA_2)

    ax.set_xticks(x, etiquetas)
    ax.set_xlim(-2.6, x[-1] + 0.4)
    ax.set_xlabel("Nivel de servicio objetivo (probabilidad de NO quedarse sin stock en cada ciclo)")
    ax.set_ylabel("Costo anual (millones de COP)")
    ax.grid(axis="x", visible=False)
    return _guardar(fig, carpeta, "05_sensibilidad_nivel_servicio.png")


# ======================================================================
# 6. ESCENARIO DE CRISIS LOGÍSTICA
# ======================================================================
def grafica_crisis(res_normal: pd.DataFrame, res_crisis: pd.DataFrame, carpeta: Path) -> Path:
    nombres = list(res_normal.index)
    colores = color_de(nombres)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=TAMANO)
    fig.subplots_adjust(top=0.78, bottom=0.2, left=0.06, right=0.98, wspace=0.2)
    _titulo(fig, "Prueba de estrés: ¿qué pasa si llega una crisis logística?",
            "Barcos más lentos e inspecciones el doble de frecuentes (como con la sequía del Canal de Panamá, 2023-24)")
    x = np.arange(len(nombres))
    ancho = 0.36
    for ax, col, titulo, fmt in [
        (ax1, "Costo total (M COP)", "Costo anual (millones de COP)", lambda v: numero(v, 1)),
        (ax2, "Ventas perdidas (kits)", "Ventas perdidas al año (kits)", lambda v: numero(v)),
    ]:
        for desplaz, df, rayado, alpha in [(-ancho / 2 - 0.01, res_normal, None, 1.0),
                                           (ancho / 2 + 0.01, res_crisis, "///", 0.55)]:
            vals = df.loc[nombres, col].to_numpy()
            barras = ax.bar(x + desplaz, vals, width=ancho, color=[colores[n] for n in nombres],
                            alpha=alpha, hatch=rayado, edgecolor=FONDO, linewidth=2)
            for b, v in zip(barras, vals):
                ax.text(b.get_x() + b.get_width() / 2, b.get_height(), fmt(v),
                        ha="center", va="bottom", fontsize=10, color=TINTA)
        ax.set_title(titulo, fontsize=13)
        ax.set_xticks(x, [nombre_corto(n) for n in nombres], fontsize=10.5, color=TINTA)
        ax.grid(axis="x", visible=False)
        ax.yaxis.set_major_formatter(lambda v, _: numero(v))
        ax.set_ylim(0, ax.get_ylim()[1] * 1.08)
    leyenda = [Patch(facecolor=TINTA_SUAVE, edgecolor=FONDO, label="Condiciones normales (sólido)"),
               Patch(facecolor=TINTA_SUAVE, alpha=0.55, hatch="///", edgecolor=FONDO, label="Crisis logística (rayado)")]
    fig.legend(handles=leyenda, loc="lower center", ncol=2, fontsize=11.5, bbox_to_anchor=(0.5, 0.0))
    return _guardar(fig, carpeta, "06_escenario_crisis.png")
