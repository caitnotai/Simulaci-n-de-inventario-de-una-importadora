"""
MÓDULO 4 — MOTOR DE SIMULACIÓN (el corazón del programa)
========================================================
Simula la bodega DÍA A DÍA. Es una SIMULACIÓN DE EVENTOS DISCRETOS con avance
de tiempo fijo (time-step): el reloj avanza de a 1 día y en cada día ocurren,
en este orden, 4 eventos:

    1. LLEGADA      -> si hoy llega un contenedor, entra a bodega.
    2. DEMANDA      -> llegan los clientes; se vende lo que haya.
                       Lo que no alcance es VENTA PERDIDA (el cliente se va).
    3. REVISIÓN     -> la política mira la posición de inventario y decide
                       si pide y cuánto. Si pide, se sortea en cuántos días llega.
    4. CONTABILIDAD -> se suman costos e indicadores del día.

Equivalencia con Arena:
    ENTIDADES  = los pedidos (contenedores) y los clientes.
    ATRIBUTOS  = cantidad del pedido, día de llegada.
    VARIABLES  = inventario en bodega, inventario en tránsito.
    RECURSO    = la bodega (el inventario disponible).

PERIODO DE CALENTAMIENTO (warm-up): los primeros días se simulan pero NO se
cuentan, porque el arranque (inventario inicial inventado) no representa la
operación normal. Así los resultados no quedan sesgados por cómo arrancamos.
"""

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from aleatoriedad import Escenario
from parametros import ParametrosCaso


@dataclass
class ResultadoCorrida:
    """Indicadores (KPI) de UNA réplica de UNA política."""
    costo_mantener: float
    costo_pedido: float
    costo_faltante: float
    demanda_total: int
    ventas: int
    ventas_perdidas: int
    dias_con_faltante: int
    inventario_promedio: float
    num_pedidos: int
    # Solo se llenan si se pide guardar la historia (para graficar)
    historia: dict = field(default_factory=dict)

    @property
    def costo_total(self) -> float:
        return self.costo_mantener + self.costo_pedido + self.costo_faltante

    @property
    def fill_rate(self) -> float:
        """Nivel de servicio tipo 2 (fill rate): % de la demanda que sí se atendió."""
        return self.ventas / self.demanda_total if self.demanda_total else 1.0

    def como_dict(self, dias_medidos: int) -> dict:
        return {
            "costo_total": self.costo_total,
            "costo_mantener": self.costo_mantener,
            "costo_pedido": self.costo_pedido,
            "costo_faltante": self.costo_faltante,
            "fill_rate": self.fill_rate,
            "pct_dias_con_faltante": self.dias_con_faltante / dias_medidos,
            "ventas_perdidas": self.ventas_perdidas,
            "inventario_promedio": self.inventario_promedio,
            "num_pedidos": self.num_pedidos,
        }


def simular(politica, escenario: Escenario, p: ParametrosCaso,
            guardar_historia: bool = False) -> ResultadoCorrida:
    """Corre UNA réplica de UNA política sobre UN escenario aleatorio."""
    n_dias = len(escenario.demanda)
    inicio_medicion = p.dias_calentamiento

    # ---- Variables de estado del sistema
    inventario = escenario.inventario_inicial   # kits en bodega
    en_transito = 0                        # kits pedidos que aún no llegan
    llegadas = defaultdict(int)            # día -> kits que llegan ese día (calendario de eventos)
    indice_pedido = 0                      # para tomar el siguiente lead time del escenario

    # ---- Acumuladores de indicadores (solo en el periodo medido)
    costo_mantener = costo_pedido = costo_faltante = 0.0
    demanda_total = ventas = perdidas = dias_faltante = num_pedidos = 0
    suma_inventario = 0

    # ---- Historia para graficar
    if guardar_historia:
        h_inventario = np.zeros(n_dias, dtype=int)
        h_posicion = np.zeros(n_dias, dtype=int)
        h_ventas = np.zeros(n_dias, dtype=int)
        h_pedidos, h_llegadas = [], []

    for dia in range(n_dias):
        midiendo = dia >= inicio_medicion

        # ---------------- EVENTO 1: LLEGADA DE PEDIDOS
        if dia in llegadas:
            cantidad = llegadas.pop(dia)
            inventario += cantidad
            en_transito -= cantidad
            if guardar_historia:
                h_llegadas.append((dia, cantidad))

        # ---------------- EVENTO 2: DEMANDA DE LOS CLIENTES
        demanda = int(escenario.demanda[dia])
        vendido = min(demanda, inventario)
        perdido = demanda - vendido
        inventario -= vendido

        # ---------------- EVENTO 3: REVISIÓN Y DECISIÓN DE PEDIDO
        posicion = inventario + en_transito
        cantidad_pedida = politica.decidir(dia, posicion)
        if cantidad_pedida > 0:
            lead_time = int(escenario.tiempos_entrega[indice_pedido])
            indice_pedido += 1
            llegadas[dia + lead_time] += cantidad_pedida
            en_transito += cantidad_pedida
            if guardar_historia:
                h_pedidos.append((dia, cantidad_pedida, lead_time))

        # ---------------- EVENTO 4: CONTABILIDAD DEL DÍA
        if midiendo:
            costo_mantener += inventario * p.costo_mantener_diario
            costo_faltante += perdido * p.costo_faltante
            if cantidad_pedida > 0:
                costo_pedido += p.costo_pedido
                num_pedidos += 1
            demanda_total += demanda
            ventas += vendido
            perdidas += perdido
            dias_faltante += perdido > 0
            suma_inventario += inventario

        if guardar_historia:
            h_inventario[dia] = inventario
            h_posicion[dia] = inventario + en_transito
            h_ventas[dia] = vendido

    dias_medidos = n_dias - inicio_medicion
    resultado = ResultadoCorrida(
        costo_mantener=costo_mantener,
        costo_pedido=costo_pedido,
        costo_faltante=costo_faltante,
        demanda_total=demanda_total,
        ventas=ventas,
        ventas_perdidas=perdidas,
        dias_con_faltante=dias_faltante,
        inventario_promedio=suma_inventario / dias_medidos,
        num_pedidos=num_pedidos,
    )
    if guardar_historia:
        resultado.historia = {
            "inventario": h_inventario,
            "posicion": h_posicion,
            "demanda": escenario.demanda.copy(),
            "ventas": h_ventas,
            "pedidos": h_pedidos,
            "llegadas": h_llegadas,
            "inventario_inicial": escenario.inventario_inicial,
            "inventario_final": inventario,
            "en_transito_final": en_transito,
        }
    return resultado
