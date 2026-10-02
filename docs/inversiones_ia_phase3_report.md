# Inversiones IA 3.0 — Informe de aprobación de la fase 3

Fecha de validación: 2026-10-02 (UTC)

## Resultado

**APROBADA.** El motor heurístico `3.0.0` cumple los controles definidos para la fase 3 de `mejoras 3.0.md`.

## Implementación

- Se creó un núcleo único en `technical_engine.py`; escáner y portafolio consumen las mismas fórmulas y estados.
- RSI y ATR usan suavizado de Wilder; MACD explicita línea, señal, histograma y pendiente; Bollinger fija ventana, desviaciones y `ddof`.
- SMA20/50/200 y todos los indicadores respetan observaciones mínimas. Un dato ausente permanece ausente.
- El score se normaliza exclusivamente sobre variables disponibles y se abstiene con cobertura inferior a 60%.
- Cada evaluación incluye `heuristic_version`, régimen, tres horizontes, estado, cobertura, contribuciones, faltantes y restricciones.
- Se definieron `COMPRAR`, `MANTENER/ESPERAR`, `REDUCIR`, `SALIR` y `SIN SEÑAL`.
- Cotizaciones vencidas, mala calidad e iliquidez obligan a abstenerse.
- Las acciones corporativas se revelan para revisión y los ETF apalancados no pueden recibir compra de tendencia basada solo en técnico clásico.
- La confianza aprendida ya no cambia la señal; solo puede filtrar el envío de una alerta.
- La UI muestra versión, horizontes, contribuciones, faltantes y restricciones, y distingue resultados heredados.

La definición matemática completa se encuentra en `docs/technical_engine_3_0.md`.

## Evidencia contra criterios de pase

| Control | Criterio | Evidencia | Estado |
|---|---|---|---|
| Fórmulas | Coincidencia ≥99.9% | RSI, MACD, señal, histograma, Bollinger y ATR: 100% de puntos comparables dentro de 0.1% frente a implementaciones pandas independientes | APROBADO |
| Series sintéticas | 100% con régimen esperado | 6/6: tendencia alcista, bajista, lateral, salto, alta volatilidad y ruido | APROBADO |
| Datos faltantes | Degrada o se abstiene | Serie de 10 observaciones: cobertura <60%, faltantes explícitos y `SIN SEÑAL` | APROBADO |
| Explicación | Tolerancia ±0.01 | Baseline + contribuciones = score mostrado; diferencia observada 0.002891 | APROBADO |
| Versionado | 100% de recomendaciones | Evaluación, salida de escáner y salida de portafolio incluyen `3.0.0`; prueba dinámica del escáner aprobada | APROBADO |
| ETF apalancados | Sin largo plazo solo técnico | Horizonte 20–60 forzado a `SIN SEÑAL` y restricción explícita | APROBADO |

## Validación ejecutada

- `tests/test_inversiones_phase3.py`: 18/18.
- Regresión fase 2: 13/13.
- Regresión fase 1: 6/6.
- Total: 37/37 pruebas aprobadas.
- `node --check tools/NOTIFICADOR_BOT/app.js`: aprobado.
- `python -m compileall -q src tools/NOTIFICADOR_BOT`: aprobado.
- Serialización JSON estricta (`allow_nan=False`) de una recomendación completa: aprobada.
- UI `/bolsa`: detalle renderizado, MACD/ señal/ histograma visibles, datos heredados identificados y consola sin errores.
- `git diff --check`: aprobado.

## Observaciones de diseño

- El score mostrado mantiene escala 0–100 para compatibilidad, pero deriva de un score direccional normalizado de -1 a 1.
- El horizonte swing (5–20 sesiones) es el estado principal; corto y tendencia se publican por separado.
- Los ajustes adaptativos y la confianza no mutan silenciosamente el motor versionado. Su evaluación estadística corresponde a fases posteriores.
