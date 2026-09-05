def calculate_position_size(
    capital: float,
    price: float,
    atr: float,
    risk_pct: float = 0.02,    # 2% del capital por defecto
    atr_multiplier: float = 2.0 # Stop a 2x ATR
) -> dict:
    """
    Calcula el tamaño de la posición y niveles de stop/target basándose en el riesgo.
    
    Args:
        capital: Capital total disponible
        price: Precio actual de la acción
        atr: Average True Range (volatilidad)
        risk_pct: Porcentaje de capital a arriesgar por operación (0.01 = 1%)
        atr_multiplier: Multiplicador del ATR para situar el stop loss
        
    Returns:
        Diccionario con los parámetros del plan de entrada
    """
    if price <= 0 or atr <= 0:
        return {'error': 'Precio o ATR inválidos'}
        
    # Stop-Loss basado en volatilidad (ATR)
    stop_loss = price - (atr_multiplier * atr)
    risk_per_share = price - stop_loss
    
    if risk_per_share <= 0:
        return {'error': 'Volatilidad demasiado baja o multiplicador inválido'}
    
    # Capital máximo que estamos dispuestos a perder en esta operación
    max_risk_dollars = capital * risk_pct
    
    # Cantidad de acciones a comprar
    num_shares = int(max_risk_dollars / risk_per_share)
    
    if num_shares == 0:
        return {
            'error': 'Capital insuficiente para el riesgo definido',
            'acciones_necesarias': 1,
            'riesgo_por_accion': round(risk_per_share, 2)
        }
        
    capital_required = num_shares * price
    
    # Target conservador: ratio R:R de 2:1 (Reward to Risk)
    target_price = price + (2 * risk_per_share)
    
    return {
        'precio_entrada':       round(price, 2),
        'stop_loss':            round(stop_loss, 2),
        'precio_objetivo':      round(target_price, 2),
        'num_acciones':         num_shares,
        'capital_requerido':    round(capital_required, 2),
        'riesgo_maximo':        round(max_risk_dollars, 2),
        'beneficio_potencial':  round(num_shares * (target_price - price), 2),
        'ratio_riesgo_recomp':  '1:2',
        'pct_capital_usado':    round((capital_required / capital) * 100, 1)
    }

if __name__ == "__main__":
    # Test rápido
    res = calculate_position_size(10000, 150, 3.5)
    import json
    print(json.dumps(res, indent=4))
