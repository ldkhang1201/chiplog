from __future__ import annotations

from typing import List, Optional, Protocol

from .models import Account, User


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

    # Legacy API: no longer used in the new login-based flow, but kept
    # for backwards compatibility with older infrastructure code.
    def get_or_create_user_from_external(
        self,
        provider: str,
        provider_user_id: str,
        first_name: str,
        last_name: str,
    ) -> User:
        ...

    def find_user_by_external(
        self,
        provider: str,
        provider_user_id: str,
    ) -> Optional[User]:
        """Return the user mapped to the given external identity, if any."""

        ...

    def set_external_identity(
        self,
        provider: str,
        provider_user_id: str,
        user_id: str,
    ) -> None:
        """
        Associate an external identity with an internal user ID.

        Used by the login/registration flow so that a single account can
        be reused across multiple channels and sessions.
        """

        ...

    def clear_external_identity(
        self,
        provider: str,
        provider_user_id: str,
    ) -> None:
        """Remove any mapping for the given external identity (logout)."""

        ...

    def get_external_ids_for_user(
        self,
        provider: str,
        user_id: str,
    ) -> List[str]:
        """
        Return all external IDs (e.g. Telegram chat IDs) associated with
        a given internal user ID for the specified provider.
        """

        ...


class AccountRepository(Protocol):
    """
    Persistence abstraction for platform accounts (username/password).
    """

    def get_by_username(self, username: str) -> Optional[Account]:
        ...

    def get_by_id(self, account_id: str) -> Optional[Account]:
        ...

    def create_account(self, account: Account) -> None:
        ...

