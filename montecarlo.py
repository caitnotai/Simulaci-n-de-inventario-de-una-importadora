"""
MÓDULO 5 — EXPERIMENTOS MONTE CARLO Y ANÁLISIS ESTADÍSTICO
==========================================================
Una sola corrida no dice nada: puede que justo ese año el barco llegara rápido.
Por eso se repite el año MUCHAS veces (réplicas) y se analizan los promedios
con su INTERVALO DE CONFIANZA. Eso es el MÉTODO DE MONTE CARLO.

En el mundo empresarial esto se usa para ANÁLISIS DE ESCENARIOS y ANÁLISIS DE
RIESGO: probar decisiones en un "gemelo digital" antes de arriesgar plata real.

Experimentos que corre este módulo:
  1. Comparación de las 4 políticas (escenario normal).
  2. Comparación pareada: ¿la diferencia entre políticas es real o es suerte?
  3. Sensibilidad: ¿qué nivel de servicio (stock de seguridad) conviene más?
  4. Escenario de crisis logística: ¿qué política aguanta mejor un golpe?
  5. Robustez al inventario inicial (sesgo de inicialización).
"""

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from aleatoriedad import generar_escenario
from parametros import ParametrosCaso
from politicas import construir_politica_qr
from simulador import simular


def intervalo_confianza(datos, nivel: float = 0.95) -> tuple[float, float, float]:
    """Media e intervalo de confianza:  media ± z · s / sqrt(n).
    Con cientos de réplicas, la t de Student ≈ normal, por eso se usa z."""
    datos = np.asarray(datos, dtype=float)
    n = len(datos)
    media = datos.mean()
    if n < 2:
        return media, media, media
    z = NormalDist().inv_cdf(0.5 + nivel / 2)
    margen = z * datos.std(ddof=1) / math.sqrt(n)
    return media, media - margen, media + margen


def correr_montecarlo(politicas: list, p: ParametrosCaso, replicas: int | None = None,
                      guardar_ejemplo: bool = True, progreso=None):
    """Corre todas las políticas sobre las mismas réplicas (números aleatorios comunes).

    Devuelve:
      resultados: dict nombre_politica -> DataFrame (una fila por réplica)
      ejemplos:   dict nombre_politica -> ResultadoCorrida de la réplica 0 con historia
    """
    replicas = replicas or p.replicas
    filas = {pol.nombre: [] for pol in politicas}
    ejemplos = {}
    for r in range(replicas):
        escenario = generar_escenario(p, r)  # el MISMO futuro para todas las políticas
        for pol in politicas:
            guardar = guardar_ejemplo and r == 0
            res = simular(pol, escenario, p, guardar_historia=guardar)
            filas[pol.nombre].append(res.como_dict(p.dias_simulacion))
            if guardar:
                ejemplos[pol.nombre] = res
        if progreso:
            progreso((r + 1) / replicas)
    resultados = {nombre: pd.DataFrame(f) for nombre, f in filas.items()}
    return resultados, ejemplos


def tabla_resumen(resultados: dict) -> pd.DataFrame:
    """Tabla con el promedio de cada indicador por política + IC 95 % del costo total."""
    filas = []
    for nombre, df in resultados.items():
        media, li, ls = intervalo_confianza(df["costo_total"])
        filas.append({
            "Política": nombre,
            "Costo total (M COP)": media / 1e6,
            "IC 95% inf (M COP)": li / 1e6,
            "IC 95% sup (M COP)": ls / 1e6,
            "Mantener (M COP)": df["costo_mantener"].mean() / 1e6,
            "Pedir (M COP)": df["costo_pedido"].mean() / 1e6,
            "Faltantes (M COP)": df["costo_faltante"].mean() / 1e6,
            "Fill rate (%)": df["fill_rate"].mean() * 100,
            "Días con faltante (%)": df["pct_dias_con_faltante"].mean() * 100,
            "Ventas perdidas (kits)": df["ventas_perdidas"].mean(),
            "Inventario prom. (kits)": df["inventario_promedio"].mean(),
            "Pedidos/año": df["num_pedidos"].mean(),
            "Prob. de perder >500 kits (%)": (df["ventas_perdidas"] > 500).mean() * 100,
        })
    return pd.DataFrame(filas).set_index("Política")


def comparacion_pareada(resultados: dict, base: str) -> pd.DataFrame:
    """Compara cada política contra `base` réplica por réplica.
    Como todas vieron el mismo futuro, se resta réplica a réplica (prueba pareada).
    Si el intervalo de la diferencia NO contiene el 0, la diferencia es
    estadísticamente significativa (no es cuestión de suerte)."""
    costo_base = resultados[base]["costo_total"].to_numpy()
    filas = []
    for nombre, df in resultados.items():
        if nombre == base:
            continue
        dif = df["costo_total"].to_numpy() - costo_base
        media, li, ls = intervalo_confianza(dif)
        filas.append({
            "Política": nombre,
            f"Diferencia vs {base[:2].strip()} (M COP)": media / 1e6,
            "IC 95% inf": li / 1e6,
            "IC 95% sup": ls / 1e6,
            "¿Significativa?": "Sí" if (li > 0 or ls < 0) else "No",
            "Réplicas donde la base gana (%)": (dif > 0).mean() * 100,
        })
    return pd.DataFrame(filas).set_index("Política")


def robustez_inventario_inicial(politicas: list, p: ParametrosCaso, rangos=None,
                                replicas: int = 300) -> pd.DataFrame:
    """Corre las políticas arrancando con distintos rangos de inventario inicial.
    Una política con RETROALIMENTACIÓN (mira la bodega) debe dar casi lo mismo
    sin importar cómo arranca. Una que no mira la bodega queda 'marcada' por su arranque."""
    if rangos is None:
        rangos = [(1_500, 4_000), (2_500, 8_000), (6_000, 9_000)]
    filas = []
    for minimo, maximo in rangos:
        pr = p.con_cambios(inventario_inicial_min=minimo, inventario_inicial_max=maximo)
        res, _ = correr_montecarlo(politicas, pr, replicas=replicas, guardar_ejemplo=False)
        tabla = tabla_resumen(res)
        for nombre in tabla.index:
            filas.append({"Inventario inicial": f"{minimo:,}–{maximo:,}", "Política": nombre,
                          "Costo total (M COP)": tabla.loc[nombre, "Costo total (M COP)"],
                          "Fill rate (%)": tabla.loc[nombre, "Fill rate (%)"]})
    return pd.DataFrame(filas)


def sensibilidad_nivel_servicio(p: ParametrosCaso, lt_media: float, lt_desv: float,
                                niveles=None, replicas: int = 500, progreso=None) -> pd.DataFrame:
    """Varía el nivel de servicio objetivo de la política (Q, R) y mide el costo.
    Más stock de seguridad = más costo de mantener pero menos faltantes.
    El punto más bajo de la curva es el nivel de servicio ÓPTIMO."""
    if niveles is None:
        niveles = [0.50, 0.70, 0.80, 0.85, 0.90, 0.95, 0.97, 0.99, 0.995, 0.999, 0.9999]
    escenarios = [generar_escenario(p, r) for r in range(replicas)]
    filas = []
    for i, nivel in enumerate(niveles):
        pol = construir_politica_qr(p, lt_media, lt_desv, nivel, f"SS {nivel:.1%}")
        res = [simular(pol, esc, p) for esc in escenarios]
        costos = [x.costo_total for x in res]
        media, li, ls = intervalo_confianza(costos)
        filas.append({
            "nivel_servicio": nivel,
            "stock_seguridad": pol.stock_seguridad,
            "punto_reorden": pol.R,
            "costo_total": media,
            "ic_inf": li,
            "ic_sup": ls,
            "costo_mantener": np.mean([x.costo_mantener for x in res]),
            "costo_pedido": np.mean([x.costo_pedido for x in res]),
            "costo_faltante": np.mean([x.costo_faltante for x in res]),
            "fill_rate": np.mean([x.fill_rate for x in res]),
        })
        if progreso:
            progreso((i + 1) / len(niveles))
    return pd.DataFrame(filas)
