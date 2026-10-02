# Inversiones IA 3.0 — Informe de aprobación de la fase 4

Fecha de validación: 2026-10-02 (UTC)

## Resultado

**APROBADA.** El ciclo de etiquetas, verificación y feedback cumple los parámetros de pase definidos para la fase 4 de `mejoras 3.0.md`.

## Implementación

- Se creó un libro mayor SQLite append-only para predicciones, resultados de mercado, feedback humano, ajustes auditados y recuperación histórica.
- Cada predicción conserva identificador, activo, mercado, timestamps UTC de datos y emisión, horizonte, entrada esperada, features y versiones, señal, probabilidad, score, modelo/hash, reglas de riesgo y fuente.
- Los triggers impiden actualizar o eliminar predicciones y feedback ya registrados.
- Cada escaneo crea predicciones independientes para 1, 3, 5, 10 y 20 sesiones; los resultados conservan el horizonte que los originó.
- La verificación usa la apertura ejecutable de `t+1`, el cierre de la sesión de vencimiento y costos separados de comisión de entrada/salida, spread y deslizamiento.
- Se añadieron etiquetas ternarias para compras y costo de oportunidad para salidas.
- El calendario contempla fines de semana, feriados observados, Viernes Santo, Juneteenth y medias sesiones de NYSE.
- El job de recuperación se ejecuta independientemente cada seis horas y convierte datos faltantes fuera de gracia en estados irrecuperables explicados por suspensión/delisting.
- El feedback positivo o negativo exige predicción, motivo estructurado, usuario y rol; se almacena como evidencia auxiliar y nunca modifica pesos ni activa un modelo.
- Las propuestas y revisiones de ajustes tienen historial auditable. Una aprobación no equivale a activación.
- Las 10 recomendaciones heredadas del 8 de septiembre de 2026 quedaron resueltas como irrecuperables, porque su esquema no contiene timestamps UTC, horizonte, entrada `t+1`, fuente, versiones/hash ni costos suficientes para reconstruir resultados sin supuestos o fuga temporal.
- La interfaz explica el flujo auditable, muestra retorno neto y ofrece feedback positivo/negativo solo cuando existe un `prediction_id` válido.

## Evidencia contra criterios de pase

| Control | Criterio | Evidencia | Estado |
|---|---|---|---|
| Registro | 100% inmutable y trazable | Campos obligatorios validados y triggers bloquean `UPDATE`/`DELETE` | APROBADO |
| Verificación automática | ≥99% dentro de 1 sesión del vencimiento | Ensayo sintético: 100/100 verificadas al vencer; 100% | APROBADO |
| Pendientes antiguos | 0 sin explicación | 10/10 heredadas resueltas; `unexplained_pending_count = 0` | APROBADO |
| Costos | 100% de resultados con costos configurados | Comisión de entrada/salida, spread y deslizamiento presentes por separado | APROBADO |
| Horizontes | 0 mezclas | Predicción y resultado distintos para 1/3/5/10/20; sesión de salida comprobada para cada horizonte | APROBADO |
| Feedback | 100% identificado y sin mutación | Usuario, rol, hora, motivo y activo obligatorios; 0 ajustes creados por clic | APROBADO |
| Calendario | 100% de pruebas | Fin de semana, feriados, feriados observados y media sesión aprobados | APROBADO |

## Validación ejecutada

- `tests/test_inversiones_phase4.py`: 19/19.
- Regresión fase 3: 18/18.
- Regresión fase 2: 13/13.
- Regresión fase 1: 6/6.
- Total: 56/56 pruebas aprobadas.
- `node --check tools/NOTIFICADOR_BOT/app.js`: aprobado.
- `python -m compileall -q src tools/NOTIFICADOR_BOT`: aprobado.
- `git diff --check`: aprobado.
- API aislada en puerto de validación: contrato v3 cargado, `legacy_irrecoverable = 10`, `pending = 0` y validación de campos de feedback aprobada.
- UI `/bolsa`: página cargada con el texto auditable actualizado y consola sin advertencias ni errores.

## Recuperación histórica

El detalle máquina-legible está en `docs/legacy_predictions_recovery_2026-09-08.json`. Las filas no se etiquetaron como acierto o fallo porque hacerlo requeriría inventar parámetros que el sistema antiguo nunca guardó.

## Alcance deliberado

Esta fase registra evidencia y habilita revisión; no reentrena ni despliega modelos automáticamente. El reentrenamiento, la validación walk-forward y la comparación contra baseline corresponden a la fase 5 y no se iniciaron.
