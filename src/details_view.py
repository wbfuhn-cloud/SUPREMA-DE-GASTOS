import json
from datetime import datetime, timedelta
from collections import defaultdict

class DetailsViewGenerator:
    @staticmethod
    def generate_html(expenses, categories=None):
        if not categories:
            categories = ['ALIMENTOS', 'TRANSPORTE', 'HOGAR', 'SERVICIOS', 'PERSONAL',
                          'ENTRETENIMIENTO', 'SALUD', 'OTRO']

        # ───── Procesamiento de datos ─────
        cat_data = defaultdict(lambda: {'total': 0.0, 'count': 0, 'merchants': defaultdict(float)})
        daily_spending = defaultdict(float)
        weekly_spending = defaultdict(float)             # week_label -> total
        weekly_by_cat = defaultdict(lambda: defaultdict(float))  # week_label -> cat -> total
        weekly_counts = defaultdict(int)

        week_labels_ordered = []
        seen_weeks = set()

        for e in expenses:
            cat = str(e.get('category', 'OTRO')).upper()
            amount = float(e.get('total', 0))
            merchant = e.get('merchant', 'Unknown')
            date_str = e.get('date', '')

            cat_data[cat]['total'] += amount
            cat_data[cat]['count'] += 1
            cat_data[cat]['merchants'][merchant] += amount

            if date_str:
                daily_spending[date_str] += amount
                try:
                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                    # Label: e.g. "Sem 1\n(Mar 3-9)"
                    iso = dt.isocalendar()
                    week_start = dt - timedelta(days=dt.weekday())
                    week_end   = week_start + timedelta(days=6)
                    week_label = f"Sem {iso[1]} ({week_start.strftime('%b %d')} - {week_end.strftime('%b %d')})"
                    weekly_spending[week_label] += amount
                    weekly_by_cat[week_label][cat] += amount
                    weekly_counts[week_label] += 1
                    if week_label not in seen_weeks:
                        seen_weeks.add(week_label)
                        week_labels_ordered.append(week_label)
                except Exception:
                    pass

        # Sort week labels chronologically (they already come out in order, but just in case)
        week_labels_ordered = sorted(seen_weeks, key=lambda w: w)

        # Top 5 categories by total spend for the stacked chart
        sorted_cats = sorted(cat_data.items(), key=lambda x: x[1]['total'], reverse=True)
        cat_labels = [c for c, d in sorted_cats]
        cat_totals = [d['total'] for c, d in sorted_cats]
        top_cats = cat_labels[:6]  # Only top 6 for readability

        # Prepare stack data per top category
        category_colors = [
            '#5631E8', '#818CF8', '#10B981', '#FCD34D', '#F87171', '#60A5FA',
            '#A78BFA', '#34D399', '#FB923C', '#38BDF8'
        ]
        cat_week_datasets = []
        for i, cat in enumerate(top_cats):
            cat_values = [weekly_by_cat[w].get(cat, 0) for w in week_labels_ordered]
            cat_week_datasets.append({
                'label': cat.title(),
                'data': cat_values,
                'backgroundColor': category_colors[i % len(category_colors)],
                'borderRadius': 4,
                'stack': 'stack0',
            })

        # Weekly totals (for trend line overlay)
        weekly_totals = [weekly_spending[w] for w in week_labels_ordered]

        # Weekly summary stats
        best_week  = min(weekly_spending, key=lambda k: weekly_spending[k]) if weekly_spending else '-'
        worst_week = max(weekly_spending, key=lambda k: weekly_spending[k]) if weekly_spending else '-'
        avg_weekly = (sum(weekly_totals) / len(weekly_totals)) if weekly_totals else 0

        # Daily chart data
        sorted_daily = sorted(daily_spending.items())
        dates     = [d for d, v in sorted_daily]
        daily_vals = [v for d, v in sorted_daily]

        return {
            'dates': dates,
            'week_labels_ordered': week_labels_ordered,
            'weekly_totals': weekly_totals,
            'worst_week': worst_week,
            'cat_labels': cat_labels,
            'cat_totals': cat_totals,
            'cat_week_datasets': cat_week_datasets,
            'daily_vals': daily_vals,
            'best_week': best_week,
            'cat_data': cat_data,
            'category_colors': category_colors,
            'weekly_spending': weekly_spending,
            'avg_weekly': avg_weekly,
        }
