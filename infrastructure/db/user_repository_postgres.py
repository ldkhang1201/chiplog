from __future__ import annotations

from typing import List, Optional

from domain.models import User
from domain.repositories import UserRepository
from user import UserTable


class PostgresUserRepository(UserRepository):
    """
    Postgres-backed implementation of `UserRepository` using the existing
    `UserTable` helper for all SQL interactions.

    This class is responsible for translating between the database row/shape
    exposed by `UserTable` (dicts with string IDs) and the `User` domain model.
    """

    def __init__(self, db_params: dict) -> None:
        self._table = UserTable(db_params)

    @staticmethod
    def _to_domain(row: dict) -> User:
        # `UserTable` stores IDs padded/truncated to 10 characters. The domain
        # model works with the logical ID, so we strip whitespace padding here.
        return User(
            id=str(row["id"]).strip(),
            first_name=row["first_name"],
            last_name=row["last_name"],
            balance=int(row["balance"]),
        )

    def get_user(self, user_id: str) -> Optional[User]:
        row = self._table.get_user(user_id)
        if not row:
            return None
        return self._to_domain(row)

    def get_all_users(self) -> List[User]:
        rows = self._table.get_all_users()
        return [self._to_domain(row) for row in rows]

    def add_user(self, user: User) -> None:
        self._table.add_user(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            balance=user.balance,
        )

    def update_balance(self, user_id: str, delta: int) -> None:
        self._table.update_balance(user_id, delta)

