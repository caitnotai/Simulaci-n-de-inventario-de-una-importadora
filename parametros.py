"""
MÓDULO 1 — PARÁMETROS DEL CASO
================================
Aquí están TODOS los datos de entrada (inputs) del modelo. Si el profe pregunta
"¿qué pasa si el flete sube?" o "¿y si la demanda es más alta?", solo se cambia
un número aquí y se vuelve a correr.

Caso: "ImportaMotos del Caribe S.A.S." (empresa ficticia), una importadora de
Barranquilla que trae desde China KITS DE ARRASTRE para moto (cadena + piñón +
corona). Les vende a talleres y almacenes de repuestos de la región Caribe.

Problema real: cada pedido es un contenedor que tarda casi 2 meses en llegar
(fabricación + barco + aduana) y ese tiempo NO es fijo. Si piden poco o tarde,
se quedan sin producto y el cliente se va con la competencia (venta perdida).
Si piden mucho, tienen plata quieta en bodega. ¿Cuándo y cuánto pedir?

En el mundo empresarial esto es GESTIÓN DE INVENTARIOS / PLANEACIÓN DE
REABASTECIMIENTO, parte de la cadena de suministro (supply chain).
"""

from dataclasses import dataclass, field, replace


def _estacionalidad_colombia():
    """Multiplicador de la demanda por mes (promedio = 1.0).

    Diciembre sube por primas y temporada alta; junio sube un poco por la prima
    de mitad de año; enero y febrero son meses flojos (cuesta de enero).
    """
    return {
        1: 0.85, 2: 0.85, 3: 0.95, 4: 0.95, 5: 1.00, 6: 1.10,
        7: 1.00, 8: 0.95, 9: 0.95, 10: 1.00, 11: 1.05, 12: 1.35,
    }


@dataclass
class ParametrosCaso:
    # ---------------------------------------------------------------- DEMANDA
    demanda_media_diaria: float = 40.0   # kits/día en un mes "normal"
    demanda_desv_diaria: float = 12.0    # desviación estándar diaria (kits)
    estacionalidad: dict = field(default_factory=_estacionalidad_colombia)

    # ------------------------------------------ TIEMPO DE ENTREGA (LEAD TIME)
    # Se modela como la SUMA de las etapas reales de una importación:
    # 1) Fabricación en China: Uniforme(min, max)
    produccion_min: float = 10
    produccion_max: float = 20
    # 2) Tránsito marítimo Shanghái -> Cartagena/Barranquilla (vía Canal de
    #    Panamá): Triangular(min, más probable, max)
    transito_min: float = 28
    transito_moda: float = 32
    transito_max: float = 45
    # 3) Nacionalización en aduana (DIAN + agencia de aduanas): Triangular
    aduana_min: float = 3
    aduana_moda: float = 5
    aduana_max: float = 12
    # 4) Inspección física aleatoria de la DIAN: pasa con cierta probabilidad
    #    y agrega Uniforme(min, max) días extra
    prob_inspeccion: float = 0.15
    inspeccion_min: float = 5
    inspeccion_max: float = 10

    # ------------------------------------------------------- COSTOS (en COP)
    costo_unitario: float = 45_000          # costo del kit puesto en bodega
    precio_venta: float = 75_000            # precio al que se vende
    tasa_mantener_anual: float = 0.25       # 25 % anual: capital, bodega, seguro, obsolescencia
    costo_pedido: float = 12_000_000        # flete del contenedor + agencia + trámites, por pedido
    penalizacion_goodwill: float = 10_000   # "castigo" extra por cliente insatisfecho, por unidad

    # ---------------------------------------------------------- SIMULACIÓN
    dias_simulacion: int = 365         # horizonte que se MIDE (1 año: ene–dic)
    dias_calentamiento: int = 120      # días previos que se simulan pero NO se miden
    # Inventario con el que arranca cada réplica: se sortea Uniforme(min, max).
    # ¿Por qué aleatorio? Si todas las réplicas arrancan igual, todas quedan en la
    # misma "fase" del ciclo de pedidos y los resultados dependen de esa suposición
    # (SESGO DE INICIALIZACIÓN). El rango 2.500–8.000 imita la posición de
    # inventario de largo plazo de una política (Q, R), que es uniforme entre R y R+Q.
    inventario_inicial_min: int = 2_500
    inventario_inicial_max: int = 8_000
    replicas: int = 1_000              # cuántas veces se repite el año (Monte Carlo)
    semilla: int = 2026                # semilla para que los resultados sean reproducibles

    # ------------------------------------------------- VALORES DERIVADOS
    @property
    def costo_mantener_diario(self) -> float:
        """Costo de tener 1 kit guardado 1 día (holding cost)."""
        return self.costo_unitario * self.tasa_mantener_anual / 365

    @property
    def costo_mantener_anual(self) -> float:
        return self.costo_unitario * self.tasa_mantener_anual

    @property
    def costo_faltante(self) -> float:
        """Costo de NO tener 1 kit cuando el cliente lo pide (stockout cost).
        = margen que se deja de ganar + penalización por mala experiencia."""
        return (self.precio_venta - self.costo_unitario) + self.penalizacion_goodwill

    @property
    def demanda_anual(self) -> float:
        return self.demanda_media_diaria * 365

    @property
    def dias_totales(self) -> int:
        return self.dias_calentamiento + self.dias_simulacion

    def con_cambios(self, **cambios) -> "ParametrosCaso":
        """Copia de los parámetros con algunos valores cambiados (para escenarios)."""
        return replace(self, **cambios)


# Escenario de "crisis logística": así se vio en 2023-2024 con la sequía que
# restringió el paso por el Canal de Panamá: más días en el mar, más variación
# y más inspecciones. Las políticas se DISEÑAN con los datos normales (la empresa
# no sabe que viene la crisis) y luego se prueban con estos datos.
CAMBIOS_CRISIS = dict(
    transito_min=32,
    transito_moda=40,
    transito_max=70,
    prob_inspeccion=0.30,
)
