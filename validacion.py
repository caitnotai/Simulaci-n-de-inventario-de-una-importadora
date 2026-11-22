"""
MÓDULO 7 — VERIFICACIÓN Y VALIDACIÓN DEL MODELO
===============================================
Pregunta clásica en una sustentación: "¿cómo saben que su simulación está bien?"

  * VERIFICACIÓN = ¿el programa hace lo que dijimos que hace? (no hay bugs)
  * VALIDACIÓN   = ¿el modelo se parece a la realidad / a la teoría?

Pruebas:
  1. Balance de unidades: no se crean ni se pierden kits "mágicamente".
  2. La demanda simulada tiene la media que se le pidió.
  3. El lead time simulado tiene la media teórica de la suma de etapas.
  4. Caso sin incertidumbre: la simulación debe dar lo mismo que la fórmula
     clásica del EOQ. Si coincide, el motor está bien construido.

Se corre con:  python validacion.py
"""

import numpy as np

from aleatoriedad import (DIAS_POR_MES, estadisticas_tiempo_entrega,
                          generar_escenario)
from parametros import ParametrosCaso
from politicas import calcular_eoq, construir_politica_qr, construir_politicas
from simulador import simular


def _linea(nombre, esperado, obtenido, tolerancia_rel):
    error = abs(obtenido - esperado) / abs(esperado) if esperado else abs(obtenido)
    ok = error <= tolerancia_rel
    print(f"  {'OK ' if ok else 'FALLA'} | {nombre:<48} esperado={esperado:>14,.2f}  "
          f"obtenido={obtenido:>14,.2f}  error={error:6.2%}")
    return ok


def prueba_balance_unidades(p: ParametrosCaso) -> bool:
    print("\n1) Balance de unidades (inicial + recibido = vendido + final)")
    lt = estadisticas_tiempo_entrega(p)
    todo_ok = True
    for pol in construir_politicas(p, *lt):
        res = simular(pol, generar_escenario(p, 0), p, guardar_historia=True)
        h = res.historia
        recibido = sum(c for _, c in h["llegadas"])
        pedido = sum(c for _, c, _ in h["pedidos"])
        entra = h["inventario_inicial"] + recibido
        sale = int(h["ventas"].sum()) + h["inventario_final"]
        ok = (entra == sale) and (pedido == recibido + h["en_transito_final"])
        todo_ok &= ok
        print(f"  {'OK ' if ok else 'FALLA'} | {pol.nombre:<34} entra={entra:,}  sale={sale:,}  "
              f"pedido={pedido:,} = recibido {recibido:,} + en camino {h['en_transito_final']:,}")
    return todo_ok


def prueba_demanda(p: ParametrosCaso, replicas: int = 300) -> bool:
    print("\n2) Media de la demanda diaria (año medido, con estacionalidad)")
    factores = np.repeat([p.estacionalidad[m] for m in range(1, 13)], DIAS_POR_MES)
    esperado = p.demanda_media_diaria * factores.mean()
    obtenido = np.mean([generar_escenario(p, r).demanda[p.dias_calentamiento:].mean()
                        for r in range(replicas)])
    return _linea("Demanda media diaria (kits)", esperado, obtenido, 0.01)


def prueba_lead_time(p: ParametrosCaso) -> bool:
    print("\n3) Media del tiempo de entrega (suma de etapas)")
    teorico = ((p.produccion_min + p.produccion_max) / 2
               + (p.transito_min + p.transito_moda + p.transito_max) / 3
               + (p.aduana_min + p.aduana_moda + p.aduana_max) / 3
               + p.prob_inspeccion * (p.inspeccion_min + p.inspeccion_max) / 2)
    media, _ = estadisticas_tiempo_entrega(p)
    # El redondeo hacia arriba a días enteros suma ~0.5 días en promedio
    return _linea("Lead time medio (días, incl. +0.5 por redondeo)", teorico + 0.5, media, 0.01)


def prueba_eoq_deterministico() -> bool:
    print("\n4) Caso determinístico vs fórmula clásica del EOQ (30 años simulados)")
    L = 58
    p = ParametrosCaso().con_cambios(
        demanda_desv_diaria=0.0,
        estacionalidad={m: 1.0 for m in range(1, 13)},
        produccion_min=L, produccion_max=L,
        transito_min=0, transito_moda=0, transito_max=0,
        aduana_min=0, aduana_moda=0, aduana_max=0,
        prob_inspeccion=0.0,
        dias_calentamiento=365, dias_simulacion=365 * 30,
    )
    pol = construir_politica_qr(p, lt_media=L, lt_desv=0.0, nivel_servicio=None, nombre="EOQ")
    p = p.con_cambios(inventario_inicial_min=pol.R + pol.Q, inventario_inicial_max=pol.R + pol.Q)
    res = simular(pol, generar_escenario(p, 0), p)
    anios = p.dias_simulacion / 365

    Q = calcular_eoq(p.demanda_anual, p.costo_pedido, p.costo_mantener_anual)
    teorico_pedir = p.demanda_anual / Q * p.costo_pedido
    teorico_mantener = Q / 2 * p.costo_mantener_anual
    ok1 = _linea("Costo anual de pedir (COP)", teorico_pedir, res.costo_pedido / anios, 0.03)
    ok2 = _linea("Costo anual de mantener (COP)", teorico_mantener, res.costo_mantener / anios, 0.03)
    ok3 = _linea("Ventas perdidas (debe ser 0)", 0, res.ventas_perdidas, 0.0)
    return ok1 and ok2 and ok3


def correr_validacion(p: ParametrosCaso | None = None) -> bool:
    p = p or ParametrosCaso()
    print("=" * 100)
    print("VERIFICACIÓN Y VALIDACIÓN DEL MODELO")
    print("=" * 100)
    resultados = [
        prueba_balance_unidades(p),
        prueba_demanda(p),
        prueba_lead_time(p),
        prueba_eoq_deterministico(),
    ]
    print("\nResultado:", "TODAS LAS PRUEBAS PASARON ✔" if all(resultados) else "HAY PRUEBAS QUE FALLARON ✘")
    return all(resultados)


if __name__ == "__main__":
    correr_validacion()
