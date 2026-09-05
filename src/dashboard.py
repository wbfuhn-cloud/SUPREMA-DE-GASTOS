import json
from typing import List, Dict, Any
from collections import defaultdict
from datetime import datetime
import calendar

class DashboardGenerator:

    @staticmethod
    def get_dashboard_data(expenses: list, categories: Any = None) -> dict:
        """
        Calcula los datos del dashboard y los retorna estructurados.
        """
        if not expenses: expenses = []
        if not categories:
             categories = ['ALIMENTOS', 'TRANSPORTE', 'HOGAR', 'SERVICIOS', 'PERSONAL', 
                           'ENTRETENIMIENTO', 'SALUD', 'OTRO']

        unconfirmed_count = sum(1 for e in expenses if e.get('status') == 'unconfirmed')
        expenses = [e for e in expenses if e.get('status') != 'unconfirmed']

        # Calcular totales por tipo
        total_amount: float = 0.0
        total_debt: float = 0.0
        total_loan: float = 0.0
        count = len(expenses)
        
        # Agrupar por categoría
        cat_totals: Dict[str, float] = {}
        merchant_totals: Dict[str, float] = {}
        
        for e in expenses:
            amount: float = float(e.get('total', 0) or 0)
            etype = e.get('type', 'Normal')
            
            total_amount = total_amount + amount
            
            if etype == 'Deuda' and e.get('status') == 'pending':
                _td: float = total_debt + amount
                total_debt = _td
            elif etype == 'Prestamo' and e.get('status') == 'pending':
                _tl: float = total_loan + amount
                total_loan = _tl
                
            cat = e.get('category', 'OTRO')
            if not cat: cat = 'OTRO'
            cat_str = str(cat).upper()
            cat_totals[cat_str] = cat_totals.get(cat_str, 0.0) + amount
            
            merchant_str = str(e.get('merchant', 'Unknown'))
            merchant_totals[merchant_str] = merchant_totals.get(merchant_str, 0.0) + amount
            
        # Ordenar categorías por monto
        sorted_cats = sorted(cat_totals.items(), key=lambda item: item[1], reverse=True)
        cats = [k for k, v in sorted_cats]
        vals = [v for k, v in sorted_cats]
        
        # Últimos 10 gastos ordenados por fecha
        sorted_expenses = list(sorted(expenses, key=lambda x: x.get('date', ''), reverse=False)) if expenses else []
        recent_expenses = []
        if sorted_expenses:
            start_idx = len(sorted_expenses) - 10
            if start_idx < 0:
                start_idx = 0
            for i in range(start_idx, len(sorted_expenses)):
                recent_expenses.append(sorted_expenses[i])
        recent_expenses.reverse()
        
        # Agrupar por semana
        week_totals: Dict[int, float] = {}
        for e in expenses:
            try:
                w = int(e.get('week', 0))
            except (ValueError, TypeError):
                w = 0
            week_totals[w] = week_totals.get(w, 0.0) + float(e.get('total', 0) or 0)
        
        sorted_weeks = sorted(week_totals.items()) 
        week_labels = [f"Semana {k}: ${v:,.2f}" for k, v in sorted_weeks]
        week_data = [v for k, v in sorted_weeks]

        # Estadísticas avanzadas - Proyección Mejorada
        now = datetime.now()
        current_day = now.day
        _, days_in_month = calendar.monthrange(now.year, now.month)
        current_month_str = now.strftime('%Y-%m')   # e.g. "2026-03"

        # ── Solo gastos del mes actual ──
        current_month_expenses = [
            e for e in expenses
            if str(e.get('date', '')).startswith(current_month_str)
               and e.get('type', 'Normal') not in ('Prestamo', 'Deuda')
        ]
        month_total_so_far = sum(e.get('total', 0) for e in current_month_expenses)

        # ── Días efectivos: días transcurridos en el mes, mínimo 7 para estabilizar ──
        # Esto evita que 1-2 gastos grandes en el día 1 o 2 inflen brutalmente la proyección.
        effective_days = max(current_day, 7)
        daily_avg = month_total_so_far / effective_days
        monthly_projection = daily_avg * days_in_month

        
        max_expense = max(expenses, key=lambda x: x.get('total', 0)) if expenses else None
        max_expense_val = max_expense.get('total', 0) if max_expense else 0
        max_expense_merchant = max_expense.get('merchant', 'N/A') if max_expense else '-'
        
        # Top 5 Comercios HTML
        sorted_m = sorted(merchant_totals.items(), key=lambda x: x[1], reverse=True)
        sorted_merchants = []
        for i in range(len(sorted_m)):
            if i == 5:
                break
            sorted_merchants.append(sorted_m[i])
        top_merchants_html = ""
        if sorted_merchants:
            max_merch_val = sorted_merchants[0][1]
            for m, total in sorted_merchants:
                percent = (total / total_amount * 100) if total_amount != 0.0 else 0
                bar_width = (total / max_merch_val * 100) if max_merch_val != 0.0 else 0
                
                top_merchants_html += f'''
                <div style="margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.9em; margin-bottom: 4px;">
                        <span style="font-weight: 500;">{m}</span>
                        <span style="font-weight: 600;">${total:,.2f}</span>
                    </div>
                    <div style="background: #E5E7EB; border-radius: 4px; height: 6px; width: 100%;">
                        <div style="background: var(--primary-purple); height: 6px; border-radius: 4px; width: {bar_width}%;"></div>
                    </div>
                </div>
                '''
        else:
            top_merchants_html = '<div style="color: var(--text-secondary); text-align: center; padding: 20px;">Sin datos suficientes</div>'

        loans_list = [e for e in expenses if e.get('type') == 'Prestamo' and e.get('status') == 'pending']
        debts_list = [e for e in expenses if e.get('type') == 'Deuda' and e.get('status') == 'pending']
        
        # Recents Table HTML
        recent_html = DashboardGenerator._generate_table_rows(recent_expenses)
        
        # Lists for modals
        loans_html = DashboardGenerator._generate_table_rows(loans_list)
        debts_html = DashboardGenerator._generate_table_rows(debts_list)
        
        return {
            'categories_list': categories,
            'count': count,
            'total_amount': total_amount,
            'total_debt': total_debt,
            'total_loan': total_loan,
            'daily_avg': daily_avg,
            'monthly_projection': monthly_projection,
            'max_expense_val': max_expense_val,
            'max_expense_merchant': max_expense_merchant,
            'cats': cats,
            'vals': vals,
            'week_labels': week_labels,
            'week_data': week_data,
            'top_merchants_html': top_merchants_html,
            'recent_html': recent_html,
            'loans_html': loans_html,
            'debts_html': debts_html,
            'current_day': current_day,
            'days_in_month': days_in_month,
            'expenses_list': expenses,
            'recent_list': recent_expenses,
            'unconfirmed_count': unconfirmed_count
        }

    @staticmethod
    def _generate_table_rows(items):
        if not items:
            return '<tr><td colspan="4" style="text-align: center; color: var(--text-secondary);">No hay registros</td></tr>'
        rows: List[str] = []
        for e in items:
            expense_id = e.get('id', '')
            merchant_safe = str(e.get('merchant', 'Unknown')).replace("'", "\\'").replace('"', '\\"')
            month_safe = str(e.get('month', '')).replace("'", "\\'").replace('"', '\\"')
            
            total_val = e.get('total', 0)
            pass_val = total_val
            
            button_html = ''
            if total_val > 0:
                button_html = f'''
                    <button class="mark-paid-btn" 
                            data-id="{expense_id}"
                            data-day="{e.get('day')}" 
                            data-month="{month_safe}" 
                            data-merchant="{merchant_safe}" 
                            data-total="{pass_val}"
                            onclick="markAsPaid(this)">
                        ✓
                    </button>
                '''
            else:
                button_html = '<span class="status-icon">✓</span>'
            
            cat_badge = f'<span class="badge purple">{e.get("category")}</span>' if e.get("category") else '<span class="badge">GENERAL</span>'
            type_badge = ''
            if e.get('type') == 'Prestamo':
                type_badge = '<span class="badge" style="color:var(--warning-color); background: #FFFBEB;">PRESTAMO</span>'
            elif e.get('type') == 'Deuda':
                type_badge = '<span class="badge" style="color:var(--danger-color); background: #FEF2F2;">DEUDA</span>'

            rows.append(f'''
            <tr id="expense-{expense_id}">
                <td><span style="opacity: 0.7; font-size:0.9em;">{e.get('month','')[:3]}</span> {e.get('day','')}</td>
                <td>
                    <div style="font-weight: 600; color: var(--text-primary);">{e.get('merchant','Unknown')}</div>
                    <div style="font-size: 0.8em; color: var(--text-secondary); margin-top: 2px;">
                        {cat_badge}
                         {type_badge}
                    </div>
                </td>
                <td class="expense-total">${total_val:,.2f}</td>
                <td style="text-align: right;">{button_html}</td>
            </tr>
            ''')
        
        total_sum = sum(e.get('total', 0) for e in items)
        
        rows.append(f'''
        <tr style="border-top: 2px solid var(--border-color); background-color: var(--bg-color);">
            <td colspan="2" style="text-align: right; font-weight: 700; color: var(--text-primary);">TOTAL:</td>
            <td class="expense-total" style="font-size: 1.1em;">${total_sum:,.2f}</td>
            <td></td>
        </tr>
        ''')
        
        return '\n'.join(rows)
    
    @staticmethod
    def generate_html(expenses, categories=None, selected_year=None, available_years=None):
        data = DashboardGenerator.get_dashboard_data(expenses, categories)
        
        # Unpack variables for template
        count = data['count']
        total_amount = data['total_amount']
        total_debt = data['total_debt']
        total_loan = data['total_loan']
        daily_avg = data['daily_avg']
        monthly_projection = data['monthly_projection']
        max_expense_val = data['max_expense_val']
        max_expense_merchant = data['max_expense_merchant']
        top_merchants_html = data['top_merchants_html']
        cats = data['cats']
        vals = data['vals']
        week_labels = data['week_labels']
        week_data = data['week_data']
        unconfirmed_count = data.get('unconfirmed_count', 0)
        
        # Calculate Health Score (Simple logic: based on projection vs budget placeholder)
        # Let's assume a theoretical budget of 25,000 for the indicator
        health_score = max(10, min(100, int(100 - (monthly_projection / 350)))) if monthly_projection > 0 else 100
        health_status = "Excelente" if health_score > 80 else "Regular" if health_score > 50 else "Crítico"

        # ── Year tabs ───────────────────────────────────────────────────────
        years_html = ""
        active_cls = 'bg-primary text-white shadow-md'
        inactive_cls = 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
        todos_cls = active_cls if selected_year is None else inactive_cls
        years_html += '<a href="/dashboard" class="px-4 py-2 rounded-xl text-xs font-bold transition-colors ' + todos_cls + '">TODOS</a>'
        if available_years:
            for y in available_years:
                cls = active_cls if selected_year == y else inactive_cls
                years_html += '<a href="/dashboard?year=' + str(y) + '" class="px-4 py-2 rounded-xl text-xs font-bold transition-colors ' + cls + '">' + str(y) + '</a>'

        unconfirmed_banner = ""
        if unconfirmed_count > 0:
            unconfirmed_banner = f'''
            <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-8 flex justify-between items-center shadow-sm">
                <div class="flex items-center gap-3 text-amber-800">
                    <span class="material-symbols-outlined text-amber-600">notifications_active</span>
                    <strong class="font-semibold text-sm md:text-base">Tienes {unconfirmed_count} gasto(s) pendientes de revisión.</strong>
                </div>
                <a href="/transactions" class="bg-amber-500 hover:bg-amber-600 text-white font-bold py-2 px-4 rounded-lg text-xs md:text-sm transition-colors">
                    Revisar Ahora
                </a>
            </div>
            '''
        
        raw_recent_html = DashboardGenerator._generate_table_rows(data['recent_list'])
        recent_html_clean = raw_recent_html.split('<tr style="border-top')[0]

        data['health_score'] = health_score
        data['health_status'] = health_status
        data['years_html'] = years_html
        data['unconfirmed_banner'] = unconfirmed_banner
        data['recent_html_clean'] = recent_html_clean
        
        return data
