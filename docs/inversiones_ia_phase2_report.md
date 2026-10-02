# Inversiones IA 3.0 — Informe de aprobación de la fase 2

Fecha de validación: 2026-10-02 (UTC)

## Resultado

**APROBADA.** La fase 2 cumple los parámetros cuantitativos definidos en `mejoras 3.0.md`.

## Contrato implementado

- Contrato canónico de cotización `3.0` con símbolo, precio, moneda, proveedor, timestamp de mercado, timestamp de recepción, intervalo, sesión, estado ajustado, frescura y calidad.
- UTC como zona horaria interna; la sesión de mercado se deriva únicamente para presentación.
- OHLC ajustado y crudo conservados en columnas independientes; el volumen no se altera con factores que también incorporan dividendos.
- Resultados heredados sin procedencia o timestamp se marcan `legacy_unknown`, vencidos y no elegibles para señal.
- El escáner y el portafolio comparten la misma cotización canónica. El tipo de cambio tiene contrato, versión y timestamp.
- Los fundamentales ausentes permanecen como `null`/`N/D`; no se presentan como cero verificado.
- Divergencias entre proveedores superiores a la tolerancia quedan marcadas para revisión.

## Evidencia contra los criterios de pase

| Métrica | Umbral | Resultado observado | Estado |
|---|---:|---:|---|
| Consistencia escáner/portafolio | ≤ 0.10%, igual timestamp | 0.000000% en TEM, SOXS y TSLA; timestamp idéntico | APROBADO |
| Completitud OHLCV | ≥ 99.5% | 100% en conjunto válido; umbral aplicado por el validador | APROBADO |
| Duplicados | 0 | El validador detecta y rechaza el caso duplicado | APROBADO |
| Frecuencia y huecos | Identificados | Frecuencia esperada calculada y hueco sintético detectado (`missing_intervals:1`) | APROBADO |
| Acciones corporativas | 100% del conjunto | Split 2:1 ajustado correctamente, valores crudos preservados | APROBADO |
| Datos vencidos | 100% detectados/bloqueados | Caso diario vencido y todos los registros heredados bloqueados | APROBADO |
| Valores faltantes | 0 conversiones silenciosas | Beta, margen y capitalización permanecen `None`/`N/D` | APROBADO |
| Trazabilidad | 100% | Contrato válido exige proveedor y timestamps; legado se identifica expresamente | APROBADO |
| Tipo de cambio intradía | ≤ 15 min | Prueba de contrato: 14 min | APROBADO |
| Reconciliación | Diferencia > tolerancia señalada | Divergencia de proveedor marcada `requires_review=true` | APROBADO |

## Verificación ejecutada

- `tests/test_inversiones_phase2.py`: 13/13 pruebas aprobadas.
- Regresión `tests/test_inversiones_phase1.py`: 6/6 pruebas aprobadas.
- `node --check tools/NOTIFICADOR_BOT/app.js`: aprobado.
- `python -m compileall -q src tools/NOTIFICADOR_BOT`: aprobado.
- `git diff --check`: sin errores de espacios.
- API local `/api/scan/results`: contrato `3.0`, estado `ok`.
- API local `/api/portfolio/analyze`: TEM, SOXS y TSLA con precio y timestamp idénticos a escáner.
- Interfaz local `/bolsa`: carga correcta; proveedor/frescura visibles y las observaciones heredadas muestran “Datos sin timestamp · Proveedor no identificado”.

## Bloqueadores revisados

- La discrepancia histórica TSLA 364.86 vs 354.11 queda eliminada dentro de una misma observación: escáner y portafolio reutilizan 364.86 con el mismo timestamp.
- Ya puede conocerse el momento exacto de toda cotización nueva; si falta, la observación se invalida de forma explícita.
- Los indicadores y el precio canónico usan la misma serie ajustada; las columnas crudas se conservan para auditoría.

## Archivos principales

- `tools/NOTIFICADOR_BOT/market_data.py`
- `tools/NOTIFICADOR_BOT/stock_scanner.py`
- `tools/NOTIFICADOR_BOT/portfolio_analyzer.py`
- `src/server.py`
- `tools/NOTIFICADOR_BOT/app.js`
- `tools/NOTIFICADOR_BOT/style.css`
- `tests/test_inversiones_phase2.py`
