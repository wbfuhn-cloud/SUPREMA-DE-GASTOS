# Catálogo API — Inversiones IA baseline

Todas las rutas están implementadas en `src/server.py`.

| Método | Ruta | Tipo |
|---|---|---|
| GET | `/bolsa` | UI |
| GET | `/visor/<path>` | Assets |
| GET | `/api/bolsa/health` | Operación |
| GET | `/api/bolsa/readiness` | Operación |
| POST | `/api/scan/start` | Mutación |
| POST | `/api/scan/stop` | Mutación |
| GET | `/api/scan/status` | Lectura |
| GET | `/api/scan/results` | Lectura |
| GET | `/api/learner/stats` | Lectura |
| GET | `/api/learner/history` | Lectura |
| POST | `/api/learner/feedback` | Mutación |
| GET | `/api/ml/status` | Lectura |
| POST | `/api/ml/retrain` | Mutación crítica |
| GET | `/api/cache/stats` | Lectura |
| POST | `/api/cache/clear` | Mutación |
| POST | `/api/risk/calculate` | Cálculo |
| GET/POST | `/api/portfolio/config` | Lectura/mutación |
| POST | `/api/portfolio/update` | Mutación |
| POST | `/api/portfolio/analyze` | Cálculo/mutación |

## Deuda detectada

- El cliente solicita `GET /api/prices/history`, pero la ruta no existe.
- Las respuestas no tienen un sobre uniforme de error.
- El estado ML expone rutas locales absolutas.
- Falta contrato versionado para timestamps, proveedor y frescura.
- Las mutaciones críticas necesitan autorización antes de producción.
