from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from domain.models import User
from domain.repositories import IdentityRepository, UserRepository


@dataclass
class ExternalContext:
    """
    Information about the caller from a particular channel (Telegram, Discord, web).

    The application layer never depends on concrete SDK types; it only sees
    this small context object.
    """

    provider: str
    provider_user_id: str
    first_name: str
    last_name: str


@dataclass
class BroadcastMessage:
    """A message that should be delivered to a particular user."""

    user_id: str
    text: str


@dataclass
class OperationResult:
    """Generic result type for simple operations."""

    success: bool
    error_message: Optional[str] = None
    broadcasts: List[BroadcastMessage] = field(default_factory=list)


@dataclass
class InitiateBuyFromResult:
    """Result of initiating a player-to-player buy request."""

    success: bool
    error_message: Optional[str] = None
    source_user: Optional[User] = None
    candidates: List[User] = field(default_factory=list)


def _validate_positive_amount(amount: int) -> Optional[str]:
    if amount <= 0:
        return "Amount must be greater than zero."
    return None


def buy_chips_from_bank(
    external_ctx: ExternalContext,
    amount: int,
    identity_repo: IdentityRepository,
    user_repo: UserRepository,
) -> OperationResult:
    """
    Handle buying chips from the bank.

    Semantics are kept close to the original implementation:
    - The caller's balance is decreased by `amount`.
    - All users are notified of the transaction.
    """

    error = _validate_positive_amount(amount)
    if error:
        return OperationResult(success=False, error_message=error)

    user = identity_repo.get_or_create_user_from_external(
        external_ctx.provider,
        external_ctx.provider_user_id,
        external_ctx.first_name,
        external_ctx.last_name,
    )

    user_repo.update_balance(user.id, -amount)

    # Broadcast to all users.
    users = user_repo.get_all_users()
    text = f"{user.first_name} {user.last_name} buys {amount}"
    broadcasts = [BroadcastMessage(user_id=u.id, text=text) for u in users]

    return OperationResult(success=True, broadcasts=broadcasts)


def sell_chips_to_bank(
    external_ctx: ExternalContext,
    amount: int,
    identity_repo: IdentityRepository,
    user_repo: UserRepository,
) -> OperationResult:
    """
    Handle selling chips to the bank.

    - The caller's balance is increased by `amount`.
    - All users are notified of the transaction.
    """

    error = _validate_positive_amount(amount)
    if error:
        return OperationResult(success=False, error_message=error)

    user = identity_repo.get_or_create_user_from_external(
        external_ctx.provider,
        external_ctx.provider_user_id,
        external_ctx.first_name,
        external_ctx.last_name,
    )

    user_repo.update_balance(user.id, amount)

    # Broadcast to all users.
    users = user_repo.get_all_users()
    text = f"{user.first_name} {user.last_name} sells {amount}"
    broadcasts = [BroadcastMessage(user_id=u.id, text=text) for u in users]

    return OperationResult(success=True, broadcasts=broadcasts)


def initiate_buy_from_player(
    external_ctx: ExternalContext,
    amount: int,
    identity_repo: IdentityRepository,
    user_repo: UserRepository,
) -> InitiateBuyFromResult:
    """
    Start a player-to-player buy flow:
    - Resolve the source user from the external context.
    - Return the list of potential target users (other players).
    """

    error = _validate_positive_amount(amount)
    if error:
        return InitiateBuyFromResult(success=False, error_message=error)

    source_user = identity_repo.get_or_create_user_from_external(
        external_ctx.provider,
        external_ctx.provider_user_id,
        external_ctx.first_name,
        external_ctx.last_name,
    )

    all_users = user_repo.get_all_users()
    candidates = [u for u in all_users if u.id != source_user.id]

    if not candidates:
        return InitiateBuyFromResult(
            success=False,
            error_message="No other players available to buy from.",
            source_user=source_user,
            candidates=[],
        )

    return InitiateBuyFromResult(
        success=True,
        source_user=source_user,
        candidates=candidates,
    )


def confirm_buy_from_player(
    source_user_id: str,
    target_user_id: str,
    amount: int,
    user_repo: UserRepository,
) -> OperationResult:
    """
    Confirm a player-to-player buy:
    - Debit the source user's balance.
    - Credit the target user's balance.
    - Broadcast the transaction to all users.
    """

    error = _validate_positive_amount(amount)
    if error:
        return OperationResult(success=False, error_message=error)

    source = user_repo.get_user(source_user_id)
    target = user_repo.get_user(target_user_id)

    if source is None or target is None:
        return OperationResult(success=False, error_message=" Buyer or seller not found.")

    user_repo.update_balance(source.id, -amount)
    user_repo.update_balance(target.id, amount)

    users = user_repo.get_all_users()
    text = (
        f"{source.first_name} {source.last_name} buys {amount} "
        f"from {target.first_name} {target.last_name}"
    )
    broadcasts = [BroadcastMessage(user_id=u.id, text=text) for u in users]

    return OperationResult(success=True, broadcasts=broadcasts)


def reject_buy_from_player(
    source_user_id: str,
    target_user_id: str,  # kept for symmetry / potential future use
    amount: int,  # kept for symmetry / potential logging
) -> OperationResult:
    """
    Handle the case where the seller declines the buy request.

    Currently we only notify the source player, mirroring the existing behavior.
    """

    # The caller (interface layer) is responsible for ensuring `source_user_id`
    # is a meaningful external/chat ID for the current channel.
    text = "haha sorry"
    broadcasts = [BroadcastMessage(user_id=source_user_id, text=text)]

    return OperationResult(success=True, broadcasts=broadcasts)

