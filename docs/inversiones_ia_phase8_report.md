# Inversiones IA 3.0 — Informe de cierre de la fase 8

Fecha: 2026-10-02 (UTC)

## Resultado

**FASE 8 COMPLETADA A NIVEL DE INFRAESTRUCTURA; ESTRATEGIA NO APROBADA.** El backtester y las puertas económicas quedaron implementados y validados. No se autoriza el avance a paper trading porque faltan datos históricos trazables y composición histórica del universo.

Publicar métricas de rentabilidad en estas condiciones requeriría usar la lista actual del S&P 500/Nasdaq para el pasado, lo cual introduce sesgo de supervivencia y es un bloqueador explícito de `mejoras 3.0.md`.

## Backtester implementado

- Arquitectura dirigida por eventos.
- Señal emitida en `t` ejecutada únicamente en la siguiente apertura disponible.
- Gaps incorporados mediante el precio de apertura ejecutable.
- Comisiones, medio spread, slippage base e impacto dependiente de participación/volumen.
- Rechazo de órdenes por liquidez, efectivo insuficiente, posición inexistente o ausencia del universo histórico.
- Límite configurable de participación en volumen y capacidad aproximada.
- Splits que ajustan acciones y costo promedio; dividendos acreditados en efectivo.
- Impuestos opcionales y desactivados por defecto hasta definir jurisdicción.
- Reducción parcial y salida total.
- Walk-forward anclado y rodante con test final reservado e inaccesible a desarrollo.
- Bootstrap determinista de valor esperado.
- Corrección Bonferroni para múltiples experimentos.
- Sensibilidad de parámetros y comparación homogénea de estrategias.
- Segmentación por régimen, sector, liquidez, volatilidad y horizonte.

## Métricas disponibles

- CAGR y retorno acumulado.
- Volatilidad anualizada, Sharpe y Sortino.
- Drawdown máximo y duración, Calmar.
- Profit factor, win rate, payoff y valor esperado por operación.
- Turnover, exposición y tiempo promedio en posición.
- Precisión de compra por horizonte.
- La precisión de salida permanece `null` hasta contar con el retorno contrafactual posterior a la salida; no se inventa una etiqueta.
- Costos totales y capacidad aproximada por liquidez.
- Contribución de las cinco mejores operaciones.

## Comparaciones preparadas

La interfaz de comparación admite:

1. buy & hold SPY;
2. buy & hold QQQ;
3. heurística;
4. ML;
5. heurística + ML;
6. heurística + ML + Fourier;
7. estrategia sin salida aprendida;
8. estrategia con salida aprendida.

Ninguna variante fue ejecutada sobre datos falsos. El estado de cada una es `NOT_EVALUATED` en `docs/backtest_phase8_evaluation.json`.

## Parámetros de aprobación

| Métrica | Criterio | Evidencia real | Estado |
|---|---:|---:|---|
| Valor esperado neto | >0 con CI bootstrap 95% no materialmente negativo | No disponible | NO APROBADO |
| Sharpe OOS | ≥1.0 o benchmark +0.25 | No disponible | NO APROBADO |
| Drawdown | ≤15% | No disponible | NO APROBADO |
| Profit factor | ≥1.25 | No disponible | NO APROBADO |
| Folds rentables | ≥70% | No disponible | NO APROBADO |
| Top 5 operaciones | <30% del beneficio | No disponible | NO APROBADO |
| Costos 2× | Sigue viable | No disponible | NO APROBADO |
| Sensibilidad ±10% | No destruye resultado | No disponible | NO APROBADO |
| Fourier | Ablación de fase 6 | Falló por falta de datos reales | NO APROBADO |

## Bloqueadores confirmados

- Cero predicciones verificadas utilizables para entrenamiento/backtest.
- No existe una serie histórica versionada con los datos visibles en cada timestamp.
- No existe composición histórica del universo para evitar supervivencia.
- El ML continúa como experimento y Fourier no superó ablación real.

El test final se mantiene `UNTOUCHED`; no se consultó para ajustar parámetros.

## Validación compacta

Se ejecutaron exactamente **3 pruebas integrales nuevas**:

1. Ejecución `t+1`, gaps, costos, liquidez, universo histórico, splits y dividendos.
2. Walk-forward anclado/rodante, reserva del test final y bootstrap reproducible.
3. Cobertura de métricas y rechazo obligatorio sin evidencia real.

Resultado: **3/3 aprobadas**. También se verificó compilación y limpieza del diff.

## Decisión

`DO_NOT_ADVANCE_TO_PAPER_TRADING`.

La fase 9 no se inició. Primero debe acumularse un dataset prospectivo trazable o adquirirse una fuente histórica point-in-time que incluya universo, precios, acciones corporativas y liquidez.
