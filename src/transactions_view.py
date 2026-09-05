import json
from datetime import datetime
from collections import defaultdict

class TransactionsViewGenerator:

    @staticmethod
    def _build_row(e, all_cats=None):
        if all_cats is None:
            all_cats = []
        eid = e.get('id')
        is_unconf = e.get('status') == 'unconfirmed'
        
        if is_unconf:
            row_bg = "bg-purple-200/80 dark:bg-purple-800/50 shadow-lg shadow-purple-500/30 border-b border-purple-300 dark:border-purple-600 relative z-10"
        else:
            row_bg = "border-b border-slate-100 dark:border-slate-800/40"
            
        row_hover = "hover:bg-slate-50/80 dark:hover:bg-slate-800/40"
        total_val    = e.get('total', 0)
        date_raw     = str(e.get('date', ''))
        date_label   = TransactionsViewGenerator._format_date_es(date_raw) if date_raw else '—'
        merchant_val = str(e.get('merchant', '')).upper()
        category_val = str(e.get('category', '')).upper()
        type_val     = str(e.get('type', ''))
        details_val  = str(e.get('details', '')).replace('<', '&lt;').replace('>', '&gt;')

        btn_conf = ""
        if is_unconf:
            btn_conf = (
                '<button class="bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 '
                'p-1.5 rounded-lg mr-1 hover:bg-emerald-200 transition-colors" '
                'onclick="confirmExpense(' + str(eid) + ', this)">&#10003;</button>'
            )

        r = '<tr class="tx-row ' + row_bg + ' ' + row_hover + '" data-amount="' + str(total_val) + '">'
        r += '<td class="p-3 text-[10px] font-bold text-slate-400">#' + str(eid) + '</td>'
        r += (
            '<td class="p-3"><div class="date-wrapper" onclick="this.querySelector(\'.date-hidden\').showPicker()">'
            '<span class="material-symbols-outlined date-icon">calendar_month</span>'
            '<span class="date-label">' + date_label + '</span>'
            '<input type="date" class="date-hidden" value="' + date_raw + '"'
            ' onchange="updateDateDisplay(this); updateExpense(' + str(eid) + ', \'date\', this.value)">'
            '</div></td>'
        )
        r += (
            '<td class="p-3"><input type="text" class="form-input text-xs font-bold" '
            'value="' + merchant_val + '" data-field="merchant"'
            ' onchange="updateExpense(' + str(eid) + ', \'merchant\', this.value)"></td>'
        )
        
        # Select de categoría diferido (lazy loaded en click)
        cat_display = category_val.title() if category_val else '(Sin categoría)'
        cat_select = (
            '<select class="form-input text-xs cat-select" data-field="category" data-id="' + str(eid) + '" '
            'data-val="' + category_val + '" onpointerdown="ensureCatOptions(this)" onfocus="ensureCatOptions(this)" '
            'onchange="handleCatSelectChange(this, ' + str(eid) + ')">'
            '<option value="' + category_val + '" selected>' + cat_display + '</option>'
            '</select>'
        )
        
        r += (
            '<td class="p-3">' + cat_select + '</td>'
        )
        r += (
            '<td class="p-3">'
            '<select class="form-input text-xs" data-field="type" onchange="updateExpense(' + str(eid) + ', \'type\', this.value)">'
            '<option value="Normal"' + (' selected' if type_val == 'Normal' else '') + '>Normal</option>'
            '<option value="Deuda"' + (' selected' if type_val == 'Deuda' else '') + '>Deuda</option>'
            '<option value="Prestamo"' + (' selected' if type_val == 'Prestamo' else '') + '>Préstamo</option>'
            '</select>'
            '</td>'
        )
        r += (
            '<td class="p-3"><textarea class="form-input text-xs resize-none" rows="2" '
            'style="min-width:140px" data-field="details"'
            ' onchange="updateExpense(' + str(eid) + ', \'details\', this.value)">'
            + details_val + '</textarea></td>'
        )
        try:
            formatted_total = f"${float(total_val):,.2f}"
        except (ValueError, TypeError):
            formatted_total = f"${total_val}"

        r += (
            '<td class="p-3"><input type="text" '
            'class="form-input text-xs text-right font-bold amount-input"'
            ' data-raw="' + str(total_val) + '"'
            ' value="' + formatted_total + '"'
            ' onfocus="this.value=this.dataset.raw; this.select()"'
            ' onblur="var n=parseFloat(this.value)||0; this.dataset.raw=n; '
            'this.closest(\'tr\').dataset.amount=n; '
            'this.value=formatCurrency(n); updateExpense(' + str(eid) + ', \'total\', n)"'
            '></td>'
        )
        r += (
            '<td class="p-3 text-center">' + btn_conf +
            '<button class="bg-rose-100 dark:bg-rose-900/40 text-rose-600 p-1.5 rounded-lg '
            'hover:bg-rose-200 transition-colors" '
            'onclick="deleteExpense(' + str(eid) + ', this)">&#x2715;</button></td>'
        )
        r += '</tr>'
        return r

    @staticmethod
    def _format_date_es(d_str: str) -> str:
        try:
            dt = datetime.strptime(d_str[:10], '%Y-%m-%d')
            ms = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC']
            return "{:02d} {} {}".format(dt.day, ms[dt.month - 1], dt.year)
        except Exception:
            return d_str

    @staticmethod
    def generate_html(expenses: list, selected_year=None, available_years=None) -> str:

        # ── Year tabs ───────────────────────────────────────────────────────
        years_html = ""
        active_cls = 'bg-primary text-white shadow-md'
        inactive_cls = 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
        # "Todos" tab
        cls = active_cls if selected_year is None else inactive_cls
        years_html += '<a href="/transactions?year=all" class="px-4 py-2 rounded-xl text-xs font-bold transition-colors ' + cls + '">TODOS</a>'
        if available_years:
            for y in available_years:
                cls = active_cls if selected_year == y else inactive_cls
                years_html += '<a href="/transactions?year=' + str(y) + '" class="px-4 py-2 rounded-xl text-xs font-bold transition-colors ' + cls + '">' + str(y) + '</a>'

        # ── Generate all_cats FIRST ──
        all_cats = sorted(set(
            str(e.get('category', '')).strip().upper()
            for e in expenses if e.get('category')
        ))
        cats_json = json.dumps(all_cats)

        # ── Group by year if showing all ────────────────────────────────────
        rows_html = ""
        if selected_year is None and available_years:
            by_year = defaultdict(list)
            for e in expenses:
                y = str(e.get('date', ''))[:4]
                by_year[y].append(e)
            for year_key in sorted(by_year.keys(), reverse=True):
                year_expenses = by_year[year_key]
                year_total = sum(float(e.get('total', 0)) for e in year_expenses)
                rows_html += (
                    '<tr class="year-separator"><td colspan="8">'
                    '<div class="flex items-center justify-between px-2 py-3">'
                    '<span class="text-sm font-black text-primary tracking-widest">AÑO ' + year_key + '</span>'
                    '<span class="text-sm font-bold text-slate-400">$' + '{:,.2f}'.format(year_total) + '</span>'
                    '</div></td></tr>'
                )
                for e in year_expenses:
                    rows_html += TransactionsViewGenerator._build_row(e, all_cats)
        else:
            for e in expenses:
                rows_html += TransactionsViewGenerator._build_row(e, all_cats)

        # ── Category options (filter) ────────────────────────────────────────────────
        cat_opts = '<option value="">Categorías</option>' + "".join(
            ['<option value="' + c + '">' + c.title() + '</option>' for c in all_cats]
        )

        return {
            'years_html': years_html,
            'cat_opts': cat_opts,
            'rows_html': rows_html,
            'cats_json': cats_json
        }
