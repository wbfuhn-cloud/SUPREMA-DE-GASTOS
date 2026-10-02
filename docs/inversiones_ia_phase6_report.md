# Inversiones IA 3.0 — Informe de cierre de la fase 6

Fecha: 2026-10-02 (UTC)

## Resultado

**FASE 6 COMPLETADA; FOURIER QUEDA SOLO COMO EXPERIMENTO.** La librería espectral supera todos los controles matemáticos, sintéticos, de rendimiento y causalidad disponibles. No se incorpora a las señales de compra o salida porque no existe un dataset histórico trazable para demostrar la mejora de ablación en datos reales fuera de muestra.

Esta decisión aplica la regla de descarte de `mejoras 3.0.md`: una mejora técnica o sintética no equivale a capacidad predictiva económica.

## Implementación

- Log-retornos `ln(P_t/P_t-1)`; nunca FFT directa sobre precio bruto.
- Estandarización causal dentro de cada ventana y ventana Hann.
- DFT completa de referencia mediante sumas de seno y coseno.
- FFT real como algoritmo eficiente equivalente.
- Magnitud, fase, periodo y densidad espectral normalizada.
- Ventanas configurables de 32, 64, 128 y 252 sesiones.
- Periodo y potencia dominantes, potencia por bandas, entropía, fase y cambio de fase.
- Persistencia del periodo entre ventanas, SNR espectral, pendiente y curvatura reconstruidas.
- Reconstrucción limitada a `K` armónicos y como máximo a un ciclo dominante.
- Funciones candidatas separadas `BUY_CANDIDATE`, `EXIT_CANDIDATE` y `NO_SIGNAL`, marcadas permanentemente `production_enabled = false`.
- Abstención por calidad menor a 0.95, iliquidez, entropía alta o ciclo inestable.
- Evaluador de ablación para precision@K, Sharpe, generalización por folds y drawdown.

## Evidencia contra parámetros de pase

| Métrica | Criterio | Resultado | Estado |
|---|---:|---:|---|
| Exactitud FFT | Error relativo ≤1e-9 | `6.4639e-15` | APROBADO |
| Frecuencia sintética | Error ≤1 barra | `0.0` barras en ventanas 32/64/128/252 | APROBADO |
| Robustez al ruido | ≥90% | 100/100 con amplitud 0.01 y ruido gaussiano σ=0.002 | APROBADO |
| Estabilidad | ≥60% | 100% en 117 ventanas elegibles | APROBADO |
| Latencia | p95 ≤50 ms | 0.386 ms por activo | APROBADO |
| Fuga temporal | 0 hallazgos | 0 | APROBADO |
| Ablación | +3 pp precision@K o +0.15 Sharpe | Sin dataset real reproducible | NO ACREDITADO |
| Generalización | Mejora en ≥70% folds | Sin dataset real reproducible | NO ACREDITADO |
| Drawdown | No empeora >5% | Sin dataset real reproducible | NO ACREDITADO |

## Decisión sobre compra y salida

El módulo puede formular hipótesis de compra y salida para un backtest futuro, pero no interviene en:

- el score heurístico;
- la confianza mostrada;
- las alertas;
- la clasificación `COMPRAR`, `REDUCIR` o `SALIR`;
- el cálculo de tamaño o riesgo.

No se encontró evidencia válida para afirmar que un ciclo espectral mejora las entradas o salidas reales después de costos. Por ello, `approved_for_signals = false` y `decision = EXPERIMENT_ONLY`.

## Reproducibilidad

La evaluación usa semilla fija `20261002` y está implementada en `scripts/evaluate_fourier_phase6.py`. El resultado máquina-legible se guarda en `docs/fourier_phase6_evaluation.json`.

Se ejecutaron exactamente **3 pruebas integrales nuevas**:

1. Paridad entre la DFT expandida y FFT más recuperación del periodo conocido.
2. Robustez a ruido, estabilidad, latencia y repetibilidad causal.
3. Regla de descarte y bloqueo de producción sin ablación real.

Resultado: **3/3 aprobadas**. También se verificó compilación y limpieza del diff, sin repetir las baterías históricas.

## Trabajo futuro necesario antes de reconsiderarlo

Se requiere acumular predicciones verificadas de las fases 4–5 y ejecutar una comparación walk-forward real `baseline vs baseline + Fourier`, con costos, purga, embargo, activos y regímenes separados. Hasta entonces, Fourier es una herramienta educativa y exploratoria.

No se inició la fase 7.
