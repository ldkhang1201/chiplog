from __future__ import annotations

from typing import List, Optional, Protocol

from .models import User


class UserRepository(Protocol):
    """
    Abstraction over user persistence.

    Implementations are responsible for:
    - Mapping between database rows and the `User` domain model.
    - Hiding any SQL / driver details from the application layer.
    """

    def get_user(self, user_id: str) -> Optional[User]:
        """Return the user with the given internal ID, or None if not found."""

        ...

    def get_all_users(self) -> List[User]:
        """Return all users currently known to the system."""

        ...

    def add_user(self, user: User) -> None:
        """Persist a new user."""

        ...

    def update_balance(self, user_id: str, delta: int) -> None:
        """
        Adjust a user's balance by `delta`.

        Implementations should atomically apply the delta.
        """

        ...


class IdentityRepository(Protocol):
    """
    Maps external identities (Telegram/Discord/Web) to internal user IDs.

    The application layer should work exclusively with internal user IDs
    and leave provider‑specific identifiers to this abstraction.
    """

    def get_or_create_user_from_external(
        self,
        provider: str,
        provider_user_id: str,
        first_name: str,
        last_name: str,
    ) -> User:
        """
        Resolve a `User` from an external identity, creating a new user
        + mapping if none exists yet.
        """

        ...

    def find_user_by_external(
        self,
        provider: str,
        provider_user_id: str,
    ) -> Optional[User]:
        """Return the user mapped to the given external identity, if any."""

        ...

