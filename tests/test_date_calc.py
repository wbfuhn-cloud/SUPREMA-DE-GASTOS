import datetime

def _enrich_date_details(data):
    """Calcula DIA, MES, SEMANA a partir de la fecha."""
    try:
        date_str = data.get('date')
        if not date_str:
            return
        
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        
        # Meses en español
        meses = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", 
                    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
        
        data['day'] = dt.day
        data['month'] = meses[dt.month - 1]
        data['week'] = dt.isocalendar()[1]
        
    except Exception as e:
        print(f"Error calculando fecha: {e}")
        # Fallback values
        data['day'] = 0
        data['month'] = "DESCONOCIDO"
        data['week'] = 0

# Test
test_data = {"date": "2026-01-15"}
_enrich_date_details(test_data)
print(f"Input: 2026-01-15")
print(f"Result: {test_data}")

if test_data['month'] == "ENERO" and test_data['week'] == 3:
    print("[OK] Calculation Correct")
else:
    print("[ERROR] Calculation Incorrect")
