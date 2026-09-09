# Plan GPT 1.1 — Bolsa funcional, recomendaciones y Machine Learning

## Propósito

Convertir `/bolsa` en un módulo confiable para investigar oportunidades, comparar alternativas, administrar una cartera y probar decisiones en simulación. El resultado debe mostrar información aun cuando falle WebGL, una fuente externa o el modelo de Machine Learning.

La primera entrega no debe enviar órdenes con dinero real. El orden seguro es: datos verificables, modelo evaluado fuera de muestra, backtesting con costos, paper trading y, después de demostrar estabilidad, una integración real separada y con confirmación explícita.

## Estado comprobado el 8 de septiembre de 2026

La revisión se realizó sobre la URL indicada, las rutas Flask, los archivos del visor, la base del learner, el modelo guardado y el render en navegador.

### Por qué `/bolsa` parece vacío

Se comprobaron dos fallos independientes:

1. Al inicio de la revisión, `http://100.75.65.112:5050/bolsa` rechazó la conexión. No había un proceso escuchando en el puerto 5050. Después de iniciar `src/server.py`, la misma URL respondió `200` y entregó el HTML.
2. Con Flask activo, el DOM contiene el encabezado, controles y diez resultados, pero LiquidGL vuelve invisibles todos los elementos `.glass-panel`: les asigna `opacity: 0`, fondo transparente y `pointer-events: none`. Su canvas también queda transparente y los paneles no se restauran cuando falla o no termina la captura. El navegador no reporta un error visible, por lo que el usuario solo ve el fondo vacío.

Esta segunda causa es el defecto visual principal. Los datos existen detrás de una capa que ocultó la interfaz.

### Evidencia funcional

Con el servidor local iniciado:

| Recurso | Resultado |
| --- | --- |
| `/bolsa` | HTTP 200, HTML de 24,790 bytes. |
| `/visor/app.js` | HTTP 200, JavaScript válido. |
| `/visor/style.css` | HTTP 200. |
| `/static/theme-controller.js` | HTTP 200. |
| `/api/bolsa/health` | `status: ok`; archivos y motor disponibles. |
| `/api/scan/status` | Escaneo detenido, progreso 100 %, diez resultados. |
| `/api/ml/status` | Scikit-learn disponible y archivo de modelo cargado, pero el artefacto es incompatible al predecir. |
| `/api/learner/stats` | Diez recomendaciones pendientes y ninguna verificada. |

Los módulos Python relacionados compilan e importan correctamente. `app.js` también pasa un análisis sintáctico. Esto descarta un error de sintaxis como causa de la pantalla vacía.

## Hallazgos que deben corregirse

### Interfaz y disponibilidad

1. `tools/NOTIFICADOR_BOT/index.html` inicializa LiquidGL sobre todos los `.glass-panel`. Un efecto opcional puede ocultar toda la función principal.
2. El HTML contiene nueve IDs duplicados: `tsla-monitor`, `tsla-content`, `risk-capital`, `risk-pct`, `risk-atr`, `risk-output`, `details-content`, `ai-confidence-container` y `ai-confidence-content`.
3. La calculadora y el análisis utilizan `getElementById`; con IDs duplicados actualizan la primera copia y dejan la segunda desincronizada.
4. `app.js` consulta `/api/prices/history`, pero `src/server.py` no ofrece esa ruta.
5. La pantalla depende de CDN para Three.js, Lucide y fuentes. Una red bloqueada no debe impedir el contenido básico.
6. `/api/bolsa/health` confirma archivos del disco, pero no detecta un render invisible, duplicados, respuestas inválidas de API ni antigüedad de los datos.
7. El servidor se ejecuta en modo debug y el acceso depende de que el proceso permanezca activo. Falta un supervisor y una comprobación de disponibilidad durante el arranque.
8. Al arrancar el servidor se activan tareas de fondo y un escaneo programado. El arranque web debe separarse de los jobs para que una comprobación de salud no dispare trabajo ni modifique resultados.

### Presentación engañosa de los resultados

1. Las tarjetas muestran `Volatility_Percent` con una flecha ascendente como si fuera rendimiento. Ese campo se calcula como ATR/precio y normalmente es positivo; no representa que la acción subió.
2. La tarjeta muestra `AI_Confidence`, que pertenece al learner histórico, mientras el modelo produce `ML_Score` y `ML_Confidence`. Son conceptos diferentes y hoy se presentan como si fueran una sola confianza.
3. El learner entrega 50 % sin historial suficiente, por lo que todas las tarjetas parecen tener una confianza real que todavía no existe.
4. `Score_Fund` siempre vale cero, aunque la interfaz presenta un bloque de análisis fundamental sobre 40 puntos.
5. `Score_Tech` se construye con `min(RSI, 40)` y no con la contribución técnica usada para calcular el score total.
6. La etiqueta “Sugerencia de entrada IA” aparece como texto por defecto aunque no haya una señal validada.
7. El monitor de TSLA contiene reglas especiales incrustadas en la interfaz en vez de usar el mismo contrato de señal que los demás activos.

### Datos y escáner

1. El motor usa endpoints no documentados de Yahoo Finance. Pueden cambiar, bloquear solicitudes o limitar el tráfico sin contrato de servicio.
2. Las listas de S&P 500 y NASDAQ-100 se extraen de Wikipedia; un cambio en sus tablas puede dejar la lista vacía.
3. El escaneo abre hasta 40 workers desde la interfaz y `_bulk_download_history` fija otros 20. No hay un límite único, rate limiting ni backoff coordinado.
4. `except: pass` dentro del procesamiento oculta fallos por ticker y puede producir un escaneo “correcto” con datos incompletos.
5. La cancelación detiene el consumo de futures, pero las solicitudes que ya están ejecutándose pueden continuar.
6. Los horarios de mercado usan horas locales fijas. Deben calcularse con `America/New_York`, calendario bursátil y horario de verano.
7. Falta registrar proveedor, instante de consulta, moneda, zona horaria, ajuste por splits/dividendos y edad de cada precio.
8. La caché se guarda con pickle. Debe tratarse como interna y nunca cargarse desde una ubicación modificable por terceros.
9. El entorno efectivo no pudo importar `lxml` durante `pandas.read_html`, aunque aparece en el archivo de requisitos del visor. Como resultado, las listas S&P 500 y NASDAQ-100 quedaron vacías.
10. Los dos archivos de símbolos de Nasdaq Trader respondieron HTTP 406. Al fallar las cuatro fuentes del universo, el escáner continuó con solo once símbolos especiales y produjo diez resultados, dando apariencia de éxito parcial.
11. Las dependencias están divididas entre `requirements.txt` raíz y `tools/NOTIFICADOR_BOT/requirements.txt`; ejecutar solo la instalación principal no garantiza el motor completo.

### Machine Learning actual

El modelo no debe usarse todavía para decidir una compra real.

1. El artefacto `stock_ml_model.joblib` declara 4,001 muestras y fecha de entrenamiento del 5 de septiembre de 2026. La base `learner.db` presente contiene solo diez registros, todos del 8 de septiembre, pendientes y sin verificar. No se puede reconstruir el entrenamiento desde los datos actuales.
2. La precisión media de validación guardada es 24.35 %, recall 55.25 % y F1 33.24 %. La tasa positiva es 20.94 %. La mejora de precisión es pequeña y no demuestra rentabilidad.
3. El AUC 74.78 % y la `full_precision` 33.69 % se calculan sobre todo el conjunto usado para entrenar. No son métricas fuera de muestra.
4. `TimeSeriesSplit` separa filas ordenadas, pero puede dividir acciones del mismo día entre train y validación. Eso filtra información del mismo régimen de mercado.
5. No existe un `gap` equivalente al horizonte de la etiqueta. Una observación cercana al corte puede utilizar un resultado que se solapa con validación.
6. La etiqueta mezcla `outcome == "WIN"` con una ganancia de un día mayor o igual a 1.5 %, mientras el learner usa `good_mild`, `good_strong`, `neutral`, `bad_mild` y `bad_severe`.
7. Un horizonte de un día no coincide necesariamente con “invertir”; debe definirse si el producto busca swing de 5/20 sesiones o una cartera de varios meses.
8. `StandardScaler` no aporta valor al `GradientBoostingClassifier` basado en árboles.
9. La confianza `MUY ALTA/ALTA/MEDIA/BAJA` usa umbrales directos de `predict_proba`, pero la probabilidad no está calibrada.
10. El supuesto desglose por ticker multiplica el valor escalado por la importancia global. Eso no es una explicación local válida del modelo.
11. La volatilidad concentra aproximadamente 43 % de la importancia guardada; varios indicadores tienen importancia cero. Se debe revisar estabilidad y redundancia.
12. El score heurístico entra como feature junto con los indicadores que forman ese mismo score. Debe compararse con un modelo sin score para evitar duplicar la misma señal.
13. No hay comparación contra comprar SPY, contra una selección aleatoria ni contra una estrategia simple.
14. No se incluyen comisiones, spread, deslizamiento, liquidez, impuestos ni rotación en la evaluación.
15. El feedback manual puede modificar pesos adaptativos con una sola opinión; debe guardarse como etiqueta separada y no alterar producción inmediatamente.
16. El artefacto cargado contiene un `GradientBoostingClassifier` directo, mientras `predict_score()` espera `self.model.named_steps['gbm']` y `['scaler']`. La inferencia genera `'GradientBoostingClassifier' object has no attribute 'named_steps'` y vuelve silenciosamente al score heurístico.
17. `/api/ml/status` marca `trained: true` porque el archivo se pudo deserializar, aunque no es compatible ni puede completar una predicción. “Cargado” y “listo para inferencia” deben ser estados diferentes.

## Producto que se debe construir

La pantalla debe responder cinco preguntas con datos rastreables:

1. ¿Qué activos cumplen filtros mínimos de liquidez y calidad de datos?
2. ¿Qué probabilidad estimada tienen de superar a su benchmark en un horizonte definido?
3. ¿Cuál es el riesgo esperado, el peor retroceso histórico comparable y el tamaño prudente de posición?
4. ¿Por qué entraron en la lista y qué invalidaría la señal?
5. ¿Cómo habría funcionado la misma regla fuera de muestra, después de costos?

La interfaz debe clasificar resultados como `Candidato`, `Vigilar`, `Sin ventaja demostrada` o `Datos insuficientes`. “Comprar” solo debe aparecer en simulación cuando exista un modelo aprobado y una regla de cartera completa.

## Arquitectura propuesta

```text
Proveedor de mercado
        │
        ▼
Ingesta y validación ──► almacén OHLCV/fundamentales versionado
        │
        ▼
Features con fecha de disponibilidad
        │
        ├──► modelo heurístico base
        ├──► modelo ML candidato
        └──► control de riesgo
                 │
                 ▼
        validación walk-forward
                 │
                 ▼
       ranking + construcción de cartera
                 │
        ┌────────┴────────┐
        ▼                 ▼
   interfaz web       paper trading
```

Separar el código en módulos explícitos:

| Módulo | Responsabilidad |
| --- | --- |
| `market_data` | Proveedores, símbolos, OHLCV, fundamentales, calendario y caché. |
| `features` | Indicadores calculados sin mirar datos futuros. |
| `labels` | Retorno relativo y riesgo para horizontes definidos. |
| `models` | Entrenamiento, calibración, inferencia y manifiestos. |
| `evaluation` | Walk-forward, benchmarks, costos y reportes. |
| `portfolio` | Límites, tamaño de posición, correlación y rebalanceo. |
| `jobs` | Escaneos con ID, progreso, cancelación y errores por símbolo. |
| `api` | Esquemas estables y validación de entrada/salida. |
| `ui` | Presentación, estados vacíos, errores y fecha de los datos. |

## Plan de implementación

### Fase 0 — Recuperar `/bolsa`

Prioridad: bloqueo crítico.

1. Desactivar la llamada actual a `liquidGL({ target: '.glass-panel' })` en Bolsa.
2. Mantener `.glass-panel` visible con CSS como implementación base.
3. Si LiquidGL se conserva más adelante, aplicarlo solo a uno o dos elementos decorativos y envolver su inicialización en una restauración garantizada: ante timeout, excepción, textura nula o contexto perdido, restablecer opacidad, fondo, filtros y eventos.
4. El efecto nunca debe cambiar `pointer-events` del contenido interactivo.
5. Eliminar el segundo bloque duplicado de monitor, calculadora y detalles; conservar IDs únicos.
6. Retirar la pestaña de precios comerciales o implementar su API como producto separado. No pertenece al escáner bursátil.
7. Colocar el detector de errores antes de `app.js`, capturar `unhandledrejection` y mostrar un estado legible dentro del contenido.
8. Añadir un timeout a la carga inicial: si `/api/scan/results` no responde, mostrar “Servidor disponible, motor de Bolsa no disponible” con botón de reintento.
9. Probar sin Three.js, sin Lucide, sin WebGL y sin Internet externa; tablas, botones y mensajes deben seguir visibles.

Criterio de aceptación: al abrir `/bolsa`, el encabezado y los controles aparecen en menos de dos segundos; ningún panel visible tiene opacidad cero; todos los IDs son únicos; la consola no contiene errores; el usuario ve resultados o un estado vacío explicativo.

### Fase 1 — Arranque y diagnóstico confiables

1. Ejecutar Flask sin debug para uso habitual.
2. Incorporar un script de arranque que espere `/api/bolsa/health` antes de abrir la URL y muestre el error si el puerto no escucha.
3. Definir claramente si la URL `100.75.65.112` depende de Tailscale u otra interfaz. Registrar la IP activa al arrancar en lugar de fijarla en documentación.
4. Evitar procesos duplicados en el puerto 5050 y terminar el servidor de forma ordenada.
5. Ampliar health con versión, commit/build, estado de base, edad del último precio, edad del último escaneo, proveedor y estado del modelo.
6. Añadir `/api/bolsa/readiness`: solo `200` cuando API, base y UI mínima puedan servir tráfico.
7. Registrar errores por etapa y ticker con un ID de escaneo; no ocultarlos con `except: pass`.
8. Separar `serve`, `worker` y `scheduler` en comandos distintos. Abrir la interfaz o ejecutar health no debe iniciar un escaneo automáticamente.

Criterio de aceptación: un arranque limpio vuelve accesible `/bolsa`; un fallo de puerto, importación o proveedor se identifica desde una sola respuesta de diagnóstico.

### Fase 2 — Contrato de interfaz y API

1. Dividir `app.js` en `api-client.js`, `scan-view.js`, `portfolio-view.js`, `model-view.js` y `risk-view.js`.
2. Usar un contrato de resultado con nombres consistentes y unidades explícitas:

```json
{
  "symbol": "AAPL",
  "as_of": "2026-09-08T20:00:00Z",
  "currency": "USD",
  "price": 0,
  "daily_return_pct": 0,
  "atr_pct": 0,
  "signal_horizon_sessions": 20,
  "probability_outperform": null,
  "expected_excess_return_pct": null,
  "risk_band": "unknown",
  "decision": "insufficient_data",
  "model_version": null
}
```

3. Validar `source`, `max_workers`, límites, tickers, cantidades, precios y porcentajes en Flask.
4. Limitar workers en backend; la interfaz no decide un valor peligroso.
5. Crear trabajos con `scan_id`; `/start` devuelve el ID y status/results lo reciben.
6. Proteger `SCAN_STATE` completo con lock o almacenar trabajos en una tabla; no compartir listas mutables sin sincronización.
7. Devolver errores parciales y cobertura: solicitados, descargados, válidos, descartados y fallidos.
8. Escapar contenido dinámico. Evitar insertar ticker, notas o URLs no confiables mediante `innerHTML`.
9. Marcar un job como `partial` o `failed` si no se pudo construir el universo solicitado; diez tickers especiales no equivalen a un escaneo correcto de S&P 500 + NASDAQ-100.

### Fase 3 — Datos reproducibles

1. Crear una interfaz de proveedor con al menos un proveedor principal documentado y Yahoo como fallback marcado.
2. Guardar datos crudos inmutables y una tabla normalizada con `symbol`, `timestamp`, `open`, `high`, `low`, `close`, `adjusted_close`, `volume`, `currency`, `provider` y `ingested_at`.
3. Ajustar correctamente splits y dividendos. Las features deben usar una serie consistente.
4. Versionar el universo de símbolos por fecha para evitar sesgo de supervivencia en backtests.
5. Sustituir horas fijas por un calendario de mercado con `America/New_York`.
6. Aplicar retry exponencial con jitter, timeout, límite por proveedor y circuit breaker.
7. Guardar checks de calidad: huecos, duplicados, precios no positivos, volumen anómalo y antigüedad.
8. No generar señal cuando los datos estén incompletos o fuera de vigencia.
9. Unificar dependencias en un archivo bloqueado o grupos instalables (`app`, `bolsa`, `dev`) y comprobar al arrancar que `lxml`, scikit-learn y joblib tienen versiones compatibles.
10. Añadir fuentes alternativas del universo y conservar la última lista válida con fecha. Un HTTP 406 o un cambio de HTML debe degradar el servicio de forma visible, no convertirlo silenciosamente en otro universo.

### Fase 4 — Definir el problema de ML correctamente

Construir primero un modelo de ranking para swing trading; es más coherente con el escáner diario que predecir el precio exacto.

Objetivo principal propuesto:

- Universo: acciones líquidas de S&P 500 y NASDAQ-100, sin ETF apalancado.
- Horizonte inicial: 20 sesiones; añadir 5 sesiones como salida secundaria.
- Etiqueta: retorno del activo menos retorno de SPY durante el mismo horizonte, neto de un supuesto de costos.
- Salida: probabilidad calibrada de superar SPY y retorno excedente estimado.
- Selección: ranking diario y top K, sujeto a riesgo, sector, liquidez y correlación.

Crear tres baselines obligatorios:

1. SPY buy-and-hold.
2. Selección aleatoria con el mismo número de activos y rebalanceo.
3. Regla heurística actual sin ML.

El modelo nuevo se aprueba solo si supera los tres fuera de muestra de forma estable.

### Fase 5 — Modelo recomendado

La opción principal es desarrollar el pipeline propio sobre los datos del proyecto y usar LightGBM como modelo tabular. LightGBM admite clasificación y ranking, es eficiente y permite empezar sin infraestructura de deep learning. Su repositorio oficial es [lightgbm-org/LightGBM](https://github.com/lightgbm-org/LightGBM).

Ruta de modelos:

1. Regresión logística como baseline interpretable.
2. Modelo actual de Gradient Boosting corregido.
3. LightGBM classifier y `LGBMRanker` agrupado por fecha de decisión.
4. Ensemble únicamente si mejora todas las ventanas fuera de muestra y no solo el promedio.

No incorporar una red neuronal o un LLM para producir señales hasta tener varios años de datos limpios y baselines estables. Más complejidad no corrige etiquetas pobres ni fuga temporal.

Features iniciales:

- Retornos 1/5/20/60 sesiones y momentum relativo a SPY.
- Volatilidad realizada, ATR porcentual y downside volatility.
- Distancia a medias móviles en porcentaje, no en dólares.
- RSI, MACD normalizado y anchura/posición de Bollinger.
- Volumen relativo, liquidez y spread cuando esté disponible.
- Beta, correlación con SPY y régimen de mercado.
- Sector y fuerza relativa sectorial.
- Fundamentales solo con su fecha real de publicación para evitar usar información futura.

Eliminar o evaluar mediante ablación:

- El score heurístico como feature.
- Nivel absoluto de precio.
- Features con importancia cero persistente.
- Valores fundamentales simulados o rellenados como si fueran reales.

### Fase 6 — Validación sin fuga de información

1. Dividir por fecha completa; todos los activos de una fecha quedan en el mismo fold.
2. Usar walk-forward con ventana de entrenamiento, validación y prueba final bloqueada.
3. Aplicar purga y embargo de al menos el horizonte de la etiqueta alrededor de cada corte.
4. Ajustar hiperparámetros solo en train/validación. La prueba final se usa una vez por versión.
5. Calibrar probabilidades con datos separados. Scikit-learn explica que el calibrador debe ajustarse con datos independientes; usar curva de calibración, Brier y log loss, además de AUC ([documentación oficial](https://github.com/scikit-learn/scikit-learn/blob/main/doc/modules/calibration.rst)).
6. Evaluar por régimen, año, sector, capitalización y decil de liquidez.
7. Ejecutar pruebas de ablación para confirmar qué feature añade valor.
8. Medir estabilidad de importancia y drift entre entrenamiento y producción.

Métricas mínimas:

| Tipo | Métricas |
| --- | --- |
| Ranking | Precision@K, Recall@K, NDCG@K, Rank IC. |
| Probabilidad | ROC-AUC fuera de muestra, PR-AUC, Brier, log loss y calibración. |
| Retorno | Retorno excedente, Sharpe, Sortino, drawdown máximo y hit rate. |
| Operación | Rotación, costos, exposición, concentración y capacidad por liquidez. |
| Estabilidad | Resultado por ventana, régimen y sector; no solo promedio global. |

### Fase 7 — Trazabilidad del modelo

Cada artefacto debe tener un manifiesto junto al archivo:

```json
{
  "model_version": "bolsa-lgbm-001",
  "trained_at": "ISO-8601",
  "code_revision": "hash",
  "dataset_hash": "sha256",
  "data_start": "YYYY-MM-DD",
  "data_end": "YYYY-MM-DD",
  "features_version": "v1",
  "label_version": "excess_spy_20d_v1",
  "rows": 0,
  "symbols": 0,
  "metrics_test": {},
  "approved_for": "shadow"
}
```

Al cargar un modelo, verificar feature names, versiones, hash y compatibilidad. Si la base no puede explicar el artefacto, mostrarlo como `modelo no verificable` y usar el baseline.

Ejecutar además una inferencia canaria al iniciar: cargar el artefacto, validar que sea el tipo de pipeline esperado y predecir una fila con las 18 features. Solo después de pasar esa prueba `/api/ml/status` puede declarar `ready: true`. Un artefacto antiguo o incompatible se mueve a cuarentena y nunca se etiqueta como IA activa.

### Fase 8 — Explicaciones honestas

1. Sustituir `scaled_value × feature_importance` por SHAP para árboles o por una explicación global claramente etiquetada.
2. Mostrar probabilidad calibrada, horizonte, intervalo/incertidumbre, versión y fecha del modelo.
3. Separar visualmente:
   - score heurístico;
   - probabilidad del modelo;
   - evidencia histórica del ticker;
   - decisión final con restricciones de riesgo.
4. No convertir automáticamente una probabilidad en certeza.
5. Añadir motivo de exclusión: datos viejos, baja liquidez, alta correlación, riesgo excesivo o modelo fuera de dominio.

### Fase 9 — Backtesting y cartera

Usar ideas de [Microsoft Qlib](https://github.com/microsoft/qlib) para organizar datasets, experimentos, señales y backtests. Qlib ofrece un flujo cuantitativo completo y ejemplos con LightGBM; debe tomarse como referencia o módulo de investigación, no copiarse entero dentro de Flask.

Para optimización y riesgo de cartera, evaluar [skfolio](https://github.com/skfolio/skfolio), compatible con la API de scikit-learn y con validación walk-forward, riesgo, costos y restricciones. Es una mejor pieza para cartera que inventar un optimizador desde cero.

Reglas del backtest:

1. Decisión con datos conocidos al cierre de `t`; ejecución como mínimo en `t+1`.
2. Incluir spread, deslizamiento, costos y límite por volumen.
3. Comparar contra SPY y cartera equiponderada.
4. Limitar peso por activo y sector; prohibir apalancados en la estrategia base.
5. Modelar activos deslistados y composición histórica del universo cuando los datos lo permitan.
6. Guardar cada corrida con configuración, dataset, modelo y resultados.
7. Rechazar una estrategia que dependa de una sola ventana o pocos tickers.

### Fase 10 — Paper trading

Solo después de aprobar backtesting:

1. Ejecutar el modelo en modo sombra durante al menos varias ventanas completas sin enviar órdenes.
2. Comparar predicciones, precios observados, rechazos y drift diariamente.
3. Integrar paper trading mediante el SDK oficial [alpacahq/alpaca-py](https://github.com/alpacahq/alpaca-py), manteniendo `paper=True` y credenciales separadas.
4. Crear un adaptador de broker; ninguna parte del modelo debe importar directamente el SDK.
5. Aplicar límites de pérdida diaria, exposición, posición, órdenes duplicadas y datos viejos.
6. Reconciliar órdenes, fills y posiciones desde el broker; no asumir que una orden fue ejecutada.
7. Añadir un interruptor de emergencia y auditoría completa.

No habilitar operaciones reales como consecuencia automática de una predicción. Una futura fase real deberá requerir configuración separada, revisión de límites y confirmación explícita por orden o política autorizada.

### Fase 11 — Evaluar repositorios externos

| Proyecto | Uso recomendado | Decisión |
| --- | --- | --- |
| [LightGBM](https://github.com/lightgbm-org/LightGBM) | Clasificación/ranking tabular eficiente. | Adoptar como candidato principal. |
| [Microsoft Qlib](https://github.com/microsoft/qlib) | Flujo de investigación, datasets, experimentos y backtesting. | Reutilizar patrones e integrar solo lo necesario. |
| [skfolio](https://github.com/skfolio/skfolio) | Construcción, validación y riesgo de cartera. | Evaluar tras obtener señales confiables. |
| [PyPortfolioOpt](https://github.com/robertmartin8/PyPortfolioOpt) | Alternativa modular para optimización clásica, Black-Litterman y HRP. | Comparar con skfolio mediante una prueba pequeña. |
| [VectorBT](https://github.com/polakowo/vectorbt) | Backtesting vectorizado y exploración rápida. | Prototipo opcional; revisar su licencia antes de distribuir un producto. |
| [FinRL](https://github.com/AI4Finance-Foundation/FinRL) | Investigación de reinforcement learning. | Posponer; el propio repositorio lo orienta a educación/investigación y remite su evolución productiva a FinRL-X. |
| [Darts](https://github.com/unit8co/darts) | Forecast probabilístico de series temporales. | No es prioridad para el ranking inicial; experimentar después del baseline. |
| [alpaca-py](https://github.com/alpacahq/alpaca-py) | Datos/broker y paper trading. | Usar solo en la fase de simulación. |

No importar modelos preentrenados de repositorios desconocidos ni cargar archivos pickle/joblib externos. Cualquier dependencia debe fijar versión, licencia, hash y pruebas de integración.

## Pruebas necesarias

### UI

- Smoke test de `/bolsa` con JavaScript habilitado y deshabilitado.
- Verificar que encabezado, inicio de escaneo y estado vacío son visibles.
- Afirmar IDs únicos.
- Probar WebGL ausente, contexto perdido y timeout de LiquidGL.
- Probar CDN bloqueados.
- Probar escritorio y móvil.
- Prueba visual que falle si el área principal queda uniforme o si todos los paneles tienen opacidad cero.

### API y jobs

- Inicio, conflicto, cancelación, fallo parcial y recuperación de escaneo.
- Validación de workers, source y tickers.
- Dos clientes consultando el mismo scan ID.
- Reinicio del proceso durante un trabajo.
- Datos viejos, proveedor caído y caché corrupta.

### Datos y features

- Splits/dividendos y zonas horarias.
- Features calculadas solo con información disponible en `as_of`.
- Repetibilidad entre entrenamiento e inferencia.
- Universo histórico sin introducir miembros futuros.

### ML

- Separación por fechas completas con purga/embargo.
- Dataset y artefacto con hashes reproducibles.
- Comparación con los tres baselines.
- Métricas fuera de muestra y por régimen.
- Calibración e incertidumbre.
- Rechazo de modelo incompatible, viejo o sin manifiesto.

### Paper trading

- Órdenes duplicadas, parciales, rechazadas y fuera de horario.
- Desconexión del stream y reconciliación posterior.
- Límites de exposición y pérdida.
- Confirmación de que ninguna configuración de prueba puede alcanzar una cuenta real.

## Orden de entrega

### Entrega A — Visor visible

- LiquidGL desactivado en los paneles funcionales.
- Duplicados eliminados.
- Estados de carga/error visibles.
- Arranque y readiness confiables.
- Smoke test visual aprobado.

### Entrega B — Escáner confiable

- Contratos API estables.
- Jobs identificables y cancelables.
- Datos con procedencia, tiempo y calidad.
- Campos de UI con significado y unidades correctas.

### Entrega C — ML verificable

- Dataset reproducible.
- Etiqueta relativa a SPY de 5/20 sesiones.
- Baselines, LightGBM y validación walk-forward purgada.
- Probabilidades calibradas y manifiesto de modelo.

### Entrega D — Decisiones de cartera

- Ranking con reglas de riesgo.
- Backtest neto de costos.
- Cartera con límites y comparación contra benchmark.
- Explicaciones y motivos de exclusión.

### Entrega E — Simulación operativa

- Modo sombra.
- Alpaca paper trading mediante adaptador.
- Reconciliación, auditoría y límites.
- Reporte de estabilidad antes de considerar una fase real.

## Criterio final de aceptación

`/bolsa` estará funcional cuando siempre muestre contenido o un error accionable; cada precio y señal indique fuente y fecha; el escaneo pueda iniciarse, cancelarse y auditarse; el modelo se pueda reproducir desde su dataset; las probabilidades estén calibradas; el resultado fuera de muestra supere baselines después de costos; la cartera aplique límites de riesgo; y cualquier operación se mantenga en paper trading hasta una decisión posterior explícita.

Un score alto por sí solo no cumple este criterio. La calidad se demuestra con trazabilidad, validación temporal, comparación contra benchmark y comportamiento observado en simulación.
