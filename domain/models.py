from dataclasses import dataclass


@dataclass
class User:
    """
    Domain representation of a poker user/player.

    This model is intentionally simple and independent of any
    particular transport (Telegram, Discord, web) or database schema.
    """

    id: str
    first_name: str
    last_name: str
    balance: int


@dataclass
class Account:
    """
    Authentication identity for a player on the poker platform.

    Multiple external identities (Telegram/Discord/Web) can be linked
    to the same account via the IdentityRepository so that a player
    can use the same username/password across channels.
    """

    id: str
    username: str
    password_hash: str

