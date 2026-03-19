import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "expenses.db")


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                amount      REAL    NOT NULL,
                merchant    TEXT,
                category    TEXT    NOT NULL,
                date        TEXT,
                image_path  TEXT,
                notes       TEXT,
                created_at  TEXT    DEFAULT (datetime('now'))
            )
        """)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_expense(amount: float, merchant: str, category: str,
                date: str, image_path: str, notes: str = "") -> dict:
    with get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO expenses (amount, merchant, category, date, image_path, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (amount, merchant, category, date, image_path, notes),
        )
        row = conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)


def get_expenses() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM expenses ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def delete_expense(expense_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT image_path FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
        if not row:
            return False
        # Remove image file if it exists
        image_path = Path(row["image_path"])
        if image_path.exists():
            image_path.unlink()
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        return True


def get_stats() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT category,
                      COUNT(*)    AS count,
                      SUM(amount) AS total
               FROM expenses
               GROUP BY category
               ORDER BY total DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
