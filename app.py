"""
INTERFAZ INTERACTIVA (para la exposición)
=========================================
Permite mover los parámetros en vivo y ver cómo cambian los resultados.
Reutiliza los mismos módulos que main.py (no duplica lógica).

Ejecutar:   streamlit run app.py
"""

import tempfile
from pathlib import Path

import streamlit as st

import graficas
from aleatoriedad import estadisticas_tiempo_entrega
from montecarlo import (comparacion_pareada, correr_montecarlo,
                        sensibilidad_nivel_servicio, tabla_resumen)
from parametros import CAMBIOS_CRISIS, ParametrosCaso
from politicas import calcular_eoq, construir_politicas

st.set_page_config(page_title="Simulación de inventario — Importadora", layout="wide")
CARPETA = Path(tempfile.mkdtemp(prefix="sim_inv_"))


# ------------------------------------------------------------ CONTROLES
st.sidebar.header("Parámetros del caso")
st.sidebar.caption("Mueve los valores y la simulación se vuelve a correr.")

with st.sidebar.expander("Demanda", expanded=True):
    demanda = st.slider("Demanda promedio (kits/día)", 10, 100, 40)
    desv = st.slider("Desviación diaria (kits)", 0, 40, 12)
    con_estacionalidad = st.checkbox("Estacionalidad (pico en diciembre)", value=True)

with st.sidebar.expander("Tiempo de entrega", expanded=True):
    transito = st.slider("Tránsito marítimo: mín / máx (días)", 15, 90, (28, 45))
    transito_moda = st.slider("Tránsito más probable (días)", transito[0], transito[1],
                              min(max(32, transito[0]), transito[1]))
    prob_insp = st.slider("Probabilidad de inspección DIAN", 0.0, 0.6, 0.15, 0.05)
    crisis = st.checkbox("Activar escenario de crisis logística", value=False,
                         help="Las políticas se diseñan con los datos normales y se prueban en crisis.")

with st.sidebar.expander("Costos (COP)", expanded=False):
    costo_pedido = st.number_input("Costo por pedido (contenedor)", 1_000_000, 50_000_000, 12_000_000, 500_000)
    costo_unit = st.number_input("Costo unitario del kit", 10_000, 200_000, 45_000, 1_000)
    precio = st.number_input("Precio de venta del kit", 10_000, 300_000, 75_000, 1_000)
    tasa = st.slider("Tasa anual de mantener inventario", 0.05, 0.60, 0.25, 0.01)
    goodwill = st.number_input("Penalización extra por kit faltante", 0, 100_000, 10_000, 1_000)

with st.sidebar.expander("Simulación", expanded=False):
    nivel = st.slider("Nivel de servicio objetivo (C y D)", 0.50, 0.999, 0.95, 0.005)
    periodo = st.slider("Periodo de revisión de A y D (días)", 15, 180, 90, 5)
    replicas = st.select_slider("Réplicas (años simulados)", [100, 200, 300, 500, 1000], 300)
    semilla = st.number_input("Semilla", 1, 99_999, 2026)

cambios = dict(
    demanda_media_diaria=float(demanda), demanda_desv_diaria=float(desv),
    transito_min=transito[0], transito_moda=transito_moda, transito_max=transito[1],
    prob_inspeccion=prob_insp, costo_pedido=float(costo_pedido), costo_unitario=float(costo_unit),
    precio_venta=float(precio), tasa_mantener_anual=tasa, penalizacion_goodwill=float(goodwill),
    replicas=int(replicas), semilla=int(semilla),
)
if not con_estacionalidad:
    cambios["estacionalidad"] = {m: 1.0 for m in range(1, 13)}


@st.cache_data(show_spinner=False)
def correr(cambios: dict, crisis: bool, nivel: float, periodo: int):
    p = ParametrosCaso().con_cambios(**cambios)
    lt = estadisticas_tiempo_entrega(p)                     # la empresa diseña con datos normales
    politicas = construir_politicas(p, *lt, periodo_revision=periodo, nivel_servicio=nivel)
    p_sim = p.con_cambios(**CAMBIOS_CRISIS) if crisis else p
    resultados, ejemplos = correr_montecarlo(politicas, p_sim)
    return p, p_sim, lt, politicas, resultados, ejemplos


@st.cache_data(show_spinner=False)
def sensibilidad(cambios: dict):
    p = ParametrosCaso().con_cambios(**cambios)
    lt = estadisticas_tiempo_entrega(p)
    rep = min(300, p.replicas)
    normal = sensibilidad_nivel_servicio(p, *lt, replicas=rep)
    en_crisis = sensibilidad_nivel_servicio(p.con_cambios(**CAMBIOS_CRISIS), *lt, replicas=rep)
    return normal, en_crisis


# ------------------------------------------------------------ RESULTADOS
st.title("Simulación de inventario — ImportaMotos del Caribe")
st.caption("Kits de arrastre importados desde China · Monte Carlo + simulación de eventos discretos")

with st.spinner(f"Simulando {replicas:,} años para cada política..."):
    p, p_sim, lt, politicas, resultados, ejemplos = correr(cambios, crisis, nivel, periodo)
resumen = tabla_resumen(resultados)
mejor = resumen["Costo total (M COP)"].idxmin()

if crisis:
    st.warning("Escenario de CRISIS activo: barcos más lentos e inspecciones más frecuentes.")

c1, c2, c3, c4 = st.columns(4)
lt_sim = estadisticas_tiempo_entrega(p_sim)
c1.metric("Tiempo de entrega promedio", f"{lt_sim[0]:.1f} días", f"σ = {lt_sim[1]:.1f} días", delta_color="off")
c2.metric("EOQ (lote económico)", f"{calcular_eoq(p.demanda_anual, p.costo_pedido, p.costo_mantener_anual):,.0f} kits")
c3.metric("Mejor política", mejor.split(" ", 1)[0].strip("."), mejor.split(" ", 1)[1], delta_color="off")
c4.metric("Costo anual de la mejor", f"${resumen.loc[mejor, 'Costo total (M COP)']:,.1f} M",
          f"fill rate {resumen.loc[mejor, 'Fill rate (%)']:.2f} %", delta_color="off")

st.subheader("Políticas comparadas")
for pol in politicas:
    st.markdown(f"- **{pol.nombre}** — {pol.descripcion}")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Costos", "Un año de ejemplo", "Riesgo", "Sensibilidad", "Tabla completa"])
with tab1:
    st.image(str(graficas.grafica_costos(resumen, CARPETA, p.replicas)))
    st.markdown("**Comparación pareada** (mismo futuro para todas las políticas):")
    st.dataframe(comparacion_pareada(resultados, mejor).round(2), width="stretch")
with tab2:
    st.image(str(graficas.grafica_trayectorias(ejemplos, politicas, p_sim, CARPETA)))
with tab3:
    st.image(str(graficas.grafica_distribucion(resultados, CARPETA)))
with tab4:
    st.write("Barre el nivel de servicio de la política EOQ + punto de reorden, en tiempos normales y en crisis.")
    if st.button("Correr análisis de sensibilidad"):
        with st.spinner("Probando 11 niveles de servicio x 2 escenarios..."):
            normal, en_crisis = sensibilidad(cambios)
        color = graficas.color_de([x.nombre for x in politicas])[politicas[2].nombre]
        st.image(str(graficas.grafica_sensibilidad(normal, en_crisis, color, CARPETA)))
with tab5:
    st.dataframe(resumen.round(2).T, width="stretch")
    st.download_button("Descargar resumen (CSV)", resumen.round(3).to_csv().encode("utf-8"),
                       "resumen_politicas.csv", "text/csv")
