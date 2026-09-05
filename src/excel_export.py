"""
Utilidad de Exportación a Excel

Este módulo convierte excel.py en una herramienta de exportación únicamente.
Permite exportar datos de la base de datos SQLite a formato Excel.

Uso:
    from src.excel_export import ExcelExporter
    
    exporter = ExcelExporter()
    exporter.export_to_excel(expenses, "reporte_2026.xlsx")
"""

import openpyxl
from openpyxl.styles import Alignment, Border, Side, PatternFill, Font
from datetime import datetime
import os

class ExcelExporter:
    """Exporta datos de gastos a formato Excel."""
    
    @staticmethod
    def export_to_excel(expenses, output_path=None):
        """
        Exporta una lista de gastos a un archivo Excel.
        
        Args:
            expenses: Lista de diccionarios con los gastos
            output_path: Ruta del archivo de salida. Si es None, usa un nombre por defecto.
        
        Returns:
            Tuple[bool, str]: (éxito, mensaje/ruta)
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"exports/gastos_export_{timestamp}.xlsx"
        
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        
        try:
            # Crear workbook
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "GASTO CORRIENTE"
            
            # Encabezados
            headers = ["#", "DIA", "MES", "SEMANA", "METODO DE PAGO", "CONCEPTO", 
                      "UNIDAD", "LUGAR O EMPRESA", "DESCRIPCION GENERAL", "COSTO TOTAL"]
            
            # Estilo de encabezados
            header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")
            
            for col_num, header in enumerate(headers, 1):
                cell = ws.cell(row=2, column=col_num)
                cell.value = header
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
            
            # Datos
            for idx, expense in enumerate(expenses, 1):
                row_num = idx + 2  # Fila 3 en adelante
                
                ws.cell(row=row_num, column=1).value = idx
                ws.cell(row=row_num, column=2).value = expense.get('day')
                ws.cell(row=row_num, column=3).value = expense.get('month')
                ws.cell(row=row_num, column=4).value = expense.get('week')
                ws.cell(row=row_num, column=5).value = expense.get('payment_method')
                ws.cell(row=row_num, column=6).value = expense.get('category')
                ws.cell(row=row_num, column=7).value = expense.get('unit', 'GENERAL')
                ws.cell(row=row_num, column=8).value = expense.get('merchant')
                ws.cell(row=row_num, column=9).value = expense.get('details')
                
                # Celda de total con formato de moneda
                total_cell = ws.cell(row=row_num, column=10)
                total_cell.value = expense.get('total', 0)
                total_cell.number_format = '$ #,##0.00'
                
                # Aplicar color según tipo
                expense_type = expense.get('type', 'Normal')
                if expense_type == 'Prestamo':
                    total_cell.fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
                elif expense_type == 'Deuda':
                    total_cell.fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
                
                # Alineación
                for col in range(1, 11):
                    cell = ws.cell(row=row_num, column=col)
                    if col in [3, 5, 6, 7, 8, 9]:  # MES, METODO, CONCEPTO, UNIDAD, LUGAR, DESCRIPCION
                        cell.alignment = Alignment(horizontal="left")
                    else:
                        cell.alignment = Alignment(horizontal="center")
            
            # Ajustar anchos de columna
            # #, DIA, MES, SEM, MET, CON, UNI, LUG, DES, TOT
            column_widths = [5, 6, 10, 8, 18, 20, 12, 25, 35, 15]
            for col_num, width in enumerate(column_widths, 1):
                ws.column_dimensions[openpyxl.utils.get_column_letter(col_num)].width = width
            
            # Guardar
            wb.save(output_path)
            
            return True, os.path.abspath(output_path)
            
        except Exception as e:
            return False, f"Error al exportar: {str(e)}"
    
    @staticmethod
    def export_from_database(db_manager, output_path=None):
        """
        Exporta directamente desde un DatabaseManager.
        
        Args:
            db_manager: Instancia de DatabaseManager
            output_path: Ruta del archivo de salida
        
        Returns:
            Tuple[bool, str]: (éxito, mensaje/ruta)
        """
        expenses = db_manager.get_all_expenses()
        return ExcelExporter.export_to_excel(expenses, output_path)


# Script ejecutable para exportar desde línea de comandos
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from src.database import DatabaseManager
    
    print("=" * 60)
    print("EXPORTACIÓN: Base de Datos → Excel")
    print("=" * 60)
    print()
    
    db = DatabaseManager()
    
    # Solicitar nombre de archivo
    default_name = f"exports/gastos_{datetime.now().strftime('%Y%m%d')}.xlsx"
    output = input(f"Nombre del archivo de salida [{default_name}]: ").strip()
    
    if not output:
        output = default_name
    
    print(f"\nExportando a: {output}")
    success, result = ExcelExporter.export_from_database(db, output)
    
    if success:
        print(f"✓ Exportación exitosa!")
        print(f"  Archivo: {result}")
    else:
        print(f"✗ Error: {result}")
