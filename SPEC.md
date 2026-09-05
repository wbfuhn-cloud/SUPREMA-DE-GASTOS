# 📋 SPEC.md — Sistema de Machine Learning e Ingeniería de Software para /bolsa

## 1. VISIÓN Y RESULTADOS ESPERADOS
- **Objetivo**: Reemplazar/complementar el sistema heurístico lineal de sugerencia de acciones en `/bolsa` por un modelo supervisado de Machine Learning (`GradientBoostingClassifier`) entrenado sobre el histórico de recomendaciones y resultados de `learner.db`.
- **Criterios de éxito**:
  - Precisión de predicción $\ge 30\%$ en la recomendación de compra (vs $15.5\%$ base actual).
  - Cero regresiones en escaneo de acciones, alertas en vivo y portfolio.
  - Consumo adicional de memoria RAM $\le 20\text{ MB}$.
  - Calidad de código profesional: Cero excepciones silenciosas (`except: pass`), cero vulnerabilidades SQL Injection, cero duplicaciones críticas.
- **Usuario objetivo**: Usuario final y administrador de la plataforma "SUPREMA DE GASTOS".

## 2. LÍMITES DE ALCANCE
- ✅ **DENTRO del alcance**:
  - Integración de `scikit-learn` (`GradientBoostingClassifier`).
  - Extracción e ingeniería de 18 características desde `learner.db`.
  - Creación del módulo autónomo `tools/NOTIFICADOR_BOT/ml_predictor.py`.
  - Integración en `stock_scanner.py`, `recommendation_learner.py`, `server.py`, `app.js` e `index.html`.
  - Refactorización de código inseguro o redundante en la suite `tools/NOTIFICADOR_BOT/`.
- ❌ **FUERA del alcance**:
  - Uso de frameworks pesados de Deep Learning (TensorFlow, PyTorch) o librerías de alto consumo como XGBoost/LightGBM.
  - Modificación del modelo de datos de finanzas/gastos generales.
  - Cambios en el lector de correos (ya corregido y verificado).

## 3. RESTRICCIONES Y REQUISITOS
- **Stack técnico**: Python 3.10+, `scikit-learn`, `joblib`, `sqlite3`, Vanilla JS, HTML/CSS.
- **Reglas de arquitectura**:
  - Manejo de rutas nativo para Windows (`pathlib` o raw strings).
  - Logging estructurado con `logging`.
  - Fallback automático a puntuación heurística si el modelo ML no está entrenado o falla.
- **Seguridad**: Consultas SQL parametrizadas obligatorias. Cero concatenación de cadenas en SQL.

## 4. DECISIONES ARQUITECTÓNICAS (ADRs)
- **ADR 1: Modelo GradientBoostingClassifier**: Se elige Gradient Boosting sobre Random Forest por su capacidad superior para aprender con datasets desbalanceados (~15% casos positivos).
- **ADR 2: scikit-learn como única dependencia ML**: Mantiene el footprint de memoria extremadamente ligero (< 20MB extra), ideal para Windows de escasos recursos.
- **ADR 3: Híbrido ML + Heurística**: La puntuación final combina la señal heurística (0-100) con la probabilidad del modelo ML (0-100) para garantizar estabilidad operacional.

## 5. DESCOMPOSICIÓN EN TAREAS
- [x] Tarea 0: Creación de SPEC.md e implementación plan.
- [ ] Tarea 1: Instalación de `scikit-learn` en `.venv` y actualización de `requirements.txt`.
- [ ] Tarea 2: Desarrollo del módulo `ml_predictor.py`.
- [ ] Tarea 3: Refactorización y eliminación de inyección SQL en `recommendation_learner.py`.
- [ ] Tarea 4: Refactorización de `stock_scanner.py` (Excepciones explícitas, integración ML).
- [ ] Tarea 5: Limpieza de duplicados en `portfolio_analyzer.py` y fix en `config_manager.py`.
- [ ] Tarea 6: Integración de endpoints REST en `server.py` (`/api/ml/status`, `/api/ml/retrain`).
- [ ] Tarea 7: Actualización de la UI en `app.js` e `index.html`.
- [ ] Tarea 8: Entrenamiento, validación de métricas y reporte en `CHANGELOG.md`.

## 6. CRITERIOS DE VERIFICACIÓN
- Comprobación de instalación limpia de `scikit-learn`.
- Script de prueba de entrenamiento con validación temporal cruzada (`TimeSeriesSplit`).
- Verificación visual en la UI de la columna "ML Score" y badge de confianza.
- Verificación de ausencia de advertencias SQL injection y excepciones silenciosas.
