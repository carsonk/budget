#!/usr/bin/python3

import argparse
import babel.dates
import babel.numbers
import datetime
import dateutil.parser
import json
import math
import os.path
import sqlite3
from tabulate import tabulate
from yoyo import read_migrations, get_backend

script_path = os.path.realpath(__file__)
script_dir = os.path.dirname(script_path)

db_path = os.path.join(script_dir, "db.sqlite3")
settings_path = os.path.join(script_dir, "settings.json")
db = None

take_home_salary = None 
start_date = None
end_date = None

def main():
    load_settings()

    parser = get_argparser()
    args = parser.parse_args()

    backend = get_backend("sqlite:///%s" % db_path)
    migrations = read_migrations(os.path.join(script_dir, 'migrations'))
    backend.apply_migrations(backend.to_apply(migrations))

    global db
    db = sqlite3.connect(db_path)

    def cpg(sub, sub_alias):
        return args.prog_sub == sub or args.prog_sub == sub_alias

    if cpg("add", "a"):
        add_transaction(args.cost, args.name, args.monthly, args.fixed)
    elif cpg("list", "l"):
        list_transactions()
    elif cpg("update", "u"):
        update_transaction(args.name, args.newname, args.cost, args.monthly, args.fixed)
    elif cpg("monthly", "m"):
        if args.monthly_sub == "add":
            create_monthly_category(args.name, args.costperitem, args.numitemspermonth)
        else:
            list_monthly_expenses()
    elif cpg("fixed", "f"):
        if args.fixed_sub == "add":
            create_fixed_category(args.name, args.cost)
        else:
            list_fixed_expenses()
    elif cpg("totals", "t"):
        print_totals()
    else:
        print_dashboard()

def load_settings():
    global take_home_salary, start_date, end_date

    with open(settings_path, "r") as f:
        settings = json.load(f)

    take_home_salary = settings["salary"]
    start_date = dateutil.parser.parse(settings["start_date"]).date()
    end_date = dateutil.parser.parse(settings["end_date"]).date()

def print_dashboard():
    print_totals()
    print("")
    list_monthly_expenses()
    print("")
    list_fixed_expenses()

def print_totals():
    (sum_spent, total_days, passed_days, daily_gain, percent_passed, percent_spent) = get_totals()

    print("Total Spent: \033[1m%s\033[0m (%s)" % (fmtdlr(sum_spent), percent_spent))
    print("Days Passed: %s (%.1f%%)" % (passed_days, percent_passed))

def get_totals():
    curs = db.cursor()
    sql = "SELECT SUM(cost) FROM transactions"
    sum_spent = curs.execute(sql).fetchone()[0]
    curs.close()

    (total_days, passed_days, daily_gain, percent_passed) = get_time_passed()
    
    percent_spent = percent_of(sum_spent, take_home_salary) 

    return (sum_spent, total_days, passed_days, daily_gain, percent_passed, percent_spent)

def get_time_passed():
    total_days = (end_date - start_date).days
    passed_days = (datetime.date.today() - start_date).days
    daily_gain = round((1 / total_days) * 100, 2)
    percent_passed = round((passed_days / total_days) * 100, 2)
    return (total_days, passed_days, daily_gain, percent_passed)

def get_argparser():
    parser = argparse.ArgumentParser(prog='budget', description='Simple budget tracker')

    subs = parser.add_subparsers(help='sub-command help', dest='prog_sub')

    add_sub = subs.add_parser('add', help='add a transaction', aliases=['a'])
    add_sub.add_argument('cost', help='cost of the transaction')
    add_sub.add_argument('-n', '--name', help='name of the transaction')
    add_sub.add_argument('-m', '--monthly', help='monthly category to associate with')
    add_sub.add_argument('-f', '--fixed', help='fixed category to associate with')

    remove_sub = subs.add_parser('remove', help='remove a transaction', aliases=['r'])
    remove_sub.add_argument('name', help='name or id of transaction to remove')

    update_sub = subs.add_parser('update', help='update a transaction', aliases=['u'])
    update_sub.add_argument('name', help='name of transaction to update')
    update_sub.add_argument('-n', '--newname', help='new name of transaction')
    update_sub.add_argument('-c', '--cost', type=int, help='new cost of transaction')
    update_sub.add_argument('-m', '--monthly', help='monthly category to use')
    update_sub.add_argument('-f', '--fixed', help='fixed category to use')

    import_sub = subs.add_parser('import', help='import a Chase CSV file', aliases=['i'])
    import_sub.add_argument('csvfile', help='path to Chase CSV exported transaction')
    import_sub.add_argument('-m', '--monthly', help='categorize all given items under'
        'this monthly category')
    import_sub.add_argument('-f', '--fixed', help='category all given items under'
        'this fixed category')

    list_sub = subs.add_parser('list', help='list transactions', aliases=['l'])

    monthly_sub = subs.add_parser('monthly', help='manage monthly transactions', aliases=['m'])
    monthly_add_sub = monthly_sub.add_subparsers(dest='monthly_sub').add_parser('add', aliases=['a'])
    monthly_add_sub.add_argument('name')
    monthly_add_sub.add_argument('costperitem', type=int)
    monthly_add_sub.add_argument('numitemspermonth', type=int)

    fixed_sub = subs.add_parser('fixed', help='manage fixed transactions', aliases=['f'])
    fixed_add_sub = fixed_sub.add_subparsers(dest='fixed_sub').add_parser('add', aliases=['a'])
    fixed_add_sub.add_argument('name')
    fixed_add_sub.add_argument('cost', type=int)
    fixed_add_sub.add_argument('spent', nargs='?', default=0, type=int)

    totals_sub = subs.add_parser('totals', help='print totals', aliases=['t'])

    return parser

def add_transaction(cost, name=None, monthly_id=None, fixed_id=None):
    curs = db.cursor()

    if monthly_id is not None:
        (monthly_id, empty_name) = get_monthly_id(monthly_id)
    elif fixed_id is not None:
        (fixed_id, empty_name) = get_fixed_id(fixed_id)

    if name is None:
        if empty_name is None:
            print("Please provide a name, or something to derive a useful name from!")
            return

        name = 'Existing' + empty_name + '-' + str(datetime.date.today())

    sql = """
        INSERT INTO transactions (name, cost, monthly_expense_id, fixed_expense_id, time)
        VALUES (?, ?, ?, ?, ?)
    """
    params = (name, cost, monthly_id, fixed_id, datetime.datetime.now())
    curs.execute(sql, params)

    db.commit()
    curs.close()

def update_transaction(name, new_name=None, cost=None, monthly_id=None, fixed_id=None):
    curs = db.cursor()

    (t_id, t_name) = get_transaction_id(name)
    if t_id is None:
        print("Could not get transaction ID for that given name")
        return None

    params = []

    sql = "UPDATE transactions SET %s WHERE id = ?"
    set_vals = ""

    if new_name is not None:
        set_vals += " name = ?,"
        params.append(new_name)

    if cost is not None:
        set_vals += " cost = ?,"
        params.append(int(cost))

    if monthly_id is not None:
        set_vals += " monthly_expense_id = ?, fixed_expense_id = NULL,"
        (monthly_id, _) = get_monthly_id(monthly_id)
        params.append(monthly_id)
    elif fixed_id is not None:
        set_vals += " fixed_expense_id = ?, monthly_expense_id = NULL,"
        (fixed_id, _) = get_fixed_id(fixed_id)
        params.append(fixed_id)

    params.append(t_id)

    if len(set_vals) > 0:
        set_vals = set_vals[:-1] # take off trailing comma
        sql = sql % set_vals
        params = tuple(params)
        curs.execute(sql, params)

    db.commit()
    curs.close()

def list_transactions():
    curs = db.cursor()

    sql = """
        SELECT t.id, t.name, t.cost, m.name as monthly_name, f.name as fixed_name, t.time 
        FROM transactions t
        LEFT JOIN monthly_expenses m ON m.id = t.monthly_expense_id
        LEFT JOIN fixed_expenses f ON f.id = t.fixed_expense_id
        ORDER BY time DESC
        LIMIT 15
    """
    res = curs.execute(sql)

    rows = res.fetchall()
    table_data = []
    for row in rows:
        (row_id, name, cost, monthly_name, fixed_name, time) = row

        name = "%s (%d)" % (name, row_id)

        if monthly_name is not None:
            category = monthly_name
        elif fixed_name is not None:
            category = fixed_name
        else:
            category = "[None]"

        table_data.append([name, cost, category, time])

    headers = ['Name', 'Cost', 'Category', 'Time']
    print(tabulate(table_data, headers=headers))

    curs.close()

def get_monthly_id(name):
    return _get_id_for_expense("monthly_expenses", name)

def get_fixed_id(name):
    return _get_id_for_expense("fixed_expenses", name)

def get_transaction_id(name):
    return _get_id_for_expense("transactions", name)

def _get_id_for_expense(table_name, name):
    curs = db.cursor()

    try:
        name_int = int(name)
        is_intable = True
    except ValueError:
        is_intable = False

    row = None
    if is_intable:
        sql = "SELECT id, name FROM %s WHERE id = ?" % table_name
        res = curs.execute(sql, (name_int,))

        if res.arraysize > 0:
            row = res.fetchone()

    if row is None:
        sql = "SELECT id, name FROM %s WHERE name LIKE ?" % table_name
        args = ('%' + name + '%',)
        res = curs.execute(sql, ('%' + name + '%',))

        if res.arraysize == 1:
            row = res.fetchone()
        elif res.arraysize > 1:
            print("Multiple line items were found with that search name!")
            row = None
        else:
            print("No items were found with that search name!")
            row = None

    if row is None:
        print("Nothing was found!")
        return None

    curs.close()

    return (int(row[0]), row[1])


def create_monthly_category(name, cost_per_item, num_items_per_month):
    curs = db.cursor()

    sql = """INSERT INTO monthly_expenses (
        name, cost_per_item, num_items_per_month, last_updated
    ) VALUES (?, ?, ?, ?)"""
    now = datetime.datetime.now()
    params = (name, cost_per_item, num_items_per_month, now)

    curs.execute(sql, params)
    db.commit()
    curs.close()

def list_monthly_expenses():
    curs = db.cursor()
    sql = """ 
        SELECT 
            m.name, cost_per_item, num_items_per_month,
            (cost_per_item * num_items_per_month) as total_per_month,
            (cost_per_item * num_items_per_month * 12) as total_per_year,
            SUM(t.cost) as spent
        FROM monthly_expenses m
        LEFT JOIN transactions t ON t.monthly_expense_id = m.id
        GROUP BY m.id
        ORDER BY total_per_year DESC
    """
    res = curs.execute(sql)

    (_, _, _, daily_gain, percent_passed, _) = get_totals()
    print("DAILY GAIN: %.2f / PERCENT PASSED: %.2f" % (daily_gain, percent_passed))

    rows = res.fetchall()
    table_data = []
    for row in rows:
        (name, cost_per_item, num_items_per_month, total_per_month, \
                total_per_year, spent) = row

        percent_income = percent_of(total_per_year, take_home_salary)

        percent_spent = ((spent or 0) / total_per_year) * 100
        cut_days = (percent_spent - percent_passed) / daily_gain
        cut_days = math.ceil(cut_days)
        ahead = cut_days < 0
        behind = cut_days > 0

        if cut_days < 0:
            cut_days *= -1

        cut_time = babel.dates.format_timedelta(datetime.timedelta(days=cut_days), locale='en_US', \
                threshold=2)

        if ahead:
            cut_days = "\033[32m+%s\033[0m" % cut_time
        elif behind:
            cut_days = "\033[31m-%s\033[0m" % cut_time
        else:
            cut_days = cut_time

        percent_spent = "%.2f%%" % percent_spent

        table_data.append([
            name, fmtdlr(cost_per_item), num_items_per_month, fmtdlr(total_per_month),
            fmtdlr(total_per_year), percent_income, fmtdlr(spent), percent_spent, cut_days
        ])

    headers = [
        'Name', 'AvgCost/Item', 'Num/Mo', 'Ttl/Mo', 'Ttl/Yr', '%Income', 'Spent', '%Spent', 'Cut'
    ]
    print(tabulate(table_data, headers=headers))

    curs.close()

def list_fixed_expenses():
    curs = db.cursor()
    sql = """ 
        SELECT f.name, f.cost as fixed_cost, SUM(t.cost)
        FROM fixed_expenses f 
        LEFT JOIN transactions t ON t.fixed_expense_id = f.id
        GROUP BY f.id
        ORDER BY f.cost DESC
    """
    res = curs.execute(sql)

    rows = res.fetchall()
    table_data = []
    for row in rows:
        (name, cost, spent) = row
        table_data.append([name, fmtdlr(cost), fmtdlr(spent)])

    headers = ['Name', 'Cost', 'Spent']
    print(tabulate(table_data, headers=headers))

    curs.close()

def fmtdlr(dollar_amt, d=False):
    dollar_amt = dollar_amt or 0
    return babel.numbers.format_currency(dollar_amt, 'USD', u'$#,##0', currency_digits=d)

def percent_of(val, total):
    dec = round((val / total) * 100, 2)
    return "%.2f%%" % dec

def create_fixed_category(name, cost):
    curs = db.cursor()

    sql = """INSERT INTO fixed_expenses (
        name, cost, last_updated
    ) VALUES (?, ?, ?)"""
    now = datetime.datetime.now()
    params = (name, cost, now)

    curs.execute(sql, params)
    db.commit()
    curs.close()

if __name__ == "__main__":
    main()

