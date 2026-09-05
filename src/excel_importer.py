import pandas as pd
import os
import sqlite3
from datetime import datetime
import sys

# Add src to path to import DatabaseManager
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import DatabaseManager

class ExcelImporter:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.months_map = {
            'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6,
            'JULIO': 7, 'AGOSTO': 8, 'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12
        }

    def import_file(self, file_path: str):
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return

        print(f"--- Importing: {os.path.basename(file_path)} ---")
        
        # Detect year from filename if possible (e.g. "FINANAZAS 2026.xlsx")
        filename = os.path.basename(file_path)
        default_year = 2026
        if '2025' in filename: default_year = 2025
        elif '2024' in filename: default_year = 2024

        xl = pd.ExcelFile(file_path)
        
        total_imported = 0
        total_skipped = 0

        for sheet_name in xl.sheet_names:
            # Skip non-data sheets
            if sheet_name in ['RESUMEN', 'CONFIG', 'HERRAMIENTA POR COMPRAR']:
                continue
            
            print(f"Processing sheet: {sheet_name}")
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Identify columns (case insensitive)
            cols = {c.upper().strip(): c for c in df.columns}
            
            # Map standard columns
            col_map = {
                'DIA': cols.get('DIA'),
                'MES': cols.get('MES'),
                'YEAR': cols.get('AÑO') or cols.get('YEAR'),
                'WEEK': cols.get('SEMANA'),
                'METHOD': cols.get('MÉTODO PAGO') or cols.get('MÉTODO'),
                'CAT': cols.get('CATEGORIA') or cols.get('CONCEPTO'),
                'MERCHANT': cols.get('COMERCIO') or cols.get('LUGAR O EMPRESA'),
                'DETAILS': cols.get('DES. GENERAL'),
                'TOTAL': cols.get('TOTAL') or cols.get('COSTO TOTAL') or cols.get('MONTO')
            }

            if not col_map['TOTAL'] or (not col_map['DIA'] and not col_map['MES']):
                print(f"  Skipping sheet {sheet_name}: Required columns missing.")
                continue

            for _, row in df.iterrows():
                try:
                    total = row.get(col_map['TOTAL'], 0)
                    if pd.isna(total) or total == 0: continue
                    
                    # Absolute value for total (expenses are stored positive, debts might be negative in Excel)
                    total = abs(float(total))

                    day = int(row.get(col_map['DIA'], 1)) if not pd.isna(row.get(col_map['DIA'])) else 1
                    month_str = str(row.get(col_map['MES'], 'ENERO')).upper().strip()
                    year = int(row.get(col_map['YEAR'], default_year)) if not pd.isna(row.get(col_map['YEAR'])) else default_year
                    
                    month_idx = self.months_map.get(month_str, 1)
                    
                    # Construct valid ISO date
                    try:
                        date_obj = datetime(year, month_idx, day)
                        date_str = date_obj.strftime('%Y-%m-%d')
                    except:
                        date_str = f"{year}-{month_idx:02d}-{day if day <= 28 else 28:02d}"

                    merchant = str(row.get(col_map['MERCHANT'], 'VARIOS')).upper().strip()
                    if pd.isna(row.get(col_map['MERCHANT'])): merchant = 'VARIOS'
                    
                    # Deduplication check
                    existing_id = self.db.find_expense(day, month_str, merchant, total)
                    if existing_id:
                        total_skipped += 1
                        continue

                    data = {
                        'day': day,
                        'month': month_str,
                        'week': int(row.get(col_map['WEEK'], 0)) if not pd.isna(row.get(col_map['WEEK'])) else 0,
                        'date': date_str,
                        'payment_method': str(row.get(col_map['METHOD'], 'TARJETA')).upper().strip() if not pd.isna(row.get(col_map['METHOD'])) else 'TARJETA',
                        'category': str(row.get(col_map['CAT'], 'OTRO')).upper().strip() if not pd.isna(row.get(col_map['CAT'])) else 'OTRO',
                        'merchant': merchant,
                        'details': str(row.get(col_map['DETAILS'], '')).upper().strip() if not pd.isna(row.get(col_map['DETAILS'])) else '',
                        'total': total,
                        'type': 'Normal',
                        'status': 'paid',  # Excel data is historical
                        'project': sheet_name
                    }
                    
                    success, _ = self.db.add_expense(data)
                    if success:
                        total_imported += 1
                except Exception as e:
                    print(f"  Error processing row: {e}")

        print(f"Finished: {total_imported} imported, {total_skipped} skipped (duplicates).")

if __name__ == "__main__":
    db = DatabaseManager()
    importer = ExcelImporter(db)
    
    # Import 2025 and 2026
    importer.import_file(r"C:\Users\PLI INGENIERIA\OneDrive\FINANAZAS 2025.xlsx")
    importer.import_file(r"C:\Users\PLI INGENIERIA\OneDrive\FINANAZAS 2026.xlsx")
