from __future__ import annotations

from typing import Optional

import psycopg2

from domain.models import User
from domain.repositories import IdentityRepository, UserRepository


class PostgresIdentityRepository(IdentityRepository):
    """
    Postgres-backed implementation of `IdentityRepository`.

    It uses a dedicated `user_identities` table to map external identities
    (provider + provider_user_id) to internal user IDs stored in the `users`
    table managed by `UserTable` / `PostgresUserRepository`.
    """

    def __init__(self, db_params: dict, user_repo: UserRepository) -> None:
        self._db_params = db_params
        self._user_repo = user_repo
        self._ensure_table()

    def _get_connection(self):
        return psycopg2.connect(**self._db_params)

    @staticmethod
    def _normalize_user_id(user_id: str) -> str:
        """
        Mirror the normalization performed by `UserTable`, which pads/truncates
        IDs to exactly 10 characters before storing them in the `users` table.
        """

        return str(user_id).ljust(10)[:10]

    def _ensure_table(self) -> None:
        """
        Ensure that the `user_identities` table exists.

        Schema (minimal):
          - provider TEXT
          - provider_user_id TEXT
          - user_id CHAR(10)  -- matches `users.id`
        """

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_identities (
                        provider TEXT NOT NULL,
                        provider_user_id TEXT NOT NULL,
                        user_id CHAR(10) NOT NULL,
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
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT user_id
                    FROM user_identities
                    WHERE provider = %s AND provider_user_id = %s
                    """,
                    (provider, provider_user_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                # Stored as CHAR(10); strip any padding.
                return str(row[0]).strip()

    def _insert_mapping(
        self,
        provider: str,
        provider_user_id: str,
        user_id: str,
    ) -> None:
        normalized_id = self._normalize_user_id(user_id)
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_identities (provider, provider_user_id, user_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (provider, provider_user_id) DO NOTHING
                    """,
                    (provider, provider_user_id, normalized_id),
                )
                conn.commit()

    def get_or_create_user_from_external(
        self,
        provider: str,
        provider_user_id: str,
        first_name: str,
        last_name: str,
    ) -> User:
        # Try existing mapping first.
        existing = self.find_user_by_external(provider, provider_user_id)
        if existing is not None:
            return existing

        # No mapping yet: create a new user using the external identifier as
        # the logical internal ID. `PostgresUserRepository` / `UserTable` will
        # handle padding/truncation as needed for storage.
        user = User(
            id=str(provider_user_id),
            first_name=first_name,
            last_name=last_name,
            balance=0,
        )
        self._user_repo.add_user(user)

        # Insert identity mapping using the normalized user ID used in `users`.
        self._insert_mapping(provider, provider_user_id, user.id)

        # Return the freshly created user (re-read to ensure we have the
        # canonical representation).
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

