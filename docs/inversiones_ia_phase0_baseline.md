# Inversiones IA 3.0 — Fase 0: línea base

Fecha de captura: 2026-10-01.

## Identidad reproducible

- Repositorio: `https://github.com/wbfuhn-cloud/SUPREMA-DE-GASTOS.git`.
- Rama: `main`.
- Commit base: `d7185c20a0f89628acc4f80a98d7c1dd74bb7f94`.
- Modelo: `tools/NOTIFICADOR_BOT/stock_ml_model.joblib`.
- SHA-256: `B1DB368B295A758130022C6D7A327F5B1CE544D85A7850351962AC012180BBE6`.
- Python: 3.12.10; Flask: 3.1.3; pandas: 3.0.5.
- scikit-learn: 1.9.0; joblib: 1.6.0.

La copia se creó desde el commit. El cambio operativo de
`database/last_scan_results.json`, `.env`, la base activa y la caché no se
copiaron ni modificaron.

## Componentes

| Componente | Archivo | Responsabilidad |
|---|---|---|
| Rutas HTTP | `src/server.py` | UI, escaneo, learner, ML, riesgo y portafolio |
| Cliente | `tools/NOTIFICADOR_BOT/app.js` | Estado, render y llamadas API |
| Vista | `tools/NOTIFICADOR_BOT/index.html` | Interfaz `/bolsa` |
| Escáner | `tools/NOTIFICADOR_BOT/stock_scanner.py` | Datos, indicadores y score |
| Predictor | `tools/NOTIFICADOR_BOT/ml_predictor.py` | Inferencia y entrenamiento |
| Aprendizaje | `tools/NOTIFICADOR_BOT/recommendation_learner.py` | Resultado y feedback |
| Riesgo | `tools/NOTIFICADOR_BOT/risk_calculator.py` | Tamaño, stop y objetivo |
| Portafolio | `tools/NOTIFICADOR_BOT/portfolio_analyzer.py` | P&L y veredictos |

## Modelo baseline

- Gradient Boosting; 4,001 muestras; 838 positivas (20.94%).
- ROC-AUC 74.78%; precision 33.69%; CV precision 24.35%.
- CV recall 55.25%; CV F1 33.24%.
- Entrenado: 2026-09-05T13:15:17.467007.
- 18 features; Fourier/FFT/DFT no aparece en el modelo activo.

## Aprendizaje baseline

- 10 recomendaciones; 10 pendientes; 0 verificadas; 0 ajustes.
- Todos los pesos adaptativos permanecen en 1.0.

## Verificación inicial

| Comprobación | Resultado |
|---|---|
| Copia Git | Limpia antes de Fase 0 |
| Compilación | Correcta (`compileall`, salida 0) |
| Suite | El entorno original no incluye pytest ni Pillow |
| Gemini | Corregida para ser opt-in y no imprimir secretos |
| `/api/prices/history` | Devuelve 404 en baseline |
| Pestañas Gemas/IA | No cambian el panel en baseline |

## Reproducción

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m compileall -q src tools\NOTIFICADOR_BOT
.venv\Scripts\python -m pytest
```

Las pruebas externas quedan excluidas. Requieren credenciales de prueba y
`RUN_LIVE_GEMINI_TESTS=1`.

## Criterio de cierre

La fase se cierra cuando inventario, catálogo API, hash, baseline y política de
secretos están versionados, la copia compila y el commit de fase queda limpio.

