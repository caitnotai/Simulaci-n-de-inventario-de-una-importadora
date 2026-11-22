"""
PROGRAMA PRINCIPAL — Simulación de inventario de una importadora
================================================================
Orquesta todos los módulos (como el "modelo" completo en Arena):

  parametros.py   -> MÓDULO 1: datos del caso
  aleatoriedad.py -> MÓDULO 2: demanda y tiempos de entrega aleatorios
  politicas.py    -> MÓDULO 3: reglas de cuándo y cuánto pedir (EOQ, ROP, SS)
  simulador.py    -> MÓDULO 4: motor de simulación día a día
  montecarlo.py   -> MÓDULO 5: réplicas, intervalos de confianza, experimentos
  graficas.py     -> MÓDULO 6: gráficas para la presentación
  validacion.py   -> MÓDULO 7: pruebas de que el modelo está bien hecho

Uso:
    python main.py                    # corrida completa (1.000 réplicas)
    python main.py --replicas 300     # más rápida
    python main.py --sin-validacion   # se salta las pruebas del modelo
"""

import argparse
import time
from pathlib import Path

import pandas as pd

import graficas
from aleatoriedad import estadisticas_tiempo_entrega
from montecarlo import (comparacion_pareada, correr_montecarlo,
                        robustez_inventario_inicial, sensibilidad_nivel_servicio,
                        tabla_resumen)
from parametros import CAMBIOS_CRISIS, ParametrosCaso
from politicas import calcular_eoq, construir_politica_qr, construir_politicas
from validacion import correr_validacion

CARPETA = Path(__file__).parent / "resultados"
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)


def titulo(texto: str):
    print("\n" + "=" * 100)
    print(texto)
    print("=" * 100)


def main():
    parser = argparse.ArgumentParser(description="Simulación de inventario de una importadora")
    parser.add_argument("--replicas", type=int, default=None, help="número de réplicas Monte Carlo")
    parser.add_argument("--sin-validacion", action="store_true", help="no correr las pruebas del modelo")
    args = parser.parse_args()

    inicio = time.time()
    p = ParametrosCaso()
    if args.replicas:
        p = p.con_cambios(replicas=args.replicas)
    CARPETA.mkdir(exist_ok=True)

    # ------------------------------------------------------------ 0. DATOS
    titulo("CASO: ImportaMotos del Caribe S.A.S. — kits de arrastre importados desde China")
    lt_media, lt_desv = estadisticas_tiempo_entrega(p)
    print(f"Demanda promedio: {p.demanda_media_diaria:.0f} kits/día (σ = {p.demanda_desv_diaria:.0f}) "
          f"-> {p.demanda_anual:,.0f} kits/año, con pico en diciembre (x{p.estacionalidad[12]})")
    print(f"Tiempo de entrega: {lt_media:.1f} días en promedio (σ = {lt_desv:.1f} días)")
    print(f"Costo de pedir: ${p.costo_pedido:,.0f} por contenedor | Costo de mantener: "
          f"${p.costo_mantener_anual:,.0f} por kit al año | Costo de faltante: ${p.costo_faltante:,.0f} por kit")
    print(f"EOQ (cantidad económica de pedido): "
          f"{calcular_eoq(p.demanda_anual, p.costo_pedido, p.costo_mantener_anual):,.0f} kits")

    politicas = construir_politicas(p, lt_media, lt_desv)
    print("\nPolíticas a comparar:")
    for pol in politicas:
        print(f"  {pol.nombre:<36} {pol.descripcion}")

    # ------------------------------------------------------- 1. VALIDACIÓN
    if not args.sin_validacion:
        correr_validacion(p)

    # ------------------------------------- 2. EXPERIMENTO 1: COMPARACIÓN BASE
    titulo(f"EXPERIMENTO 1 — Comparación de políticas ({p.replicas:,} años simulados por política)")
    resultados, ejemplos = correr_montecarlo(politicas, p)
    resumen = tabla_resumen(resultados)
    print(resumen.round(2).T.to_string())
    mejor = resumen["Costo total (M COP)"].idxmin()
    print(f"\nComparación pareada contra la mejor ({mejor}):")
    pareada = comparacion_pareada(resultados, mejor)
    print(pareada.round(2).to_string())

    # ------------------------------------ 3. EXPERIMENTO 2: SENSIBILIDAD
    titulo("EXPERIMENTO 2 — Sensibilidad al nivel de servicio (stock de seguridad)")
    rep_sens = min(500, p.replicas)
    sens_normal = sensibilidad_nivel_servicio(p, lt_media, lt_desv, replicas=rep_sens)
    p_crisis = p.con_cambios(**CAMBIOS_CRISIS)
    # La política se diseña con los datos NORMALES; se prueba en crisis
    sens_crisis = sensibilidad_nivel_servicio(p_crisis, lt_media, lt_desv, replicas=rep_sens)
    for nombre, df in [("Normal", sens_normal), ("Crisis", sens_crisis)]:
        i = df["costo_total"].idxmin()
        print(f"  {nombre}: óptimo = {df.loc[i, 'nivel_servicio']:.2%} de nivel de servicio "
              f"(SS = {df.loc[i, 'stock_seguridad']:,} kits) -> ${df.loc[i, 'costo_total'] / 1e6:,.1f} M/año")
    vista = sens_normal[["nivel_servicio", "stock_seguridad", "costo_total", "fill_rate"]].copy()
    vista["costo_crisis"] = sens_crisis["costo_total"]
    vista[["costo_total", "costo_crisis"]] /= 1e6
    print(vista.round(3).to_string(index=False))

    # ------------------------------------------ 4. EXPERIMENTO 3: CRISIS
    titulo("EXPERIMENTO 3 — Prueba de estrés: crisis logística")
    print("Cambios:", CAMBIOS_CRISIS)
    lt_c = estadisticas_tiempo_entrega(p_crisis)
    print(f"Tiempo de entrega en crisis: {lt_c[0]:.1f} días (σ = {lt_c[1]:.1f}) vs {lt_media:.1f} normal")
    res_crisis, _ = correr_montecarlo(politicas, p_crisis, guardar_ejemplo=False)
    resumen_crisis = tabla_resumen(res_crisis)
    print(resumen_crisis.round(2).T.to_string())
    # ¿Y si la empresa se da cuenta y recalcula la política C con los tiempos de crisis?
    c_ajustada = construir_politica_qr(p_crisis, lt_c[0], lt_c[1], 0.95, "C ajustada a la crisis")
    res_aj, _ = correr_montecarlo([c_ajustada], p_crisis, guardar_ejemplo=False)
    aj = tabla_resumen(res_aj).iloc[0]
    print(f"\nSi la empresa RECALCULA la política C con los tiempos de crisis "
          f"(nuevo punto de reorden {c_ajustada.R:,}, SS = {c_ajustada.stock_seguridad:,}):")
    print(f"  costo ${aj['Costo total (M COP)']:,.1f} M/año · fill rate {aj['Fill rate (%)']:.2f} % "
          f"· ventas perdidas {aj['Ventas perdidas (kits)']:,.0f} kits")

    # ------------------------- 5. EXPERIMENTO 4: ROBUSTEZ AL INVENTARIO INICIAL
    titulo("EXPERIMENTO 4 — ¿Los resultados dependen de con cuánto inventario se arranca?")
    robustez = robustez_inventario_inicial(politicas, p, replicas=min(300, p.replicas))
    print(robustez.pivot(index="Política", columns="Inventario inicial",
                         values="Costo total (M COP)").round(1).to_string())
    rango_costo = robustez.groupby("Política")["Costo total (M COP)"].agg(lambda s: s.max() - s.min())
    print("\nVariación del costo según el arranque (M COP):",
          ", ".join(f"{n[:2].strip()} {v:.1f}" for n, v in rango_costo.items()))

    # ---------------------------------------------- 6. GUARDAR RESULTADOS
    resumen.round(3).to_csv(CARPETA / "resumen_politicas.csv", encoding="utf-8-sig")
    resumen_crisis.round(3).to_csv(CARPETA / "resumen_crisis.csv", encoding="utf-8-sig")
    pareada.round(3).to_csv(CARPETA / "comparacion_pareada.csv", encoding="utf-8-sig")
    pd.concat({"normal": sens_normal, "crisis": sens_crisis}).round(3).to_csv(CARPETA / "sensibilidad.csv", encoding="utf-8-sig")
    robustez.round(3).to_csv(CARPETA / "robustez_inventario_inicial.csv", index=False, encoding="utf-8-sig")
    pd.concat(resultados, names=["politica", "replica"]).round(2).to_csv(CARPETA / "detalle_replicas.csv", encoding="utf-8-sig")

    rutas = [
        graficas.grafica_entradas(p, CARPETA),
        graficas.grafica_trayectorias(ejemplos, politicas, p, CARPETA),
        graficas.grafica_costos(resumen, CARPETA, p.replicas),
        graficas.grafica_distribucion(resultados, CARPETA),
        graficas.grafica_sensibilidad(sens_normal, sens_crisis,
                                      graficas.color_de([x.nombre for x in politicas])[politicas[2].nombre],
                                      CARPETA),
        graficas.grafica_crisis(resumen, resumen_crisis, CARPETA),
    ]

    # ------------------------------------------------------- 7. CONCLUSIONES
    titulo("CONCLUSIONES (calculadas a partir de los resultados)")
    costo = resumen["Costo total (M COP)"]
    costo_c = resumen_crisis["Costo total (M COP)"]
    peor = costo.idxmax()
    ahorro = costo[peor] - costo[mejor]
    print(f"1. La mejor política en condiciones normales es {mejor}: ${costo[mejor]:,.1f} M/año, "
          f"fill rate {resumen.loc[mejor, 'Fill rate (%)']:.2f} %.")
    print(f"2. Frente a {peor} ahorra ${ahorro:,.1f} M al año ({ahorro / costo[peor]:.0%}).")
    sin_ss, con_ss = politicas[1].nombre, politicas[2].nombre
    dif_ss = costo[con_ss] - costo[sin_ss]
    print(f"3. Agregar stock de seguridad ({sin_ss[:2].strip()} -> {con_ss[:2].strip()}) hace que el costo "
          f"{'BAJE' if dif_ss < 0 else 'suba'} ${abs(dif_ss):,.1f} M y la probabilidad de perder más de 500 kits en el año "
          f"pasa de {resumen.loc[sin_ss, 'Prob. de perder >500 kits (%)']:.1f} % a "
          f"{resumen.loc[con_ss, 'Prob. de perder >500 kits (%)']:.1f} %.")
    mejor_crisis = costo_c.idxmin()
    print(f"4. En crisis la mejor sigue siendo {mejor_crisis} (${costo_c[mejor_crisis]:,.1f} M). "
          "Cambio de costo por la crisis: "
          + ", ".join(f"{n[:2].strip()} {v:+.1f} M" for n, v in (costo_c - costo).sort_values().items()))
    i_n, i_c = sens_normal["costo_total"].idxmin(), sens_crisis["costo_total"].idxmin()
    print(f"5. Nivel de servicio óptimo: {sens_normal.loc[i_n, 'nivel_servicio']:.1%} en tiempos normales, "
          f"{sens_crisis.loc[i_c, 'nivel_servicio']:.2%} si se espera una crisis -> el stock de seguridad "
          "es un seguro: se ajusta según el riesgo que se espere.")
    print(f"   Mejor aún: si se RECALCULA la política con los datos de crisis, el costo en crisis queda en "
          f"${aj['Costo total (M COP)']:,.1f} M (vs ${costo_c[con_ss]:,.1f} M sin recalcular).")
    print(f"6. La política {rango_costo.idxmax()[:2].strip()} es la que más depende del inventario con que se "
          f"arranca (varía ${rango_costo.max():,.1f} M): no mira la bodega, así que nunca se autocorrige.")
    print(f"\nArchivos guardados en: {CARPETA}")
    for r in rutas:
        print("   -", r.name)
    print(f"\nTiempo total: {time.time() - inicio:.1f} s")


if __name__ == "__main__":
    main()
