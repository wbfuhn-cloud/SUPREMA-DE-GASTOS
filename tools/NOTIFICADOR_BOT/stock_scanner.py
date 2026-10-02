"""
stock_scanner.py — Motor de escaneo bursátil optimizado.
- Llama directamente a la API v8 de Yahoo Finance (sin yfinance session bugs)
- Descarga masiva en paralelo
- Caché con pickle
- Score compuesto técnico + liquidez
"""
import pandas as pd
import numpy as np
import pickle
import requests
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO

from market_data import apply_adjusted_close, exchange_rate_contract, quote_from_history

try:
    from recommendation_learner import get_learner
except ImportError:
    get_learner = None

logger = logging.getLogger(__name__)

# ── Sesión HTTP con headers de navegador real (evita 401) ────────────────────
_SESSION = requests.Session()
_SESSION.headers.update({
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept':          'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer':         'https://finance.yahoo.com/',
    'Origin':          'https://finance.yahoo.com',
})

# ── Descargador directo a Yahoo v8 (sin crumb) ───────────────────────────────
_YF_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
_YF_QUOTE = "https://query1.finance.yahoo.com/v7/finance/quote"

def _fetch_history_raw(ticker: str, period='1y', interval='1d') -> pd.DataFrame | None:
    """Descarga OHLCV de Yahoo v8 directamente. No usa yfinance."""
    _period_map = {'5d': '5d', '1mo': '1mo', '3mo': '3mo', '6mo': '6mo',
                   '1y': '1y', '2y': '2y', '5y': '5y', 'max': 'max'}
    try:
        url = _YF_CHART.format(ticker=ticker)
        params = {'range': _period_map.get(period, '1y'), 'interval': interval,
                  'includePrePost': 'false', 'events': 'div,split'}
        r = _SESSION.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        result = data.get('chart', {}).get('result', [])
        if not result:
            return None
        res = result[0]
        timestamps = res.get('timestamp', [])
        ohlcv = res.get('indicators', {}).get('quote', [{}])[0]
        if not timestamps or not ohlcv:
            return None
        df = pd.DataFrame({
            'Open':   ohlcv.get('open', []),
            'High':   ohlcv.get('high', []),
            'Low':    ohlcv.get('low', []),
            'Close':  ohlcv.get('close', []),
            'Volume': ohlcv.get('volume', []),
        }, index=pd.to_datetime(timestamps, unit='s', utc=True))
        adjusted_values = (
            res.get('indicators', {}).get('adjclose', [{}])[0].get('adjclose', [])
        )
        events = res.get('events', {}) or {}
        df.attrs['corporate_action_count'] = sum(len(items) for items in events.values() if isinstance(items, dict))
        if adjusted_values and len(adjusted_values) == len(df):
            df = apply_adjusted_close(df, adjusted_values)
        # Mantener UTC con zona horaria: eliminarla impedía medir frescura y
        # reconciliar una misma cotización entre módulos.
        df.index = df.index.tz_convert('UTC')  # type: ignore
        df = df.dropna(subset=['Close'])
        return df if len(df) > 0 else None
    except Exception as e:
        logger.debug(f"_fetch_history_raw({ticker}): {e}")
        return None

def _fetch_quote_batch(tickers: list) -> dict:
    """Descarga precio/marketCap de múltiples tickers de una sola llamada."""
    try:
        params = {'symbols': ','.join(tickers[:50]),
                  'fields': 'regularMarketPrice,marketCap,beta,trailingPE,sector,industry'}
        r = _SESSION.get(_YF_QUOTE, params=params, timeout=10)
        if r.status_code != 200: return {}
        results = r.json().get('quoteResponse', {}).get('result', [])
        return {q['symbol']: q for q in results if 'symbol' in q}
    except Exception as e:
        logger.debug(f"_fetch_quote_batch: {e}")
        return {}

# ── Tipo de cambio USD/MXN ────────────────────────────────────────────────────
def _get_usd_mxn() -> float:
    """Obtiene tipo de cambio USD/MXN directamente de Yahoo Finance."""
    try:
        url = _YF_CHART.format(ticker='USDMXN=X')
        params = {'range': '5d', 'interval': '1d', 'includePrePost': 'false'}
        r = _SESSION.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            result = data.get('chart', {}).get('result', [])
            if result:
                ohlcv = result[0].get('indicators', {}).get('quote', [{}])[0]
                closes = ohlcv.get('close', [])
                valid = [c for c in closes if c is not None]
                if valid:
                    return float(valid[-1])
    except Exception as e:
        logger.debug(f"_get_vix_via_chart error: {e}")
    return 20.5  # fallback actualizado (2026)

# ── Constantes ────────────────────────────────────────────────────────────────
SPECIAL_TICKERS = ['TZA', 'TNA', 'XLF', 'SOXS', 'SQQQ', 'SPXY', 'TEM', 'TSLA', 'DJT', 'PHUN', 'RUM']
TRUMP_TICKERS = ['DJT', 'PHUN', 'RUM']
VOLATILE_TICKERS = ['TSLA', 'MSTR', 'NVDA', 'COIN', 'PLTR', 'TQQQ', 'SOXL', 'TNA', 'FAS', 'SQQQ', 'SOXS', 'TZA', 'FAZ']
LEVERAGED_ETFS = frozenset([
    # 3x Bull
    'SOXL', 'TQQQ', 'FAS', 'TNA', 'UPRO', 'SPXL', 'FNGU', 'LABU', 'NUGT',
    # 3x Bear (Inverse)
    'SOXS', 'SQQQ', 'FAZ', 'TZA', 'SPXU', 'FNGD', 'LABD', 'DUST',
    # 2x Bull
    'SSO', 'QLD', 'UDOW', 'DDM',
    # 2x Bear
    'SDS', 'QID', 'DXD',
])
CACHE_DIR       = Path("cache")
CACHE_INFO_DIR  = CACHE_DIR / "info"
CACHE_HIST_DIR  = CACHE_DIR / "history"
TICKER_CACHE    = CACHE_DIR / "ticker_lists.pkl"

# ── Inicialización de caché ───────────────────────────────────────────────────
def init_cache():
    CACHE_INFO_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_HIST_DIR.mkdir(parents=True, exist_ok=True)

# ── Caché genérico ────────────────────────────────────────────────────────────
def _cache_path(ticker: str, kind: str) -> Path:
    return (CACHE_INFO_DIR if kind == 'info' else CACHE_HIST_DIR) / f"{ticker}.pkl"

def save_to_cache(ticker, data, kind):
    try:
        init_cache()
        with open(_cache_path(ticker, kind), 'wb') as f:
            pickle.dump({'ts': datetime.now(), 'data': data}, f, protocol=4)
    except Exception as e:
        logger.debug(f"save_to_cache({ticker}): {e}")

def load_from_cache(ticker, kind):
    try:
        p = _cache_path(ticker, kind)
        if not p.exists(): return None
        with open(p, 'rb') as f:
            return pickle.load(f)['data']
    except Exception as e:
        logger.debug(f"load_from_cache({ticker}): {e}")
        return None

def is_cache_valid(ticker, kind, max_hours=6):
    try:
        p = _cache_path(ticker, kind)
        if not p.exists(): return False
        with open(p, 'rb') as f:
            ts = pickle.load(f)['ts']
        return (datetime.now() - ts) < timedelta(hours=max_hours)
    except Exception as e:
        logger.debug(f"is_cache_valid({ticker}): {e}")
        return False

def get_cache_stats():
    try:
        init_cache()
        files = list(CACHE_INFO_DIR.glob("*.pkl")) + list(CACHE_HIST_DIR.glob("*.pkl"))
        size  = sum(f.stat().st_size for f in files)
        return {
            'total_tickers': len(list(CACHE_INFO_DIR.glob("*.pkl"))),
            'total_files':   len(files),
            'total_size_mb': round(size / 1_048_576, 2)
        }
    except Exception as e:
        logger.debug(f"get_cache_stats error: {e}")
        return {'total_tickers': 0, 'total_files': 0, 'total_size_mb': 0}

def clear_cache(older_than_hours=None):
    deleted = 0
    try:
        init_cache()
        for d in [CACHE_INFO_DIR, CACHE_HIST_DIR]:
            for f in d.glob("*.pkl"):
                try:
                    if older_than_hours is None:
                        f.unlink(); deleted += 1
                    else:
                        with open(f, 'rb') as fp:
                            ts = pickle.load(fp)['ts']
                        if (datetime.now() - ts) > timedelta(hours=older_than_hours):
                            f.unlink(); deleted += 1
                except Exception:
                    f.unlink(); deleted += 1
    except Exception as e:
        logger.debug(f"clear_cache error: {e}")
    return deleted

# ── Caché de listas de tickers ────────────────────────────────────────────────
def _load_ticker_cache():
    try:
        if TICKER_CACHE.exists():
            with open(TICKER_CACHE, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        logger.debug(f"_load_ticker_cache error: {e}")
    return {}

def _save_ticker_cache(data):
    try:
        init_cache()
        with open(TICKER_CACHE, 'wb') as f:
            pickle.dump(data, f, protocol=4)
    except Exception as e:
        logger.debug(f"_save_ticker_cache error: {e}")

def get_cached_ticker_list(name, fn, max_hours=24):
    cache = _load_ticker_cache()
    entry = cache.get(name)
    if entry:
        ts = entry.get('ts', entry.get('timestamp'))
        if ts and (datetime.now() - ts) < timedelta(hours=max_hours):
            print(f"[CACHE] {name}: {len(entry['tickers'])} tickers")
            return entry['tickers']
    print(f"[DOWNLOAD] Descargando {name}...")
    tickers = fn()
    if tickers:
        cache[name] = {'tickers': tickers, 'ts': datetime.now()}
        _save_ticker_cache(cache)
        print(f"[OK] {name}: {len(tickers)} tickers guardados")
    return tickers

def get_ticker_cache_stats():
    try:
        cache = _load_ticker_cache()
        sources = []
        total = 0
        for k, v in cache.items():
            ts = v.get('ts', v.get('timestamp', datetime.now()))
            age = (datetime.now() - ts).total_seconds() / 3600
            sources.append({'source': k, 'count': len(v['tickers']), 'age_hours': round(age, 1)})
            total += len(v['tickers'])
        return {'cached_sources': len(sources), 'sources': sources, 'total_tickers': total}
    except: return {'cached_sources': 0, 'sources': [], 'total_tickers': 0}

def clear_ticker_cache():
    try:
        if TICKER_CACHE.exists(): TICKER_CACHE.unlink()
        return True
    except: return False

# ── Indicadores técnicos ─────────────────────────────────────────────────────
def calculate_rsi(close: pd.Series, periods=14) -> float:
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(periods).mean()
    loss  = (-delta.clip(upper=0)).rolling(periods).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = 100 - (100 / (1 + rs))
    v = rsi.iloc[-1]
    return float(v) if not pd.isna(v) else 50.0

def calculate_macd(close: pd.Series, fast=12, slow=26, sig=9):
    if len(close) < slow: return 0.0, 0.0, 0.0
    e1 = close.ewm(span=fast, adjust=False).mean()
    e2 = close.ewm(span=slow, adjust=False).mean()
    macd = e1 - e2
    signal = macd.ewm(span=sig, adjust=False).mean()
    hist = macd - signal
    def safe(s): v = s.iloc[-1]; return float(v) if not pd.isna(v) else 0.0
    return safe(macd), safe(signal), safe(hist)

def calculate_bollinger_bands(close: pd.Series, window=20, std=2):
    rm  = close.rolling(window).mean()
    rs  = close.rolling(window).std()
    def safe(s): v = s.iloc[-1]; return float(v) if not pd.isna(v) else 0.0
    return safe(rm + rs*std), safe(rm), safe(rm - rs*std)

def calculate_atr(df: pd.DataFrame, period=14) -> float:
    h, l, c = df['High'], df['Low'], df['Close']
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    v = tr.rolling(period).mean().iloc[-1]
    return float(v) if not pd.isna(v) else 0.0

def analyze_volume(df: pd.DataFrame, window=20):
    avg  = df['Volume'].rolling(window).mean().iloc[-1]
    curr = df['Volume'].iloc[-1]
    avg  = float(avg)  if not pd.isna(avg)  else 0.0
    curr = float(curr) if not pd.isna(curr) else 0.0
    ratio = curr / avg if avg > 0 else 0.0
    return avg, curr, ratio

# ── Score compuesto ───────────────────────────────────────────────────────────
def _score_label(score: float) -> str:
    if score >= 75: return "🟢 EXCELENTE"
    if score >= 55: return "🟡 BUENA"
    if score >= 35: return "🟠 MODERADA"
    return "🔴 EVITAR"

def calculate_composite_score(df: pd.DataFrame, info: dict) -> dict:
    close = df['Close']
    
    # Obtener pesos adaptativos o usar defaults si no está disponible el learner
    learner = get_learner() if get_learner else None
    weights = learner.get_adaptive_weights() if learner else {}
    
    # Helpers con valores por defecto
    def w(key, default=1.0): return weights.get(key, default)

    score = 0

    # RSI (0-20 pts) -> Modificado por pesos
    rsi = calculate_rsi(close)
    if   40 <= rsi <= 60: score += 20 * w('rsi_optimal', 1.0)
    elif 30 <= rsi <  40 or 60 < rsi <= 70: score += 10
    elif rsi < 30: score += 15 * w('rsi_extreme_low', 1.0)
    else: score += 3

    # Tendencia vs SMA50/SMA200 (0-30 pts)
    price  = float(close.iloc[-1])
    sma50  = float(close.rolling(50).mean().iloc[-1])  if len(close) >= 50  else price
    sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else price
    if price > sma50 > sma200: score += 30 * w('trend_sma', 1.0)
    elif price > sma50:        score += 18
    elif price > sma200:       score += 8

    # MACD (0-20 pts)
    macd, sig, hist = calculate_macd(close)
    if   macd > sig and hist > 0: score += 20 * w('macd_bullish', 1.0)
    elif macd > sig:              score += 10

    # Volumen (0-15 pts)
    avg_vol, _, vol_ratio = analyze_volume(df)
    if   avg_vol > 2_000_000: score += 15 * w('volume_high', 1.0)
    elif avg_vol > 500_000:   score += 8
    elif avg_vol > 100_000:   score += 3
    
    if vol_ratio > 1.5: score += 5 * w('volume_ratio', 1.0)

    # Market Cap (0-15 pts) — desde fast_info para no hacer llamada extra
    mkt_cap = info.get('marketCap', 0) or 0
    if   mkt_cap > 10e9: score += 15 * w('market_cap_large', 1.0)
    elif mkt_cap > 2e9:  score += 8
    elif mkt_cap > 300e6: score += 3
    
    # Bollinger Bands
    bb_u, bb_m, bb_l = calculate_bollinger_bands(close)
    if bb_l > 0 and price <= bb_l: score += 10 * w('bb_oversold', 1.0)
    if bb_u > 0 and price >= bb_u: score -= 15 * w('bb_overbought', 1.0) # Penalización adaptativa

    # Retornar total e indicadores activos
    total = min(max(score, 0), 100)
    
    active_ind = []
    if 30 <= rsi <= 55: active_ind.append("rsi_optimal")
    if price > sma50 > sma200: active_ind.append("trend_sma")
    if macd > sig and hist > 0: active_ind.append("macd_bullish")
    if avg_vol > 2_000_000: active_ind.append("volume_high")
    if bb_l > 0 and price <= bb_l: active_ind.append("bb_oversold")

    return {
        'score_total': total,
        'score_tecnico': min(rsi, 40),
        'score_fundamental': 0,
        'score_liquidez': min(int(avg_vol / 200_000), 20),
        'etiqueta': _score_label(total),
        'active_indicators': active_ind
    }

# ── Régimen de mercado (directo a Yahoo v8) ──────────────────────────────────
def get_market_regime() -> dict:
    try:
        spy_df = _fetch_history_raw('SPY', period='1y')
        vix_df = _fetch_history_raw('%5EVIX', period='3mo')  # ^VIX url-encoded

        if spy_df is None or spy_df.empty:
            raise ValueError("Sin datos de SPY")

        price  = float(spy_df['Close'].iloc[-1])
        sma200 = float(spy_df['Close'].rolling(200).mean().iloc[-1])
        vix    = float(vix_df['Close'].iloc[-1]) if (vix_df is not None and not vix_df.empty) else 20.0

        if price > sma200 and vix < 20:
            regime, mod = "ALCISTA", 1.0
        elif price > sma200:
            regime, mod = "NEUTRAL", 0.85
        else:
            regime, mod = "BAJISTA", 0.70

        return {
            'regime': regime,
            'spy_vs_sma200': round(((price / sma200) - 1) * 100, 2),
            'vix': round(vix, 2),
            'score_modifier': mod
        }
    except Exception as e:
        logger.warning(f"Regimen de mercado no disponible: {e}")
        return {'regime': 'DESCONOCIDO', 'spy_vs_sma200': 0, 'vix': 0, 'score_modifier': 1.0}

# ── Descarga masiva paralela (directo a Yahoo v8) ──────────────────────────
def _bulk_download_history(tickers: list, period='1y') -> dict:
    """Descarga paralela de históricos usando la API v8 directa."""
    result = {}
    def _dl(t):
        df = _fetch_history_raw(t, period=period)
        if df is not None and len(df) >= 50:
            return t, df
        return t, None

    with ThreadPoolExecutor(max_workers=20) as ex:
        for t, df in ex.map(_dl, tickers):
            if df is not None:
                result[t] = df
    return result

# ── Procesamiento de un ticker individual ─────────────────────────────────────
def process_single_ticker(ticker: str, use_cache=True, prefetched_history=None) -> dict | None:
    try:
        # Historia desde prefetch o caché o descarga directa
        if prefetched_history is not None:
            history = prefetched_history
        elif use_cache and is_cache_valid(ticker, 'history'):
            history = load_from_cache(ticker, 'history')
        else:
            history = _fetch_history_raw(ticker, period='1y')
            if history is not None:
                save_to_cache(ticker, history, 'history')

        if history is None or len(history) < 50:
            return None

        quote = quote_from_history(
            ticker,
            history,
            interval='1d',
            adjusted=bool(history.attrs.get('adjusted', False)),
        )
        close  = history['Close'].dropna()
        if len(close) < 50: return None

        price  = float(quote['price'])
        if price <= 0: return None

        # Info (marketCap, beta) via batch quote
        info = {}
        if use_cache and is_cache_valid(ticker, 'info'):
            info = load_from_cache(ticker, 'info') or {}

        if not info:
            quotes = _fetch_quote_batch([ticker])
            q = quotes.get(ticker, {})
            info = {
                'marketCap': q.get('marketCap'),
                'beta':      q.get('beta'),
                'sector':    q.get('sector', 'N/A'),
                'industry':  q.get('industry', 'N/A'),
            }
            save_to_cache(ticker, info, 'info')

        # Filtro de precio mínimo (evitar penny stocks)
        if price < 1.0 and ticker not in SPECIAL_TICKERS:
            return None

        # Calcular indicadores
        sma100 = float(close.rolling(100).mean().iloc[-1]) if len(close) >= 100 else price
        sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else price
        rsi    = calculate_rsi(close)
        macd, macd_sig, macd_hist = calculate_macd(close)
        bb_u, bb_m, bb_l = calculate_bollinger_bands(close)
        atr    = calculate_atr(history)
        avg_vol, curr_vol, vol_ratio = analyze_volume(history)
        vol_pct = (atr / price * 100) if price > 0 else 0

        # Score
        scores = calculate_composite_score(history, info)

        # Nota rápida
        note = ""
        if macd > macd_sig and macd_hist > 0 and price > sma100 > sma200:
            note = "🟢 Tendencia alcista confirmada"
        elif price <= bb_l and bb_l > 0:
            note = "💎 Zona de sobreventa (BB)"
        elif macd < macd_sig:
            note = "📉 MACD bajista"
        elif vol_ratio > 2.0:
            note = "📊 Volumen anormalmente alto"

        beta = info.get('beta')

        # Penalizar ETFs apalancados: su decaimiento estructural hace que
        # el analisis tecnico clasico NO sea aplicable (SOXS, SOXL, TQQQ, etc.)
        is_leveraged = ticker.upper() in LEVERAGED_ETFS
        if is_leveraged:
            scores['score_total'] = min(scores['score_total'], 45)  # tope maximo
            scores['etiqueta'] = 'ADVERTENCIA: Apalancado'
            warning = 'ALERTA: ETF apalancado - analisis tecnico NO es confiable'
            if not note:
                note = warning
            else:
                note = warning + ' | ' + note

        # Predicción de Machine Learning
        ml_score = None
        ml_conf = "NO DISPONIBLE"
        ml_breakdown = {}
        ml_source = "fallback"
        try:
            from ml_predictor import get_ml_predictor
            predictor = get_ml_predictor()
            prediction = predictor.predict_score({
                'score': scores['score_total'],
                'rsi': rsi,
                'macd': macd,
                'macd_signal': macd_sig,
                'macd_hist': macd_hist,
                'price_at_rec': price,
                'bb_upper': bb_u,
                'bb_lower': bb_l,
                'vol_ratio': vol_ratio,
                'volatility_pct': vol_pct / 100.0,
                'market_cap': info.get('marketCap', 0) or 0,
                'active_indicators': scores.get('active_indicators', [])
            })
            ml_score = prediction.get('ml_score', ml_score)
            ml_conf = prediction.get('confidence_level', ml_conf)
            ml_breakdown = prediction.get('feature_breakdown', {})
            ml_source = prediction.get('source', ml_source)
        except Exception as e:
            logger.debug(f"ML prediction error for {ticker}: {e}")

        return {
            'Ticker':           ticker,
            'Price':            round(price, 2),
            'Score':            scores['score_total'],
            'ML_Score':         ml_score,
            'ML_Confidence':    ml_conf,
            'ML_Breakdown':     ml_breakdown,
            'ML_Source':        ml_source,
            'Quote':            quote,
            'Data_Quality':     quote['quality_score'],
            'Data_Quality_Issues': quote['quality_issues'],
            'Signal_Eligible':  not quote['is_stale'] and quote['quality_score'] >= 0.95,
            'Is_Leveraged':     is_leveraged,
            'Viabilidad':       scores['etiqueta'],
            'Score_Tech':       scores['score_tecnico'],
            'Score_Fund':       scores['score_fundamental'],
            'Score_Liq':        scores['score_liquidez'],
            'RSI':              round(rsi, 2),
            'MA100':            round(sma100, 2),
            'MA200':            round(sma200, 2),
            'MACD':             round(macd, 2),
            'MACD_Signal':      round(macd_sig, 2),
            'MACD_Hist':        round(macd_hist, 2),
            'BB_Upper':         round(bb_u, 2),
            'BB_Lower':         round(bb_l, 2),
            'ATR':              round(atr, 2),
            'Volatility_Percent': round(vol_pct, 2),
            'Avg_Volume':       int(avg_vol),
            'Vol_Ratio':        round(vol_ratio, 2),
            'Beta':             round(float(beta), 2) if beta is not None else None,
            'Gross Margin':     None,
            'PE_Ratio':         None,
            'Debt_Equity':      None,
            'Rev_Growth':       None,
            'Profit_Margin':    None,
            'Current_Ratio':    None,
            'Sector':           info.get('sector', 'N/A'),
            'Industry':         info.get('industry', 'N/A'),
            'Market_Cap':       info.get('marketCap'),
            'Fundamentals_Available': info.get('marketCap') is not None or beta is not None,
            'Nota':             note,
            'AI_Confidence':    0,  # Se rellenará más adelante si se pide
            'AI_Notes':         [],
        }
    except Exception as e:
        logger.debug(f"process_single_ticker({ticker}): {e}")
        return None

# ── Fuentes de tickers ────────────────────────────────────────────────────────
def get_sp500_tickers():
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        r = _SESSION.get(url, timeout=10)
        r.raise_for_status()
        tables = pd.read_html(StringIO(r.text))
        return tables[0]['Symbol'].str.replace('.', '-', regex=False).tolist()
    except Exception as e:
        print(f"[ERROR] S&P 500: {e}"); return []

def get_nasdaq100_tickers():
    try:
        url = 'https://en.wikipedia.org/wiki/NASDAQ-100'
        r = _SESSION.get(url, timeout=10)
        r.raise_for_status()
        tables = pd.read_html(StringIO(r.text))
        for t in tables:
            if isinstance(t.columns, pd.MultiIndex):
                t.columns = t.columns.get_level_values(-1)
            cols = [str(c).lower() for c in t.columns]
            if 'ticker' in cols or 'symbol' in cols:
                col = t.columns[cols.index('ticker') if 'ticker' in cols else cols.index('symbol')]
                tickers = t[col].astype(str).str.replace('.', '-', regex=False).tolist()
                return [tk for tk in tickers if tk and len(tk) <= 6 and tk.replace('-','').isalpha()]
        return []
    except Exception as e:
        print(f"[ERROR] NASDAQ-100: {e}"); return []

def get_nasdaq_composite_tickers():
    try:
        url = 'https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt'
        r = _SESSION.get(url, timeout=15)
        r.raise_for_status()
        tickers = []
        for line in r.text.split('\n')[1:-2]:
            parts = line.split('|')
            if parts and parts[0].strip():
                sym = parts[0].strip().replace('.', '-')
                if sym.isalpha() or (sym.replace('-','').isalpha() and '-' in sym):
                    tickers.append(sym)
        return list(set(tickers))
    except Exception as e:
        print(f"[ERROR] NASDAQ Composite: {e}"); return []

def get_nyse_tickers():
    try:
        url = 'https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt'
        r = _SESSION.get(url, timeout=15)
        r.raise_for_status()
        tickers = []
        for line in r.text.split('\n')[1:-2]:
            parts = line.split('|')
            if len(parts) > 2 and parts[2] in ('N', 'A', 'P'):
                sym = parts[0].strip().replace('.', '-')
                if sym.isalpha() or (sym.replace('-','').isalpha() and '-' in sym):
                    tickers.append(sym)
        return list(set(tickers))
    except Exception as e:
        print(f"[ERROR] NYSE: {e}"); return []

def get_all_tickers():
    sp500    = get_cached_ticker_list('sp500',            get_sp500_tickers)
    ndq100   = get_cached_ticker_list('nasdaq100',        get_nasdaq100_tickers)
    ndq_comp = get_cached_ticker_list('nasdaq_composite', get_nasdaq_composite_tickers)
    nyse     = get_cached_ticker_list('nyse',             get_nyse_tickers)
    combined = list(set(sp500 + ndq100 + ndq_comp + nyse))
    for t in SPECIAL_TICKERS:
        if t not in combined: combined.append(t)
    print(f"[STATS] S&P500:{len(sp500)} | NASDAQ-100:{len(ndq100)} | NASDAQComp:{len(ndq_comp)} | NYSE:{len(nyse)} | TOTAL:{len(combined)}")
    return combined

def get_tickers_by_source(source='sp500_nasdaq', use_cache=True):
    if source == 'sp500':
        t = get_cached_ticker_list('sp500', get_sp500_tickers) if use_cache else get_sp500_tickers()
    elif source == 'nasdaq100':
        t = get_cached_ticker_list('nasdaq100', get_nasdaq100_tickers) if use_cache else get_nasdaq100_tickers()
    elif source == 'nasdaq_composite':
        t = get_cached_ticker_list('nasdaq_composite', get_nasdaq_composite_tickers) if use_cache else get_nasdaq_composite_tickers()
    elif source == 'nyse':
        t = get_cached_ticker_list('nyse', get_nyse_tickers) if use_cache else get_nyse_tickers()
    elif source == 'sp500_nasdaq':
        # Fuente rápida: S&P500 + NASDAQ-100 ≈ 600 tickers de alta calidad
        sp  = get_cached_ticker_list('sp500',    get_sp500_tickers)
        ndq = get_cached_ticker_list('nasdaq100', get_nasdaq100_tickers)
        t   = list(set(sp + ndq))
        print(f"[STATS] S&P500:{len(sp)} + NASDAQ-100:{len(ndq)} = {len(t)} tickers (modo rapido)")
    elif source == 'trump':
        t = TRUMP_TICKERS.copy()
    elif source == 'volatile':
        t = VOLATILE_TICKERS.copy()
    else:
        return get_all_tickers()
    # Agregar SPECIAL_TICKERS a cualquier fuente
    for st in SPECIAL_TICKERS:
        if st not in t: t.append(st)
    return t

# ── Función principal de escaneo (BULK + paralelo) ────────────────────────────
def fetch_stock_data(progress_callback=None, stop_event=None, use_cache=True, max_workers=15, source='all'):
    def cb(msg, pct):
        if progress_callback: progress_callback(msg, pct)
        else: print(f"[{pct*100:.0f}%] {msg}")

    cb("Analizando régimen de mercado...", 0.0)
    market_context = get_market_regime()
    score_mod = market_context['score_modifier']
    
    # ── IA ADAPTATIVA: Verificar resultados anteriores antes de iniciar ──────
    if get_learner:
        try:
            cb("IA: Verificando resultados de días anteriores...", 0.01)
            learner = get_learner()
            learner.verify_past_recommendations()
        except Exception as e:
            logger.error(f"Error verificando recomendaciones: {e}")

    cb(f"Obteniendo lista de tickers ({source})...", 0.02)
    tickers = get_tickers_by_source(source, use_cache)
    total = len(tickers)

    if total == 0:
        cb("Sin tickers. Abortando.", 0.0)
        return []

    cb(f"{total} tickers encontrados. Iniciando descarga masiva...", 0.05)

    # ── PASO 1: Descarga BULK de históricos (el más eficiente) ────────────────
    # Verificar cuáles ya tienen caché válido
    cached_tickers  = [t for t in tickers if use_cache and is_cache_valid(t, 'history')]
    missing_tickers = [t for t in tickers if t not in cached_tickers]

    cb(f"Caché: {len(cached_tickers)} | Descarga: {len(missing_tickers)}", 0.07)

    prefetched = {}
    if missing_tickers:
        cb(f"Descargando {len(missing_tickers)} históricos en lotes...", 0.10)
        prefetched = _bulk_download_history(missing_tickers)
        # Guardar en caché
        for t, df in prefetched.items():
            save_to_cache(t, df, 'history')
        cb(f"Descarga completada: {len(prefetched)} exitosos", 0.35)

    if stop_event and stop_event.is_set():
        cb("Detenido por el usuario.", 0.35)
        return []

    # ── PASO 2: Procesar en paralelo ──────────────────────────────────────────
    results     = []
    processed   = 0
    start_time  = time.time()

    # Reunir todos los tickers con sus datos
    def get_hist(t):
        if t in prefetched:
            return prefetched[t]
        elif is_cache_valid(t, 'history'):
            return load_from_cache(t, 'history')
        return None

    def process(t):
        h = get_hist(t)
        return process_single_ticker(t, use_cache=use_cache, prefetched_history=h)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process, t): t for t in tickers}
        for future in as_completed(futures):
            if stop_event and stop_event.is_set():
                executor.shutdown(wait=False, cancel_futures=True)
                cb("Detenido por el usuario.", processed / total)
                break

            t = futures[future]
            processed += 1

            try:
                r = future.result()
                if r:
                    r['Score'] = round(r['Score'] * score_mod, 1)
                    r['Viabilidad'] = _score_label(r['Score'])
                    
                    # Calcular confianza si hay learner
                    if get_learner:
                        conf = get_learner().get_confidence(r['Ticker'], r.get('Sector', ''), r.get('RSI', 50))
                        r['AI_Confidence'] = conf.get('confidence')
                        r['AI_Confidence_Available'] = conf.get('available', False)
                        r['AI_Sample_Size'] = conf.get('sample_size', 0)
                        r['AI_Notes'] = conf['notes']
                        
                        # Ajustar etiqueta si la confianza es muy baja o muy alta
                        if conf.get('confidence') is not None and conf['confidence'] < 30 and 'EXCELENTE' in r['Viabilidad']:
                            r['Viabilidad'] = "🟡 BUENA (Riesgo IA)"
                    
                    results.append(r)
            except: pass

            pct  = 0.35 + (processed / total) * 0.65
            rate = processed / max(time.time() - start_time, 0.1)
            eta  = (total - processed) / rate
            cb(f"{processed}/{total} | {t} | {rate:.1f} t/s | ETA: {eta:.0f}s | Resultados: {len(results)}", pct)

    cb(f"✅ Escaneo completo: {len(results)} oportunidades encontradas.", 1.0)

    if not results:
        return []

    df = pd.DataFrame(results).sort_values('Score', ascending=False)
    final_results = df.to_dict('records')
    
    # ── Convertir precios a MXN ───────────────────────────────────────────────
    usd_mxn = _get_usd_mxn()
    rate_meta = exchange_rate_contract(usd_mxn)
    for r in final_results:
        if 'Price' in r and r['Price']:
            r['Price_MXN'] = round(r['Price'] * usd_mxn, 2)
            r['ATR_MXN'] = round(r.get('ATR', 0) * usd_mxn, 2)
        else:
            r['Price_MXN'] = 0
            r['ATR_MXN'] = 0
        r['Exchange_Rate'] = rate_meta
    cb(f"Tipo de cambio USD/MXN: {usd_mxn:.2f}", 0.95)
    
    # ── IA ADAPTATIVA: Registrar recomendaciones de este escaneo ──────────────
    if get_learner and final_results:
        try:
            get_learner().record_scan_results(final_results, top_n=50)
        except Exception as e:
            logger.error(f"Error registrando resultados en IA: {e}")
            
    return final_results


# ── API de fundamental_metrics (compatibilidad) ───────────────────────────────
def get_fundamental_metrics(info: dict) -> dict:
    return {
        'pe_ratio':       info.get('trailingPE'),
        'debt_equity':    info.get('debtToEquity'),
        'revenue_growth': info.get('revenueGrowth'),
        'profit_margin':  info.get('profitMargins'),
        'current_ratio':  info.get('currentRatio'),
        'return_equity':  info.get('returnOnEquity'),
        'sector':         info.get('sector', 'N/A'),
        'industry':       info.get('industry', 'N/A'),
        'market_cap':     info.get('marketCap', 0),
    }
