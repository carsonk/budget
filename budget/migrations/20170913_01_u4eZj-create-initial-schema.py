"""
Create initial schema
"""

from yoyo import step

__depends__ = {}

steps = [
    step("""
        CREATE TABLE monthly_expenses (
            id INTEGER PRIMARY KEY,
            name TEXT,
            cost_per_item INT NOT NULL,
            num_items_per_month INT NOT NULL,
            last_updated DATETIME
        )
        """,
        "DROP TABLE monthly_expenses"
    ),
    step("""
        CREATE TABLE fixed_expenses (
            id INTEGER PRIMARY KEY,
            name TEXT,
            cost INT NOT NULL,
            last_updated DATETIME
        )
        """,
        "DROP TABLE fixed_expenses"
    ),
    step("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY,
            name TEXT,
            monthly_expense_id INT REFERENCES monthly_expenses(id),
            fixed_expense_id INT REFERENCES fixed_expenses(id),
            cost INTEGER NOT NULL,
            time DATETIME
        )
        """,
        "DROP TABLE transactions"
    )
]
