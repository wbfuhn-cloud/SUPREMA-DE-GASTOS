import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from src.database import DatabaseManager
from src.core.constants import MONTHS_ES

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service for generating smart notifications about expenses, budgets, and debts.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the notification service.
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager
        logger.info("NotificationService initialized")
    
    def check_budget_alerts(self) -> List[Dict]:
        """
        Check if any category has exceeded its monthly budget.
        
        Returns:
            List of alert dictionaries with category, budget, spent, and overage info
        """
        alerts = []
        
        try:
            now = datetime.now()
            current_month = MONTHS_ES[now.month - 1]
            current_year = now.year
            
            # Get all budgets
            budgets = self.db.get_budgets()
            
            if not budgets:
                logger.info("No budgets configured")
                return []
            
            # Get current month spending by category
            spending = self.db.get_monthly_spending_by_category(current_month, current_year)
            
            # Check each budget
            for budget in budgets:
                category = budget['category']
                limit = budget['monthly_limit']
                spent = spending.get(category, 0.0)
                
                # Alert if spending exceeds 90% of budget
                if spent >= limit * 0.9:
                    overage = spent - limit
                    percentage = (spent / limit) * 100
                    
                    alerts.append({
                        'category': category,
                        'budget': limit,
                        'spent': spent,
                        'overage': overage,
                        'percentage': percentage,
                        'severity': 'critical' if spent >= limit else 'warning'
                    })
                    
                    logger.info(f"Budget alert: {category} - ${spent:.2f} / ${limit:.2f} ({percentage:.1f}%)")
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking budget alerts: {e}", exc_info=True)
            return []
    
    def check_debt_reminders(self) -> List[Dict]:
        """
        Get all pending debts and loans that need attention.
        
        Returns:
            List of pending debt/loan dictionaries
        """
        try:
            debts = self.db.get_pending_debts()
            
            if debts:
                logger.info(f"Found {len(debts)} pending debts/loans")
            
            return debts
            
        except Exception as e:
            logger.error(f"Error checking debt reminders: {e}", exc_info=True)
            return []
    
    def generate_weekly_summary(self) -> Dict:
        """
        Generate a summary of expenses for the past week.
        
        Returns:
            Dictionary with weekly statistics and breakdown
        """
        try:
            # Calculate date range (last 7 days)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")
            
            # Get expenses for the week
            expenses = self.db.get_weekly_expenses(start_str, end_str)
            
            if not expenses:
                return {
                    'period': f"{start_str} a {end_str}",
                    'total': 0,
                    'count': 0,
                    'by_category': {},
                    'by_payment_method': {},
                    'top_expenses': []
                }
            
            # Calculate totals
            total = sum(e['total'] for e in expenses)
            
            # Group by category
            by_category = {}
            for expense in expenses:
                cat = expense['category']
                by_category[cat] = by_category.get(cat, 0) + expense['total']
            
            # Group by payment method
            by_payment = {}
            for expense in expenses:
                method = expense['payment_method']
                by_payment[method] = by_payment.get(method, 0) + expense['total']
            
            # Get top 5 expenses
            top_expenses = sorted(expenses, key=lambda x: x['total'], reverse=True)[:5]
            
            summary = {
                'period': f"{start_str} a {end_str}",
                'total': total,
                'count': len(expenses),
                'by_category': by_category,
                'by_payment_method': by_payment,
                'top_expenses': top_expenses
            }
            
            logger.info(f"Weekly summary generated: ${total:.2f} in {len(expenses)} transactions")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating weekly summary: {e}", exc_info=True)
            return {}
    
    def format_budget_alert_message(self, alerts: List[Dict]) -> str:
        """
        Format budget alerts into a Telegram message with premium aesthetics.
        """
        if not alerts:
            return ""
        
        msg = "✨ **ESTADO DE TUS PRESUPUESTOS** ✨\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for alert in alerts:
            is_critical = alert['severity'] == 'critical'
            emoji = "🔴" if is_critical else "🟡"
            status_text = "¡Límite superado!" if is_critical else "Cerca del límite"
            
            msg += f"{emoji} **{alert['category']}**\n"
            msg += f"Status: _{status_text}_\n"
            msg += f"• Gastado: `${alert['spent']:,.2f}`\n"
            msg += f"• Límite: `${alert['budget']:,.2f}`\n"
            msg += f"• Progreso: `{alert['percentage']:.1f}%`\n"
            
            if alert['overage'] > 0:
                msg += f"⚠️ **Exceso**: `${alert['overage']:,.2f}`\n"
            
            msg += "\n"
        
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "📊 _Revisa los detalles en tu Dashboard Interactivo._"
        return msg
    
    def format_debt_reminder_message(self, debts: List[Dict]) -> str:
        """
        Format debt reminders into a Telegram message with premium aesthetics.
        """
        if not debts:
            return ""
        
        msg = "📈 **GESTIÓN DE COMPROMISOS** 📈\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        total_debts = sum(d['total'] for d in debts if d['type'] == 'Deuda')
        total_loans = sum(d['total'] for d in debts if d['type'] == 'Prestamo')
        
        if total_debts > 0:
            msg += f"🔴 **Cuentas por Pagar**\n"
            msg += f"Total: `${total_debts:,.2f}`\n"
            
            for debt in [d for d in debts if d['type'] == 'Deuda']:
                msg += f"• {debt['merchant']}: `${debt['total']:,.2f}`\n"
                msg += f"  _({debt['date']})_\n"
            msg += "\n"
        
        if total_loans > 0:
            msg += f"🟢 **Cuentas por Cobrar**\n"
            msg += f"Total: `${total_loans:,.2f}`\n"
            
            for loan in [d for d in debts if d['type'] == 'Prestamo']:
                msg += f"• {loan['merchant']}: `${loan['total']:,.2f}`\n"
                msg += f"  _({loan['date']})_\n"
            msg += "\n"
        
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "✅ _Marca como pagado desde el dashboard para actualizar tu balance._"
        return msg
    
    def format_weekly_summary_message(self, summary: Dict) -> str:
        """
        Format weekly summary into a premium Telegram message.
        """
        if not summary or summary.get('count', 0) == 0:
            return "📊 **RESUMEN SEMANAL**\n\nSin movimientos registrados esta semana. ¡Excelente control financiero! 🥂"
        
        msg = "💎 **RESUMEN SEMANAL DE GASTOS** 💎\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"📅 Período: _{summary['period']}_\n"
        msg += f"💰 Inversión Total: **${summary['total']:,.2f}**\n"
        msg += f"📝 Movimientos: `{summary['count']}`\n\n"
        
        # By category
        if summary['by_category']:
            msg += "📂 **Distribución por Categoría**\n"
            sorted_cats = sorted(summary['by_category'].items(), key=lambda x: x[1], reverse=True)
            for cat, amount in sorted_cats[:5]:
                msg += f"• {cat}: `${amount:,.2f}`\n"
            msg += "\n"
        
        # Top expenses
        if summary['top_expenses']:
            msg += "🔝 **Movimientos Destacados**\n"
            for i, expense in enumerate(summary['top_expenses'][:3], 1):
                msg += f"{i}. {expense['merchant']}: `${expense['total']:,.2f}`\n"
            msg += "\n"
        
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "📈 _Análisis detallado disponible en tu Panel Web._"
        return msg
