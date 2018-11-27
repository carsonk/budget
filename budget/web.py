#!/usr/bin/env python3

from flask import Flask, render_template, g

import budget
from budget import fmtdlr

def get_db():
    if 'db' not in g:
        g.db = budget.get_db_connection()

    return g.db


def create_app():
    app = Flask(__name__)

    app.logger.debug('Creating app')
    budget.load_settings()

    @app.route('/')
    def dashboard():
        get_db()

        t = budget.get_totals(g.db)
        t["sum_spent"] = fmtdlr(t["sum_spent"])
        t["total_unallocated"] = fmtdlr(budget.take_home_salary -
            t["allocated_per_period"])

        context = {
            'take_home_salary': fmtdlr(budget.take_home_salary),
            'totals': t,
            'monthly_expenses': budget.list_monthly_expenses(g.db),
            'fixed_expenses': budget.list_fixed_expenses(g.db)
        }
        return render_template('dashboard.html', **context)

    @app.route('/monthly/add', methods=['POST'])
    def add_monthly_exp():
        get_db()
        return render_template('add_monthly.html')

    @app.route('/fixed/add', methods=['POST'])
    def add_fixed_exp():
        get_db()
        return render_template('add_fixed.html')

    return app


if __name__ == "__main__":
    app = create_app()

    use_debugger = app.debug
    
    app.run(use_debugger=use_debugger, debug=app.debug,
            use_reloader=use_debugger)
