import json
import os
from datetime import datetime

class ConfigManager:
    """Gestor de configuraciones y preferencias del usuario"""
    
    def __init__(self, config_file='visor_config.json'):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        """Carga configuración desde archivo JSON"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error al cargar configuración: {e}")
                return self.get_default_config()
        else:
            return self.get_default_config()
    
    def get_default_config(self):
        """Retorna configuración por defecto"""
        return {
            'filters': {
                'min_rsi': 0,
                'max_rsi': 100,
                'min_beta': 0.8,
                'max_beta': 1.5,
                'min_margin': 0.25,
                'viability_filter': 'TODAS'
            },
            'display': {
                'theme': 'Dark',
                'visible_columns': [
                    'ticker', 'price', 'viabilidad', 'rsi', 
                    'ma100', 'ma200', 'macd', 'beta', 'nota'
                ]
            },
            'watchlist': [],
            'portfolio': {}, # { 'TICKER': {'qty': 0, 'avg_price': 0, 'date': ''} }
            'risk_management': {
                'capital': 10000.0,
                'risk_pct': 0.02,
                'atr_multiplier': 2.0
            },
            'last_scan': None,
            'scan_history': [],
            'live_alerts': {
                'enabled': True,
                'interval_minutes': 5,
                'min_confidence': 40.0,
                'sources': ['trump', 'volatile', 'portfolio', 'watchlist'],
                'alert_on_buy': True,
                'alert_on_sell': True
            }
        }
    
    def get_portfolio(self):
        """Obtiene el portafolio actual con cantidades y precios"""
        return self.config.get('portfolio', {})

    def update_portfolio_item(self, ticker, qty, avg_price):
        """Agrega o actualiza una posición en el portafolio"""
        portfolio = self.get_portfolio()
        portfolio[ticker.upper()] = {
            'qty': float(qty),
            'avg_price': float(avg_price),
            'updated_at': datetime.now().isoformat()
        }
        self.config['portfolio'] = portfolio
        self.save_config()
        return True

    def remove_from_portfolio(self, ticker):
        """Elimina una posición del portafolio"""
        portfolio = self.get_portfolio()
        if isinstance(portfolio, list):
            if ticker.upper() in portfolio:
                portfolio.remove(ticker.upper())
                self.config['portfolio'] = portfolio
                self.save_config()
                return True
        else:
            if ticker.upper() in portfolio:
                del portfolio[ticker.upper()]
                self.config['portfolio'] = portfolio
                self.save_config()
                return True
        return False
    
    def save_config(self):
        """Guarda configuración actual a archivo"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error al guardar configuración: {e}")
            return False
    
    def get_filters(self):
        """Obtiene filtros actuales"""
        return self.config.get('filters', {})
    
    def set_filters(self, filters):
        """Actualiza filtros"""
        self.config['filters'] = filters
        self.save_config()
    
    def get_watchlist(self):
        """Obtiene lista de favoritos"""
        return self.config.get('watchlist', [])
    
    def add_to_watchlist(self, ticker):
        """Agrega ticker a favoritos"""
        watchlist = self.get_watchlist()
        if ticker not in watchlist:
            watchlist.append(ticker)
            self.config['watchlist'] = watchlist
            self.save_config()
            return True
        return False
    
    def remove_from_watchlist(self, ticker):
        """Remueve ticker de favoritos"""
        watchlist = self.get_watchlist()
        if ticker in watchlist:
            watchlist.remove(ticker)
            self.config['watchlist'] = watchlist
            self.save_config()
            return True
        return False
    
    def is_in_watchlist(self, ticker):
        """Verifica si ticker está en favoritos"""
        return ticker in self.get_watchlist()
    
    def update_last_scan(self, results_count):
        """Actualiza información del último escaneo"""
        self.config['last_scan'] = {
            'timestamp': datetime.now().isoformat(),
            'results_count': results_count
        }
        
        # Agregar a historial (mantener últimos 10)
        history = self.config.get('scan_history', [])
        history.append(self.config['last_scan'])
        self.config['scan_history'] = history[-10:]  # Mantener solo últimos 10
        
        self.save_config()
    
    def get_last_scan_info(self):
        """Obtiene información del último escaneo"""
        return self.config.get('last_scan', None)
    
    def get_scan_history(self):
        """Obtiene historial de escaneos"""
        return self.config.get('scan_history', [])
    
    def reset_to_defaults(self):
        """Resetea configuración a valores por defecto"""
        self.config = self.get_default_config()
        self.save_config()

if __name__ == "__main__":
    # Test
    config = ConfigManager('test_config.json')
    
    print("Configuración por defecto:")
    print(json.dumps(config.config, indent=2))
    
    # Agregar a watchlist
    config.add_to_watchlist("AAPL")
    config.add_to_watchlist("GOOGL")
    config.add_to_watchlist("MSFT")
    
    print("\nWatchlist:")
    print(config.get_watchlist())
    
    # Actualizar último escaneo
    config.update_last_scan(45)
    
    print("\nÚltimo escaneo:")
    print(config.get_last_scan_info())
    
    # Guardar
    config.save_config()
    print("\n✅ Configuración guardada en test_config.json")
