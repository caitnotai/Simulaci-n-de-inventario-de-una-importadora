"""
MÓDULO 3 — POLÍTICAS DE INVENTARIO (las "reglas de decisión")
=============================================================
Una POLÍTICA DE INVENTARIO responde dos preguntas: ¿CUÁNDO pedir? y ¿CUÁNTO pedir?
Es el equivalente al módulo DECIDE de Arena: según el estado del sistema,
se toma un camino u otro.

Todas las políticas miran la POSICIÓN DE INVENTARIO, no solo lo que hay en bodega:
    posición de inventario = inventario en bodega + lo que ya viene en camino
Si solo miraran la bodega, volverían a pedir cada día mientras el barco viene
en camino y se llenarían de mercancía.

Las 4 políticas que se comparan:
  A. Pedido fijo trimestral ("como se hace a ojo"): cada 90 días se pide lo mismo.
  B. EOQ + punto de reorden SIN stock de seguridad.
  C. EOQ + punto de reorden CON stock de seguridad (nivel de servicio 95 %).
  D. Revisión periódica trimestral: cada 90 días se pide lo necesario para
     subir hasta un nivel objetivo S (la cantidad cambia según cómo esté la bodega).
"""

import math
from dataclasses import dataclass
from statistics import NormalDist

from parametros import ParametrosCaso


# ===================================================================
#  FÓRMULAS CLÁSICAS DE INVENTARIOS (las de los libros de operaciones)
# ===================================================================

def calcular_eoq(demanda_anual: float, costo_pedido: float, costo_mantener_anual: float) -> float:
    """Cantidad Económica de Pedido (EOQ, modelo de Wilson, 1913):
        Q* = sqrt(2 · D · S / H)
    Es la cantidad que equilibra el costo de pedir muchas veces (S) contra el
    costo de guardar mucha mercancía (H)."""
    return math.sqrt(2 * demanda_anual * costo_pedido / costo_mantener_anual)


def z_de_nivel_servicio(nivel_servicio: float) -> float:
    """Valor z de la normal estándar. Ej.: 95 % -> 1.645."""
    return NormalDist().inv_cdf(nivel_servicio)


def desv_demanda_en_periodo(dias: float, d: float, sd: float, sd_lt: float) -> float:
    """Desviación de la demanda acumulada durante un periodo de duración
    aleatoria (dias = duración media, sd_lt = desviación de esa duración):
        σ = sqrt(dias · σd² + d² · σLT²)
    Junta las dos fuentes de incertidumbre: cuánto se vende y cuánto tarda el barco."""
    return math.sqrt(dias * sd ** 2 + d ** 2 * sd_lt ** 2)


# ===================================================================
#  POLÍTICAS (cada una sabe decidir cuánto pedir hoy)
# ===================================================================

@dataclass
class PoliticaPuntoReorden:
    """Revisión CONTINUA (Q, R): todos los días se revisa; si la posición de
    inventario baja hasta el punto de reorden R, se pide una cantidad fija Q."""
    nombre: str
    Q: int                 # cantidad a pedir (lote)
    R: int                 # punto de reorden
    stock_seguridad: int = 0

    @property
    def descripcion(self) -> str:
        return f"Pedir {self.Q:,} kits cuando la posición baje a {self.R:,} (SS = {self.stock_seguridad:,})"

    def decidir(self, dia: int, posicion: int) -> int:
        return self.Q if posicion <= self.R else 0


@dataclass
class PoliticaRevisionPeriodica:
    """Revisión PERIÓDICA (T, S): cada T días se mira la bodega y se pide lo
    necesario para que la posición de inventario suba hasta el nivel objetivo S."""
    nombre: str
    T: int                 # cada cuántos días se revisa
    S: int                 # nivel objetivo (order-up-to level)
    R: int | None = None   # no aplica, se deja para las gráficas

    @property
    def descripcion(self) -> str:
        return f"Cada {self.T} días pedir lo que falte para llegar a {self.S:,} kits"

    def decidir(self, dia: int, posicion: int) -> int:
        if dia % self.T == 0:
            return max(0, self.S - posicion)
        return 0


@dataclass
class PoliticaPedidoFijo:
    """Pedido fijo por calendario: cada T días se pide SIEMPRE la misma cantidad Q,
    sin mirar cuánto hay en bodega. Es lo que hacen muchas empresas 'a ojo'."""
    nombre: str
    T: int
    Q: int
    R: int | None = None

    @property
    def descripcion(self) -> str:
        return f"Cada {self.T} días pedir {self.Q:,} kits, sin mirar la bodega"

    def decidir(self, dia: int, posicion: int) -> int:
        return self.Q if dia % self.T == 0 else 0


# ===================================================================
#  CONSTRUCCIÓN DE LAS 4 POLÍTICAS A PARTIR DE LOS PARÁMETROS
# ===================================================================

def construir_politica_qr(p: ParametrosCaso, lt_media: float, lt_desv: float,
                          nivel_servicio: float | None, nombre: str) -> PoliticaPuntoReorden:
    """EOQ + punto de reorden. Si nivel_servicio es None, no hay stock de seguridad."""
    d, sd = p.demanda_media_diaria, p.demanda_desv_diaria
    Q = calcular_eoq(p.demanda_anual, p.costo_pedido, p.costo_mantener_anual)
    demanda_en_lead_time = d * lt_media
    if nivel_servicio is None:
        ss = 0.0
    else:
        ss = z_de_nivel_servicio(nivel_servicio) * desv_demanda_en_periodo(lt_media, d, sd, lt_desv)
    return PoliticaPuntoReorden(nombre=nombre, Q=round(Q), R=round(demanda_en_lead_time + ss),
                                stock_seguridad=round(ss))


def construir_politicas(p: ParametrosCaso, lt_media: float, lt_desv: float,
                        periodo_revision: int = 90, nivel_servicio: float = 0.95) -> list:
    d, sd = p.demanda_media_diaria, p.demanda_desv_diaria

    # A. Pedido fijo trimestral: pide justo la demanda promedio de 90 días
    politica_a = PoliticaPedidoFijo(nombre="A. Pedido fijo trimestral",
                                    T=periodo_revision, Q=round(d * periodo_revision))

    # B y C. EOQ + punto de reorden
    politica_b = construir_politica_qr(p, lt_media, lt_desv, None, "B. EOQ + ROP sin SS")
    politica_c = construir_politica_qr(p, lt_media, lt_desv, nivel_servicio,
                                       f"C. EOQ + ROP + SS {nivel_servicio:.0%}")

    # D. Revisión periódica: debe cubrir el periodo de revisión + el lead time
    horizonte = periodo_revision + lt_media
    S = d * horizonte + z_de_nivel_servicio(nivel_servicio) * desv_demanda_en_periodo(horizonte, d, sd, lt_desv)
    politica_d = PoliticaRevisionPeriodica(nombre=f"D. Revisión trimestral (T,S) {nivel_servicio:.0%}",
                                           T=periodo_revision, S=round(S))

    return [politica_a, politica_b, politica_c, politica_d]
