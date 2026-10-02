# Inversiones IA 3.0 — Informe de cierre de la fase 5

Fecha: 2026-10-02 (UTC)

## Resultado

**FASE 5 COMPLETADA; MODELO ML RECHAZADO PARA PRODUCCIÓN.** Se aplicó la regla de decisión del plan: la aplicación queda identificada como analizador heurístico y el Gradient Boosting heredado se conserva únicamente como experimento.

## Hallazgo principal

El artefacto `stock_ml_model.joblib` declara 4,001 muestras y 838 positivos, pero la base disponible permite reconstruir exactamente **0** de esas muestras. Las únicas 10 recomendaciones persistentes son del 8 de septiembre de 2026, no están verificadas y la fase 4 ya justificó por qué son irrecuperables.

No existe evidencia reproducible para acreditar el AUC declarado de 74.78%. El artefacto tampoco contiene PR-AUC, precision@10%, Brier, ECE, rentabilidad por fold, drawdown, comparación de benchmarks, perfil OOD ni calibración fuera de muestra.

## Decisión aplicada

- Hash SHA-256 auditado: `b1db368b295a758130022c6d7a327f5b1ce544d85a7850351962ac012180bbe6`.
- Versión identificada: `legacy-1.0`.
- Estado: `experiment_only`.
- `production_approved`: `false`.
- La instancia conserva el modelo como `experimental_model`, pero no lo usa para señales.
- La aplicación no muestra probabilidad ni confianza ML numérica sin validación y calibración.
- Todas las señales actuales degradan explícitamente a `heuristic_fallback` con motivo.

## Infraestructura incorporada

- Split walk-forward expansivo con purga y embargo en sesiones.
- Puerta de aprobación que exige todos los umbrales de `mejoras 3.0.md`.
- Cálculo de Expected Calibration Error.
- Perfil OOD por percentiles de entrenamiento y marcado explícito de variables fuera de distribución.
- Contrato de salida con `model_prediction`, `calibrated_probability`, `model_version`, `top_features`, `buy_score`, `exit_score`, `ood_detected` y `degraded_reason`.
- Compra y salida se mantienen como scores distintos; la ausencia de un modelo de salida se representa con `exit_score = null`.
- Hash del artefacto y razón de degradación expuestos por `/api/ml/status`.

## Parámetros de pase del modelo

| Métrica | Umbral | Evidencia reproducible | Resultado |
|---|---:|---:|---|
| PR-AUC | prevalencia + 0.10 | No disponible | RECHAZADO |
| Precision top 10% | ≥55% y benchmark +10 pp | No disponible | RECHAZADO |
| Brier | 10% mejor que prevalencia | No disponible | RECHAZADO |
| ECE | ≤0.05 | No disponible | RECHAZADO |
| Folds rentables | ≥70% neto de costos | No disponible | RECHAZADO |
| Peor fold | ≥−1.5× presupuesto de riesgo | No disponible | RECHAZADO |
| OOD | 100% detectado y marcado | Contrato incorporado; artefacto sin perfil | Degrada |
| Integración | ≥95% señales elegibles | Modelo no aprobado | No aplica |
| Reproducibilidad | mismas entradas/versión | Dataset original ausente | RECHAZADO |

La fase se cierra correctamente porque la regla del plan exige retirar el modelo de producción cuando no supera los umbrales, no fabricar una aprobación.

## Actualizaciones de GitHub priorizadas

- Comprobación automática y no bloqueante al iniciar `src/app.py`.
- Descarga de la última publicación en cualquier PC sin necesidad de Git.
- ZIP/EXE, validación de tamaño, hash SHA-256, descarga atómica `.part` y estado persistente.
- Fallo de red tolerado sin impedir el arranque.
- Workflow de GitHub Actions que crea un ZIP por cada etiqueta `v*`.
- La configuración y publicación se documentan en `docs/github_updates.md`.

## Validación solicitada

Se ejecutaron exactamente **3 pruebas integrales nuevas**:

1. Walk-forward con purga/embargo y puerta de métricas completa.
2. Rechazo del artefacto heredado, fallback heurístico y detección OOD.
3. Detección y descarga de una GitHub Release, hash y estado, sin auto-instalar.

Resultado: **3/3 aprobadas**. También se ejecutaron comprobaciones estáticas de sintaxis/compilación y limpieza del diff; no se repitió la batería histórica de fases anteriores.

## Repositorio de actualizaciones

El repositorio real quedó configurado como `wbfuhn-cloud/SUPREMA-DE-GASTOS`. `APP_UPDATE_REPOSITORY` continúa disponible para sobrescribirlo en instalaciones especiales.

No se inició la fase 6 ni el módulo Fourier.
