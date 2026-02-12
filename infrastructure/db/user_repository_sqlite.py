from __future__ import annotations

import sqlite3
from typing import List, Optional

from domain.models import User
from domain.repositories import UserRepository


class SqliteUserRepository(UserRepository):
    """
    SQLite-backed implementation of `UserRepository`.

    This repository owns the `users` table and maps rows to the `User`
    domain model. It is self-initialising: the table is created if needed.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_table()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _ensure_table(self) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    balance INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()

    @staticmethod
    def _to_domain(row: sqlite3.Row) -> User:
        return User(
            id=str(row[0]),
            first_name=row[1],
            last_name=row[2],
            balance=int(row[3]),
        )

    def get_user(self, user_id: str) -> Optional[User]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, first_name, last_name, balance FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._to_domain(row)

    def get_all_users(self) -> List[User]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, first_name, last_name, balance FROM users")
            rows = cur.fetchall()
            return [self._to_domain(row) for row in rows]

    def add_user(self, user: User) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO users (id, first_name, last_name, balance)
                VALUES (?, ?, ?, ?)
                """,
                (user.id, user.first_name, user.last_name, user.balance),
            )
            conn.commit()

    def update_balance(self, user_id: str, delta: int) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE users
                SET balance = balance + ?
                WHERE id = ?
                """,
                (delta, user_id),
            )
            conn.commit()

