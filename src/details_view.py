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

        html = f"""
<!DOCTYPE html>
<html lang="es" class="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analíticos | ASISTENTE FINANCIERO</title>
    
    <!-- Restaurar tema ANTES del CSS para evitar flash -->
    <script>(function(){{var t=localStorage.getItem('theme')||'light';document.documentElement.className=t;}})();</script>

    <!-- Scripts & Styles -->
    <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="/static/html2canvas.min.js"></script>
    <script src="/static/liquidGL.js"></script>
    <!-- Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />

    <script id="tailwind-config">
        tailwind.config = {{
            darkMode: "class",
            theme: {{
                extend: {{
                    colors: {{
                        "primary": "#5631E8",
                        "secondary": "#006c49",
                        "background": "#f7f9fb",
                        "surface": "#ffffff",
                    }},
                    fontFamily: {{
                        "body": ["Inter", "sans-serif"],
                        "heading": ["Hanken Grotesk", "sans-serif"]
                    }}
                }}
            }}
        }}
    </script>

    <style>
        body {{ 
            font-family: 'Inter', sans-serif; 
            -webkit-font-smoothing: antialiased; 
            background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
            background-attachment: fixed;
            min-height: 100vh;
        }}

        html.dark body, .dark body {{
            background: linear-gradient(135deg, #020617 0%, #1e1b4b 50%, #4c1d95 100%) !important;
            background-attachment: fixed !important;
        }}

        .material-symbols-outlined {{ font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }}
        
        .glass-card {{
            backdrop-filter: blur(20px) saturate(180%) brightness(1.05);
            -webkit-backdrop-filter: blur(20px) saturate(180%) brightness(1.05);
            border: 1px solid rgba(255, 255, 255, 0.15);
            box-shadow:
                0 4px 24px rgba(0, 0, 0, 0.10),
                inset 0 1px 0 rgba(255, 255, 255, 0.18);
            position: relative;
            z-index: 10;
            transition: transform 0.2s ease-out, box-shadow 0.3s ease, border-color 0.3s ease;
        }}
        html:not(.dark) .glass-card {{
            background: rgba(255, 255, 255, 0.72);
            border-color: rgba(255, 255, 255, 0.60);
        }}
        html.dark .glass-card {{
            background: rgba(20, 27, 56, 0.62) !important;
            border-color: rgba(255, 255, 255, 0.07) !important;
            box-shadow:
                0 4px 32px rgba(0, 0, 0, 0.35),
                inset 0 1px 0 rgba(255, 255, 255, 0.06) !important;
        }}
        .glass-card:hover {{
            transform: translateY(-2px);
            border-color: rgba(86, 49, 232, 0.25);
        }}
        html.dark .glass-card:hover {{
            border-color: rgba(129, 140, 248, 0.2) !important;
        }}

        .chart-container {{
            position: relative;
            height: 380px;
            width: 100%;
        }}

        .toggle-active {{
            background: #5631E8;
            color: white;
            box-shadow: 0 4px 12px rgba(86, 49, 232, 0.3);
        }}
    </style>
</head>
<body class="text-slate-900 min-h-screen font-body transition-colors duration-300">

    <!-- Navbar -->
    <header class="fixed top-0 w-full h-16 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 z-50 flex items-center justify-between px-6">
        <div class="flex items-center gap-3">
            <a href="/dashboard" class="w-10 h-10 bg-slate-100 dark:bg-slate-800 rounded-xl flex items-center justify-center text-slate-600 dark:text-slate-400 hover:text-primary transition-colors">
                <span class="material-symbols-outlined">arrow_back</span>
            </a>
            <span class="font-heading text-lg font-bold tracking-tight">Análisis Inteligente</span>
        </div>
        <button onclick="toggleTheme()" class="p-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-slate-600 dark:text-slate-400" id="theme-btn">
            <span class="material-symbols-outlined">dark_mode</span>
        </button>
    </header>

    <main class="pt-24 pb-32 px-4 md:px-8 max-w-[1400px] mx-auto w-full">
        
        <!-- Summary Dashboard -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="glass-card liquidGL rounded-3xl p-6 shadow-sm border border-slate-200 dark:border-slate-800 flex flex-col items-center text-center">
                <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Promedio Semanal</span><div class="content">
                <span class="text-3xl font-heading font-black text-primary">${avg_weekly:,.0f}</span>
                <span class="text-[10px] text-slate-400 mt-2">Basado en registros actuales</span></div>
            </div>
            <div class="glass-card liquidGL rounded-3xl p-6 shadow-sm border border-rose-200 dark:border-rose-900/30 flex flex-col items-center text-center">
                <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Pico de Gasto</span><div class="content">
                <span class="text-xl font-heading font-bold text-rose-500 mb-1">{worst_week}</span>
                <span class="text-2xl font-heading font-black text-slate-900 dark:text-white">${weekly_spending.get(worst_week, 0):,.0f}</span></div>
            </div>
            <div class="glass-card liquidGL rounded-3xl p-6 shadow-sm border border-emerald-200 dark:border-emerald-900/30 flex flex-col items-center text-center">
                <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Eficiencia Máxima</span><div class="content">
                <span class="text-xl font-heading font-bold text-emerald-500 mb-1">{best_week}</span>
                <span class="text-2xl font-heading font-black text-slate-900 dark:text-white">${weekly_spending.get(best_week, 0):,.0f}</span></div>
            </div>
        </div>

        <!-- Weekly & Trending Analysis -->
        <div class="glass-card liquidGL rounded-[2rem] p-8 mb-8 shadow-sm">
            <div class="flex flex-wrap items-center justify-between gap-6 mb-10">
                <div>
                    <h2 class="text-2xl font-heading font-extrabold tracking-tight">Evolución de Finanzas</h2>
                    <p class="text-sm text-slate-500 dark:text-slate-400">Análisis comparativo por semana y tendencia de gasto</p>
                </div>
                <div class="flex bg-slate-100 dark:bg-slate-800 p-1.5 rounded-2xl">
                    <button id="btn-stack" onclick="switchView('stack')" class="px-5 py-2 text-xs font-bold rounded-xl transition-all toggle-active">Apilado</button>
                    <button id="btn-group" onclick="switchView('group')" class="px-5 py-2 text-xs font-bold rounded-xl transition-all text-slate-500">Agrupado</button>
                    <button id="btn-line" onclick="switchView('line')" class="px-5 py-2 text-xs font-bold rounded-xl transition-all text-slate-500">Líneas</button>
                </div>
            </div>
            <div class="chart-container">
                <canvas id="weeklyChart"></canvas>
            </div>
            <div id="weekly-legend" class="mt-8 flex flex-wrap justify-center gap-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                <!-- Legend items injected by JS -->
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <!-- Category Distribution -->
            <div class="glass-card liquidGL rounded-[2rem] p-8 shadow-sm">
                <h3 class="text-xl font-heading font-bold mb-6">Distribución por Categoría</h3>
                <div class="chart-container" style="height: 320px;">
                    <canvas id="pieChart"></canvas>
                </div>
            </div>

            <!-- Detailed Breakdown -->
            <div class="glass-card liquidGL rounded-[2rem] p-8 shadow-sm overflow-hidden flex flex-col">
                <h3 class="text-xl font-heading font-bold mb-6">Desglose de Gastos</h3>
                <div class="flex-grow space-y-3 overflow-y-auto pr-2 max-h-[320px]">
                    {"".join([f'''
                    <div class="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-800/50">
                        <div class="flex flex-col">
                            <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{c}</span>
                            <span class="font-bold text-slate-700 dark:text-slate-300">Registros: {cat_data[c]['count']}</span>
                        </div>
                        <span class="text-lg font-heading font-black text-primary">${v:,.2f}</span>
                    </div>
                    ''' for c, v in zip(cat_labels, cat_totals)])}
                </div>
            </div>

            <!-- Daily Trends -->
            <div class="lg:col-span-2 glass-card liquidGL rounded-[2rem] p-8 shadow-sm">
                <h3 class="text-xl font-heading font-bold mb-6">Tendencia Diaria de Movimientos</h3>
                <div class="chart-container" style="height: 300px;">
                    <canvas id="lineChart"></canvas>
                </div>
            </div>
        </div>
    </main>

    <script>
        // Chart Configuration & Logic
        const isDark = () => document.documentElement.classList.contains('dark');
        const getTextColor = () => isDark() ? '#94A3B8' : '#64748B';
        const getGridColor = () => isDark() ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)';

        const weekLabels   = {json.dumps(week_labels_ordered)};
        const weeklyTotals = {json.dumps(weekly_totals)};
        const catDatasets  = {json.dumps(cat_week_datasets)};
        const catColors    = {json.dumps(category_colors[:len(top_cats)])};

        // Initialize Weekly Chart
        const weeklyCtx = document.getElementById('weeklyChart').getContext('2d');
        const weeklyChartConfig = {{
            type: 'bar',
            data: {{
                labels: weekLabels,
                datasets: [
                    ...catDatasets.map(d => ({{ 
                        ...d, 
                        type: 'bar', 
                        stack: 'stack0',
                        borderRadius: 6,
                        barThickness: 32
                    }})),
                    {{
                        label: 'Tendencia Total',
                        data: weeklyTotals,
                        type: 'line',
                        borderColor: '#5631E8',
                        borderWidth: 3,
                        pointBackgroundColor: '#5631E8',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 5,
                        tension: 0.4,
                        order: -1
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        padding: 16,
                        backgroundColor: '#1E293B',
                        titleFont: {{ family: 'Hanken Grotesk', size: 14, weight: 'bold' }},
                        bodyFont: {{ family: 'Inter', size: 12 }},
                        cornerRadius: 12
                    }}
                }},
                scales: {{
                    x: {{ stacked: true, grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: getTextColor() }} }},
                    y: {{ stacked: true, grid: {{ color: getGridColor() }}, border: {{ display: false }}, ticks: {{ color: getTextColor() }} }}
                }}
            }}
        }};

        const weeklyChart = new Chart(weeklyCtx, weeklyChartConfig);

        // Legend Generation
        const legendEl = document.getElementById('weekly-legend');
        catDatasets.forEach((ds, i) => {{
            const item = document.createElement('div');
            item.className = 'flex items-center gap-2';
            item.innerHTML = `<span class="w-3 h-3 rounded-full" style="background:${{catColors[i]}}"></span>${{ds.label}}`;
            legendEl.appendChild(item);
        }});

        function switchView(view) {{
            const buttons = ['stack', 'group', 'line'];
            buttons.forEach(b => {{
                const el = document.getElementById('btn-' + b);
                if (b === view) el.classList.add('toggle-active');
                else el.classList.remove('toggle-active', 'text-slate-500');
                if (b !== view) el.classList.add('text-slate-500');
            }});

            weeklyChart.data.datasets.forEach(ds => {{
                if (ds.type === 'line' && ds.label === 'Tendencia Total') return;
                
                if (view === 'stack') {{
                    ds.type = 'bar';
                    ds.stack = 'stack0';
                    weeklyChart.options.scales.x.stacked = true;
                    weeklyChart.options.scales.y.stacked = true;
                }} else if (view === 'group') {{
                    ds.type = 'bar';
                    ds.stack = null;
                    weeklyChart.options.scales.x.stacked = false;
                    weeklyChart.options.scales.y.stacked = false;
                }} else {{
                    ds.type = 'line';
                    ds.stack = null;
                    ds.fill = false;
                    weeklyChart.options.scales.x.stacked = false;
                    weeklyChart.options.scales.y.stacked = false;
                }}
            }});
            weeklyChart.update();
        }}

        // Other Charts
        new Chart(document.getElementById('pieChart'), {{
            type: 'doughnut',
            data: {{
                labels: {json.dumps(cat_labels)},
                datasets: [{{
                    data: {json.dumps(cat_totals)},
                    backgroundColor: ['#5631E8', '#818CF8', '#C7D2FE', '#FCD34D', '#10B981', '#F87171', '#60A5FA', '#A78BFA'],
                    borderWidth: 0,
                    cutout: '80%'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ position: 'bottom', labels: {{ usePointStyle: true, padding: 20, color: getTextColor(), font: {{ size: 10, weight: 'bold' }} }} }}
                }}
            }}
        }});

        new Chart(document.getElementById('lineChart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps(dates)},
                datasets: [{{
                    label: 'Gasto Diario',
                    data: {json.dumps(daily_vals)},
                    borderColor: '#5631E8',
                    backgroundColor: 'rgba(86, 49, 232, 0.05)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 6,
                    borderWidth: 3
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    x: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: getTextColor(), maxRotation: 0, autoSkip: true, maxTicksLimit: 10 }} }},
                    y: {{ grid: {{ color: getGridColor() }}, border: {{ display: false }}, ticks: {{ color: getTextColor() }} }}
                }}
            }}
        }});

        // Theme Toggle
        function toggleTheme() {{
            const html = document.documentElement;
            const next = html.classList.contains('dark') ? 'light' : 'dark';
            html.className = next;
            localStorage.setItem('theme', next);
            updateThemeIcon(next);
            updateChartsTheme();
        }}

        function updateThemeIcon(theme) {{
            const btn = document.getElementById('theme-btn');
            btn.innerHTML = `<span class="material-symbols-outlined">${{theme === 'dark' ? 'light_mode' : 'dark_mode'}}</span>`;
        }}

        function updateChartsTheme() {{
            const textColor = getTextColor();
            const gridColor = getGridColor();
            
            Chart.instances.forEach(chart => {{
                if (chart.options.scales) {{
                    if (chart.options.scales.x) chart.options.scales.x.ticks.color = textColor;
                    if (chart.options.scales.y) {{
                        chart.options.scales.y.ticks.color = textColor;
                        chart.options.scales.y.grid.color = gridColor;
                    }}
                }}
                if (chart.options.plugins && chart.options.plugins.legend) {{
                    chart.options.plugins.legend.labels.color = textColor;
                }}
                chart.update();
            }});
        }}

        // Init
        (function() {{
            const theme = localStorage.getItem('theme') || 'light';
            document.documentElement.className = theme;
            updateThemeIcon(theme);
            setTimeout(updateChartsTheme, 100);
            // Init LiquidGL — disabled: CSS glassmorphism is used instead
            // liquidGL causes mirror/refraction artifacts on dark backgrounds
        }})();
    </script>
</body>
</html>
"""
        return html
