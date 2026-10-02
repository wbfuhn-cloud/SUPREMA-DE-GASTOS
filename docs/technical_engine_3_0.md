# Especificación del motor técnico y heurístico 3.0

Versión de reglas: `3.0.0`  
Implementación: `tools/NOTIFICADOR_BOT/technical_engine.py`  
Bibliotecas numéricas: pandas y NumPy.

## Datos de entrada

El motor consume OHLCV canónico. Si el proveedor entrega cierre ajustado, todas las fórmulas usan la serie ajustada y las columnas `Raw_*` permanecen disponibles para auditoría. Los valores ausentes se conservan como `None`/`NaN`; nunca se sustituyen por cero ni por el precio actual.

## Fórmulas

### RSI de Wilder

- Periodo: 14.
- Cambio: `delta_t = close_t - close_(t-1)`.
- Ganancia: `max(delta_t, 0)`.
- Pérdida: `max(-delta_t, 0)`.
- Suavizado RMA de Wilder: `ewm(alpha=1/14, adjust=False, min_periods=14)`.
- `RS = RMA(ganancia) / RMA(pérdida)`.
- `RSI = 100 - 100/(1+RS)`.
- Mínimo: 15 cierres.

### MACD

- EMA rápida: 12.
- EMA lenta: 26.
- Línea MACD: `EMA12 - EMA26`.
- Señal: EMA de 9 periodos de la línea MACD.
- Histograma: `MACD - señal`.
- Aceleración: `histograma_t - histograma_(t-1)`.
- Mínimo para el conjunto completo: 35 cierres.
- Semántica: MACD por encima de señal e histograma positivo significa impulso alcista; la pendiente del histograma indica aceleración, no dirección por sí sola.

### Bandas de Bollinger

- Ventana: 20.
- Centro: SMA20.
- Desviación estándar poblacional: `ddof=0`.
- Superior/inferior: `SMA20 ± 2σ`.
- Mínimo: 20 cierres.

### ATR de Wilder

- Periodo: 14.
- Rango verdadero: máximo de `high-low`, `|high-close_previo|`, `|low-close_previo|`.
- Suavizado: RMA de Wilder `ewm(alpha=1/14, adjust=False, min_periods=14)`.
- Mínimo: 15 velas.

### Medias y volumen

- SMA20, SMA50 y SMA200 requieren exactamente 20, 50 y 200 observaciones como mínimo.
- Volumen medio y ratio de volumen usan ventana 20.
- Un volumen medio inferior a 100,000 unidades produce abstención por iliquidez.

## Score normalizado

Cada horizonte tiene pesos versionados. Para señales disponibles `s_i ∈ [-1,1]`:

```text
score_direccional = Σ(w_i × s_i × disponible_i) / Σ(w_i × disponible_i)
score_mostrado = 50 + 50 × score_direccional
```

La cobertura es el peso disponible dividido entre el peso total. Con cobertura menor a 60% el estado es `SIN SEÑAL`. La explicación incluye un baseline de 50 y cada contribución normalizada; su suma reproduce el score mostrado con tolerancia de 0.01.

## Horizontes y estados

- Corto: 1–3 sesiones.
- Swing: 5–20 sesiones; es el estado principal.
- Tendencia: 20–60 sesiones.

Estados posibles:

- `COMPRAR`: score direccional ≥ 0.35.
- `MANTENER/ESPERAR`: -0.15 < score direccional < 0.35.
- `REDUCIR`: -0.50 < score direccional ≤ -0.15.
- `SALIR`: score direccional ≤ -0.50.
- `SIN SEÑAL`: cobertura insuficiente o restricción obligatoria.

## Regímenes y restricciones

- Regímenes explícitos: `uptrend`, `downtrend`, `lateral`, `jump`, `high_volatility` y `noise`.
- Una cotización vencida o con calidad menor a 0.95 obliga a abstenerse.
- La iliquidez obliga a abstenerse.
- Una acción corporativa se revela en las restricciones y exige revisión de la serie ajustada.
- Un ETF apalancado nunca recibe recomendación de compra de tendencia basada solo en análisis técnico clásico.
- La confianza del módulo de aprendizaje puede filtrar una notificación, pero no modifica la señal heurística.
