"""
MÓDULO 2 — GENERACIÓN DE VARIABLES ALEATORIAS
=============================================
Aquí se "inventa" la incertidumbre del negocio usando distribuciones de
probabilidad. Es el equivalente al módulo CREATE de Arena con sus
distribuciones (UNIF, TRIA, NORM...).

Dos variables aleatorias mandan en este problema:
  1. DEMANDA diaria  -> cuántos kits piden los clientes cada día.
  2. TIEMPO DE ENTREGA (lead time) -> cuántos días tarda en llegar un pedido.

Concepto clave: NÚMEROS ALEATORIOS COMUNES (Common Random Numbers).
Para comparar políticas de forma justa, TODAS se prueban contra el MISMO
"futuro" (mismas demandas y mismos tiempos de entrega). Así, si una política
sale mejor, es por la política y no porque le tocó un año con suerte.
Esto en simulación se llama técnica de REDUCCIÓN DE VARIANZA.
"""

from dataclasses import dataclass

import numpy as np

from parametros import ParametrosCaso

DIAS_POR_MES = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
# MES_DEL_DIA[k] = número de mes (1..12) del día k del año (0..364)
MES_DEL_DIA = np.repeat(np.arange(1, 13), DIAS_POR_MES)


@dataclass
class Escenario:
    """Un "futuro posible" del negocio: lo que va a pasar en una réplica."""
    demanda: np.ndarray            # demanda de cada día (kits)
    tiempos_entrega: np.ndarray    # lead time del 1er pedido, 2do pedido, ... (días)
    inventario_inicial: int        # kits en bodega el día 0 de esta réplica


def mes_de_cada_dia(p: ParametrosCaso, n_dias: int) -> np.ndarray:
    """El día 'dias_calentamiento' es el 1 de enero; los días previos son el
    final del año anterior (septiembre–diciembre)."""
    dia_del_anio = (np.arange(n_dias) - p.dias_calentamiento) % 365
    return MES_DEL_DIA[dia_del_anio]


def generar_demanda(p: ParametrosCaso, rng: np.random.Generator, n_dias: int) -> np.ndarray:
    """Demanda diaria ~ Normal(media * factor_mes, desv * factor_mes),
    redondeada y sin valores negativos (no existe demanda negativa)."""
    factores = np.array([p.estacionalidad[m] for m in range(1, 13)])
    factor_dia = factores[mes_de_cada_dia(p, n_dias) - 1]
    media = p.demanda_media_diaria * factor_dia
    desv = p.demanda_desv_diaria * factor_dia
    demanda = rng.normal(media, desv)
    return np.maximum(0, np.round(demanda)).astype(int)


def _triangular(rng: np.random.Generator, minimo, moda, maximo, n) -> np.ndarray:
    """Triangular(min, moda, max). Si min == max el valor es fijo (sirve para validar)."""
    if minimo == maximo:
        return np.full(n, float(minimo))
    return rng.triangular(minimo, moda, maximo, n)


def generar_tiempos_entrega(p: ParametrosCaso, rng: np.random.Generator, n: int) -> np.ndarray:
    """Lead time = fabricación + barco + aduana + (inspección física si toca).
    Se redondea hacia arriba porque el pedido llega en un día entero."""
    fabricacion = rng.uniform(p.produccion_min, p.produccion_max, n)
    transito = _triangular(rng, p.transito_min, p.transito_moda, p.transito_max, n)
    aduana = _triangular(rng, p.aduana_min, p.aduana_moda, p.aduana_max, n)
    hay_inspeccion = rng.random(n) < p.prob_inspeccion
    extra = np.where(hay_inspeccion, rng.uniform(p.inspeccion_min, p.inspeccion_max, n), 0.0)
    return np.ceil(fabricacion + transito + aduana + extra).astype(int)


def generar_escenario(p: ParametrosCaso, replica: int) -> Escenario:
    """Crea el escenario de la réplica número `replica`.
    La semilla depende de la réplica -> la réplica 7 siempre es la misma,
    sin importar qué política se esté probando (números aleatorios comunes)."""
    rng = np.random.default_rng([p.semilla, replica])
    n = p.dias_totales
    return Escenario(
        demanda=generar_demanda(p, rng, n),
        # Se generan de sobra: como máximo habrá 1 pedido por día.
        tiempos_entrega=generar_tiempos_entrega(p, rng, n),
        inventario_inicial=int(rng.integers(p.inventario_inicial_min, p.inventario_inicial_max + 1)),
    )


def estadisticas_tiempo_entrega(p: ParametrosCaso, muestras: int = 200_000) -> tuple[float, float]:
    """Media y desviación del lead time, estimadas SIMULANDO muchas entregas.
    (La fórmula exacta de una suma de uniforme + triangulares + inspección
    aleatoria es engorrosa; simulando se obtiene igual de bien.)"""
    rng = np.random.default_rng([p.semilla, 999_999])
    lt = generar_tiempos_entrega(p, rng, muestras)
    return float(lt.mean()), float(lt.std(ddof=1))
