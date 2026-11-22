# Simulación de inventario de una importadora

**Caso:** *ImportaMotos del Caribe S.A.S.* (empresa ficticia, Barranquilla) importa desde China **kits de arrastre para moto**. Cada pedido es un contenedor que tarda ~58 días en llegar (fabricación + barco + aduana) y ese tiempo **no es fijo**. Si piden tarde o poco, se quedan sin producto y el cliente se va con la competencia. Si piden mucho, tienen plata quieta en bodega.

**Pregunta del proyecto:** ¿cuándo y cuánto debe pedir la empresa para gastar lo menos posible sin dejar clientes sin atender? ¿Y qué pasa si llega una crisis logística?

**Cómo se llama esto en el mundo empresarial:** *gestión de inventarios / planeación de reabastecimiento*, dentro de la cadena de suministro (*supply chain*). La técnica es **simulación Monte Carlo + simulación de eventos discretos**, que en las empresas se usa como "gemelo digital" para probar decisiones antes de arriesgar plata real.

---

## 1. Cómo correrlo

```bash
pip install -r requirements.txt

python main.py              # corrida completa: validación + 4 experimentos + gráficas (~6 s)
python validacion.py        # solo las pruebas del modelo
streamlit run app.py        # interfaz interactiva para la exposición
```

Los resultados quedan en `resultados/` (6 gráficas PNG en 16:9 listas para las diapositivas + tablas CSV).

---

## 2. Módulos del programa

| # | Archivo | Qué hace | Equivalente en Arena |
|---|---------|----------|----------------------|
| 1 | `parametros.py` | Todos los datos de entrada: demanda, tiempos, costos, réplicas | Variables / Expressions |
| 2 | `aleatoriedad.py` | Genera la demanda diaria y los tiempos de entrega con distribuciones de probabilidad | Módulo **Create** con sus distribuciones (NORM, UNIF, TRIA) |
| 3 | `politicas.py` | Reglas de cuándo y cuánto pedir + fórmulas clásicas (EOQ, stock de seguridad) | Módulo **Decide** |
| 4 | `simulador.py` | Motor día a día: llegada → demanda → revisión → contabilidad | **Process / Assign / Record** + el reloj de simulación |
| 5 | `montecarlo.py` | Repite el año 1.000 veces, intervalos de confianza, experimentos | **Process Analyzer** / réplicas en *Run Setup* |
| 6 | `graficas.py` | Gráficas de resultados | Reportes / Output Analyzer |
| 7 | `validacion.py` | Pruebas de que el modelo está bien hecho | Verificación con animación / reportes |
| — | `main.py` | Orquesta todo en orden | El modelo completo |
| — | `app.py` | Interfaz con controles deslizantes | — |

### Atributos y variables (lenguaje de Arena)
- **Entidades:** los pedidos (contenedores) y los clientes.
- **Atributos de un pedido:** cantidad y día de llegada (lead time sorteado).
- **Variables de estado:** inventario en bodega, inventario en tránsito, posición de inventario.
- **Contadores / acumuladores:** costos, ventas, ventas perdidas, días con faltante, número de pedidos.

---

## 3. Secuencia lógica del programa

```
main.py
 │
 ├─ 1. Lee parámetros (parametros.py)
 ├─ 2. Estima media y desviación del lead time simulando 200.000 entregas (aleatoriedad.py)
 ├─ 3. Calcula las 4 políticas: EOQ, punto de reorden, stock de seguridad, nivel S (politicas.py)
 ├─ 4. Corre la validación (validacion.py)
 ├─ 5. Para cada réplica r = 1..1.000:                                  (montecarlo.py)
 │      ├─ genera UN futuro: demanda de 485 días, lead times, inventario inicial
 │      └─ para cada política, simula ese MISMO futuro:                  (simulador.py)
 │            para cada día:
 │              1. LLEGADA      ¿llega un contenedor hoy? → entra a bodega
 │              2. DEMANDA      vende lo que pueda; lo que falte = venta perdida
 │              3. REVISIÓN     posición = bodega + en camino
 │                              ¿la política dice pedir? → sortea lead time y agenda la llegada
 │              4. CONTABILIDAD (solo después del calentamiento) suma costos y KPIs
 ├─ 6. Promedios + intervalos de confianza + comparación pareada
 ├─ 7. Experimentos: sensibilidad, crisis, robustez al inventario inicial
 └─ 8. Guarda CSV y gráficas
```

---

## 4. Datos del caso (supuestos)

| Parámetro | Valor | Distribución |
|---|---|---|
| Demanda diaria | 40 kits, σ = 12 | Normal, con estacionalidad mensual (diciembre ×1,35, enero ×0,85) |
| Fabricación en China | 10 a 20 días | Uniforme |
| Tránsito marítimo | 28 / 32 / 45 días | Triangular (mín / más probable / máx) |
| Aduana | 3 / 5 / 12 días | Triangular |
| Inspección física DIAN | 15 % de los pedidos, +5 a 10 días | Bernoulli + Uniforme |
| **Lead time total** | **58,3 días promedio, σ = 5,7** | Suma de las anteriores |
| Costo de pedir | $12.000.000 por contenedor | Flete + agencia de aduanas + trámites |
| Costo de mantener | 25 % anual del costo del kit ($45.000) = $11.250/kit/año | Capital, bodega, seguro, obsolescencia |
| Costo de faltante | $40.000 por kit | Margen perdido ($30.000) + penalización por cliente insatisfecho ($10.000) |

Los datos son ficticios pero realistas. En una empresa real se sacan del histórico de ventas y de las fechas de los pedidos.

---

## 5. Las 4 políticas comparadas

| Política | Regla | Parámetros |
|---|---|---|
| **A. Pedido fijo trimestral** | Cada 90 días pedir siempre lo mismo, sin mirar la bodega ("a ojo") | Q = 3.600 kits |
| **B. EOQ + punto de reorden sin SS** | Cuando la posición baje a R, pedir Q | Q = 5.581, R = 2.331 |
| **C. EOQ + punto de reorden + SS 95 %** | Igual, pero con un colchón de seguridad | Q = 5.581, R = 2.736 (SS = 405) |
| **D. Revisión trimestral (T, S)** | Cada 90 días pedir lo que falte para llegar a S | S = 6.377 |

**Fórmulas usadas:**
- EOQ: `Q* = √(2·D·S / H)` = √(2 · 14.600 · 12.000.000 / 11.250) ≈ **5.581 kits**
- Punto de reorden: `R = d · L + SS` (demanda durante el tiempo de entrega + colchón)
- Stock de seguridad: `SS = z · √(L·σd² + d²·σL²)` → junta la incertidumbre de la demanda **y** la del barco. Con z = 1,645 (95 %) da 405 kits.

---

## 6. Resultados (1.000 años simulados por política, semilla 2026)

### Experimento 1: condiciones normales

| | A | B | **C** | D |
|---|---|---|---|---|
| Costo anual (M COP) | 99,6 | 74,7 | **69,4** | 74,6 |
| Fill rate (% de la demanda atendida) | 99,94 % | 97,88 % | **99,69 %** | 99,76 % |
| Pedidos por año | 4,0 | 2,5 | 2,6 | 4,0 |
| Probabilidad de perder > 500 kits en el año | 0,5 % | 23,9 % | **0,4 %** | 0,2 % |

**Comparación pareada contra C** (como todas vieron el mismo futuro, se resta réplica a réplica):
- A cuesta **$30,2 M más** al año (IC 95 %: 28,8 a 31,6) → significativa.
- B cuesta **$5,4 M más** (IC: 4,7 a 6,0) → significativa. Ojo: C le gana a B solo en el 60 % de los años, pero cuando B pierde, pierde feo. Por eso el promedio favorece a C.
- D cuesta **$5,2 M más** (IC: 4,7 a 5,6) → significativa.

### Experimento 2: ¿cuánto stock de seguridad conviene?
- En tiempos normales, el costo mínimo está en un **nivel de servicio del 95 % (SS ≈ 405 kits)**. La curva es plana entre 90 % y 97 %.
- Si se espera una crisis, el costo sigue bajando hasta el 99,99 % (SS ≈ 916 kits) → con más riesgo conviene un colchón más grande.

### Experimento 3: prueba de estrés (crisis logística)
Barcos de 32 a 70 días y el doble de inspecciones (lead time sube a 71,7 días, σ = 9,6). Las políticas se diseñaron con los datos normales: la empresa no sabía que venía la crisis.

| | A | B | **C** | D |
|---|---|---|---|---|
| Costo en crisis (M COP) | 96,7 | 112,8 | **86,2** | 93,3 |
| Cambio vs normal | −2,9 | **+38,0** | +16,8 | +18,7 |
| Fill rate | 99,52 % | 90,32 % | 95,70 % | 95,80 % |

Si la empresa **recalcula** C con los nuevos tiempos (R = 3.519, SS = 651), el costo en crisis baja a **$72,2 M** con fill rate de 99,73 %.

### Experimento 4: ¿los resultados dependen del inventario inicial?
Se probó arrancando con 1.500–4.000, 2.500–8.000 y 6.000–9.000 kits. B, C y D varían $4 M o menos; **A varía $43 M**. Como A no mira la bodega, nunca corrige: si arranca con mucho, vive con mucho; si arranca con poco, vive con faltantes.

---

## 7. Conclusiones y recomendación a la empresa

1. **Usar la política C** (EOQ + punto de reorden + stock de seguridad al 95 %): es la más barata (**$69,4 M/año**) y atiende el 99,7 % de la demanda. Frente a pedir "a ojo" cada trimestre (A) ahorra **$30 M al año (30 %)**.
2. **El stock de seguridad no es un gasto, es un seguro barato:** pasar de B a C *baja* el costo $5,4 M y la probabilidad de un año malo cae de 24 % a 0,4 %.
3. **Pedir muy seguido sale caro por el flete:** D atiende bien, pero paga 4 contenedores al año en lugar de 2,6.
4. **Lo más importante en una crisis es actualizar los datos:** la misma fórmula, recalculada con los tiempos reales, recupera casi todo el control ($72 M en vez de $86 M).
5. **Mirar la posición de inventario (bodega + en camino), no solo la bodega:** es lo que permite que B, C y D se autocorrijan.





