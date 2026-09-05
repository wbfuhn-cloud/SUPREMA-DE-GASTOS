import sys
sys.path.insert(0, 'tools/NOTIFICADOR_BOT')
import stock_scanner as ss

tickers = ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'AMZN']
results = []
for t in tickers:
    r = ss.process_single_ticker(t)
    if r:
        results.append(r)
        print(f"OK {t}: Score={r['Score']} Price={r['Price']} RSI={r['RSI']}")
    else:
        print(f"SKIP {t}")

print(f"\nTotal: {len(results)}/{len(tickers)}")
ctx = ss.get_market_regime()
print(f"Mercado: {ctx['regime']} | VIX: {ctx['vix']}")
