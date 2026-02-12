from __future__ import annotations

import sqlite3
from typing import Optional

from domain.models import User
from domain.repositories import IdentityRepository, UserRepository


class SqliteIdentityRepository(IdentityRepository):
    """
    SQLite-backed implementation of `IdentityRepository`.

    Stores mappings from (provider, provider_user_id) to internal user IDs
    in a `user_identities` table.
    """

    def __init__(self, db_path: str, user_repo: UserRepository) -> None:
        self._db_path = db_path
        self._user_repo = user_repo
        self._ensure_table()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _ensure_table(self) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_identities (
                    provider TEXT NOT NULL,
                    provider_user_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    PRIMARY KEY (provider, provider_user_id)
                )
                """
            )
            conn.commit()

    def _get_internal_user_id(
        self,
        provider: str,
        provider_user_id: str,
    ) -> Optional[str]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT user_id
                FROM user_identities
                WHERE provider = ? AND provider_user_id = ?
                """,
                (provider, provider_user_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return str(row[0])

    def set_external_identity(
        self,
        provider: str,
        provider_user_id: str,
        user_id: str,
    ) -> None:
        """
        Upsert a mapping from external identity to internal user ID.
        """

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO user_identities (provider, provider_user_id, user_id)
                VALUES (?, ?, ?)
                ON CONFLICT (provider, provider_user_id)
                DO UPDATE SET user_id = excluded.user_id
                """,
                (provider, provider_user_id, user_id),
            )
            conn.commit()

    def clear_external_identity(
        self,
        provider: str,
        provider_user_id: str,
    ) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM user_identities
                WHERE provider = ? AND provider_user_id = ?
                """,
                (provider, provider_user_id),
            )
            conn.commit()

    def get_or_create_user_from_external(
        self,
        provider: str,
        provider_user_id: str,
        first_name: str,
        last_name: str,
    ) -> User:
        # Legacy behaviour: auto-create a user bound directly to the
        # external identity. Kept for backwards compatibility but not
        # used in the new login-based flow.
        existing = self.find_user_by_external(provider, provider_user_id)
        if existing is not None:
            return existing

        user = User(
            id=str(provider_user_id),
            first_name=first_name,
            last_name=last_name,
            balance=0,
        )
        self._user_repo.add_user(user)
        self.set_external_identity(provider, provider_user_id, user.id)

        stored_user = self._user_repo.get_user(user.id)
        return stored_user or user

    def find_user_by_external(
        self,
        provider: str,
        provider_user_id: str,
    ) -> Optional[User]:
        user_id = self._get_internal_user_id(provider, provider_user_id)
        if user_id is None:
            return None
        return self._user_repo.get_user(user_id)

    def get_external_ids_for_user(
        self,
        provider: str,
        user_id: str,
    ) -> list[str]:
        """
        Return all external IDs for the given internal user ID and provider.
        """

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT provider_user_id
                FROM user_identities
                WHERE provider = ? AND user_id = ?
                """,
                (provider, user_id),
            )
            rows = cur.fetchall()
            return [str(row[0]) for row in rows]

