# Fase 9 — Paper trading y validación prospectiva

## Resultado

La infraestructura quedó implementada, pero la fase **no está aprobada todavía**. El veredicto inicial es `EXTEND_PAPER_TRADING`: los mínimos de 60 sesiones, 300 señales elegibles y 75 ejecutables deben recopilarse prospectivamente y no pueden reconstruirse ni simularse para declarar el pase.

## Implementación

- Protocolo congelado con hash reproducible de modelo, features, umbrales y reglas.
- Ledger SQLite append-only con deduplicación por `decision_hash`.
- Shadow mode mediante almacenamiento separado de señal baseline y candidata.
- Ejecuciones observadas con precio ejecutable, spread, slippage, latencia y desviación contra la cotización.
- Medición de sesiones, señales, datos vencidos, duplicados, latencia e incidentes.
- Registro de incidentes y simulacros del kill switch.
- Gate explícito con todos los parámetros del plan y regla de extensión.

## Estado de aprobación

El sistema debe operar en paper trading hasta cumplir todos los criterios con evidencia real. El modelo ML y Fourier siguen en modo experimental, sin autoridad para generar compras.
