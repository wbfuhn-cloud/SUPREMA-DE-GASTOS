# Inversiones IA 3.0 — Informe de aprobación de la fase 7

Fecha: 2026-10-02 (UTC)

## Resultado

**FASE 7 APROBADA.** Se incorporó un motor de fusión determinista y explicable para producir un único veredicto por activo y horizonte: `COMPRAR`, `ESPERAR`, `MANTENER`, `REDUCIR`, `SALIR` o `SIN SEÑAL`.

El estado actual de producción es deliberadamente conservador: como el modelo ML de la fase 5 no está aprobado y Fourier permanece experimental, el sistema real no puede emitir compras atribuidas a esos módulos. Continúa usando la heurística y el riesgo para esperar, mantener, reducir o salir.

## Diseño implementado

- Entradas independientes para heurística, probabilidad calibrada de subida, probabilidad calibrada de bajada, Fourier, calidad, régimen y riesgo.
- Fourier solo puede contribuir si `spectral_validated = true`; actualmente siempre queda excluido.
- Compra solo con modelo aprobado, probabilidad calibrada ≥65%, edge neto suficiente, heurística favorable, régimen aceptable y presupuesto de riesgo disponible.
- Salida separada con probabilidad de caída ≥60%, stop, trailing stop o deterioro heurístico severo.
- Reducción por riesgo agregado >5%, concentración >25%, régimen de crisis o toma parcial de ganancias.
- Abstención obligatoria con calidad <95%, OOD, precio/ATR inválido o capital insuficiente.
- ETF apalancado sin compra estructural.
- Edge mínimo mayor entre dos veces los costos y `0.25 × ATR/precio`.
- Riesgo por operación limitado a 0.5%–1.0% y riesgo agregado posterior máximo de 5%.
- Cada resultado incluye factores a favor, factores en contra y gatillos de invalidación.
- Toda compra incluye acciones, entrada, stop, pérdida máxima, presupuesto, porcentaje de riesgo y horizonte.
- Hash SHA-256 determinista de entrada y salida para reproducibilidad.

## Integración

- `stock_scanner.py` calcula la fusión para horizontes corto, swing y tendencia; el estado swing es el veredicto principal.
- `portfolio_analyzer.py` usa `has_position = true` cuando existe cantidad y precio de entrada, y aplica stops y toma parcial.
- `app.js` muestra el veredicto fusionado, argumentos, invalidación y plan de riesgo.
- El score heurístico original permanece visible y separado; no se oculta ni se suma dos veces.

## Evidencia contra criterios de pase

| Control | Criterio | Evidencia | Estado |
|---|---|---|---|
| Coherencia | 0 compras y salidas simultáneas | El contrato devuelve un único estado escalar; matriz de estados aprobada | APROBADO |
| Abstención | Calidad <95% u OOD | Todos los casos controlados devuelven `SIN SEÑAL` | APROBADO |
| Explicación | 100% con a favor, en contra e invalidación | Los tres arreglos son obligatorios y nunca vacíos | APROBADO |
| Riesgo | 100% de compras con plan completo | Tamaño, stop, pérdida máxima, presupuesto, porcentaje y horizonte verificados | APROBADO |
| Calibración | Banda dentro de ±5 pp | Bandas controladas 0.62→0.60 y 0.80→0.80 aprobadas | APROBADO |
| Repetibilidad | Misma entrada/versiones, mismo resultado | Igualdad completa y mismo `decision_hash` | APROBADO |

## Validación solicitada

Se ejecutaron exactamente **3 pruebas integrales nuevas**:

1. Coherencia de estados y abstención obligatoria por calidad/OOD.
2. Compra con riesgo, explicación, integración UI/escáner y reproducibilidad.
3. Calibración por bandas y salida independiente de la compra.

Resultado: **3/3 aprobadas**. También se verificaron sintaxis JavaScript, compilación Python y limpieza del diff, sin repetir las baterías históricas.

## Limitación honesta

La prueba de calibración valida el contrato matemático con observaciones controladas. Todavía no existen suficientes predicciones reales verificadas para acreditar calibración productiva. Por ello el modelo ML sigue desactivado, y la puerta de compra no se abre en la operación actual.

No se inició la fase 8.
