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

---

## 8. Supuestos y limitaciones (decirlos antes de que los pregunten)

- Datos ficticios, aunque con órdenes de magnitud realistas.
- **Ventas perdidas:** si no hay producto, el cliente se va (no hay pedidos pendientes / *backorders*).
- La demanda de un día no depende de la del día anterior (independencia).
- No se modela la capacidad del contenedor ni descuentos por volumen.
- No se cobra costo de capital por la mercancía que viene en el barco (inventario en tránsito). Agregarlo subiría todos los costos casi por igual, porque el inventario en tránsito ≈ demanda × lead time (Ley de Little) no depende de la política.
- Un solo producto. Una importadora real maneja cientos (se podría extender con una clasificación ABC).

---

## 9. Conceptos que deben saber explicar

| Concepto | En palabras simples |
|---|---|
| **Lead time** | Días desde que se hace el pedido hasta que llega a bodega |
| **EOQ** (cantidad económica de pedido) | El tamaño de pedido que equilibra el costo de pedir muchas veces contra el de guardar mucho |
| **Punto de reorden (ROP)** | El nivel en el que hay que volver a pedir para que lo que queda alcance mientras llega el barco |
| **Stock de seguridad (SS)** | Colchón extra por si el barco se demora o se vende más de lo normal |
| **Nivel de servicio (ciclo)** | Probabilidad de NO quedarse sin stock mientras llega un pedido (95 % → z = 1,645) |
| **Fill rate** | % de la demanda total que sí se atendió |
| **Posición de inventario** | Bodega + lo que viene en camino. Es lo que se mira para decidir |
| **Monte Carlo** | Repetir la simulación muchas veces con números aleatorios y analizar los promedios |
| **Réplica** | Una repetición completa del año simulado |
| **Intervalo de confianza 95 %** | Rango donde está el costo promedio verdadero con 95 % de confianza: media ± 1,96·s/√n |
| **Números aleatorios comunes** | Todas las políticas se prueban con el mismo futuro para compararlas de forma justa (reducción de varianza) |
| **Periodo de calentamiento** | Días iniciales que se simulan pero no se cuentan, para que el arranque no sesgue |
| **Sesgo de inicialización** | Si todas las réplicas arrancan igual, el resultado depende de ese arranque. Por eso el inventario inicial es aleatorio |
| **Verificación vs validación** | Verificar = el programa hace lo que decimos. Validar = el modelo se parece a la realidad o a la teoría |
| **Análisis de sensibilidad** | Mover un parámetro y ver cómo cambia el resultado |
| **Prueba de estrés** | Simular un escenario malo para ver qué política aguanta |

---

## 10. Preguntas probables del profe

**¿Por qué Python y no Arena?** Python permite separar el modelo en módulos claros, correr 1.000 réplicas en segundos y hacer los análisis estadísticos y gráficas en el mismo programa. La lógica es la misma de Arena (entidades, atributos, decisiones, réplicas) y la tabla de la sección 2 muestra la equivalencia.

**¿Cómo saben que el modelo está bien?** `validacion.py` hace 4 pruebas: (1) balance de unidades: inicial + recibido = vendido + final; (2) la demanda simulada tiene la media esperada (error 0,01 %); (3) el lead time simulado coincide con el teórico (error 0,04 %); (4) **sin aleatoriedad, la simulación da lo mismo que la fórmula del EOQ** (error < 1 %).

**¿Por qué 1.000 réplicas?** Con 1.000 el intervalo de confianza del costo de C queda en ± $0,4 M, suficientemente estrecho para separar las políticas. Las diferencias entre políticas son de $5 M o más.

**¿Por qué el lead time es una suma de distribuciones?** Porque cada etapa tiene una incertidumbre distinta y así se puede explicar de dónde sale cada día de retraso. Además permite simular la crisis cambiando solo el tránsito y las inspecciones.

**¿Por qué triangular?** Se usa cuando no hay muchos datos pero se conocen el mínimo, el máximo y el valor más probable (por ejemplo, preguntándole a la naviera o al agente de aduanas).

**¿Por qué el inventario inicial es aleatorio?** Si todas las réplicas arrancan con el mismo inventario, quedan en la misma fase del ciclo de pedidos y el resultado depende de esa suposición (sesgo de inicialización). El experimento 4 muestra que con el arranque aleatorio B, C y D dan casi lo mismo sin importar el rango.

**¿Por qué A sale tan bien en ventas perdidas?** Porque arranca con un colchón grande y nunca lo ajusta, y paga ese colchón todo el año ($51 M solo en mantener). El experimento 4 muestra que su resultado depende de cómo arranca.

**¿Por qué el óptimo en crisis sale en el extremo (99,99 %)?** Porque la política se diseñó para un barco de 58 días y ahora tarda 72. Ningún colchón "normal" alcanza. La solución correcta no es subir el z indefinidamente sino **recalcular la política con los datos nuevos** ($72,2 M).

**¿Qué es la comparación pareada?** Como todas las políticas vieron el mismo futuro, se resta el costo de cada una réplica por réplica y se saca el intervalo de esa diferencia. Si no contiene el cero, la diferencia es real y no suerte.

---

## 11. Sugerencia para repartir la sustentación

Como pueden escoger a cualquiera, **todos deben entender las secciones 3, 5 y 7**. Para la exposición:
1. Problema y caso (secciones 1 y 4) + gráfica `01_entradas_aleatorias.png`
2. Módulos y secuencia lógica (secciones 2 y 3) + demo de `app.py`
3. Políticas y fórmulas (sección 5) + gráfica `02_trayectorias_inventario.png`
4. Resultados y riesgo (sección 6) + gráficas `03` y `04`
5. Sensibilidad, crisis y conclusiones (secciones 6 y 7) + gráficas `05` y `06`
