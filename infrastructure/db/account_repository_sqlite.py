from __future__ import annotations

import sqlite3
from typing import Optional

from domain.models import Account
from domain.repositories import AccountRepository


class SqliteAccountRepository(AccountRepository):
    """
    SQLite-backed implementation of `AccountRepository`.

    Manages the `accounts` table, which stores usernames and password
    hashes for platform-wide identities.
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
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL
                )
                """
            )
            conn.commit()

    @staticmethod
    def _to_domain(row: sqlite3.Row) -> Account:
        return Account(
            id=str(row[0]),
            username=row[1],
            password_hash=row[2],
        )

    def get_by_username(self, username: str) -> Optional[Account]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, username, password_hash FROM accounts WHERE username = ?",
                (username,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._to_domain(row)

    def get_by_id(self, account_id: str) -> Optional[Account]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, username, password_hash FROM accounts WHERE id = ?",
                (account_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._to_domain(row)

    def create_account(self, account: Account) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO accounts (id, username, password_hash)
                VALUES (?, ?, ?)
                """,
                (account.id, account.username, account.password_hash),
            )
            conn.commit()

