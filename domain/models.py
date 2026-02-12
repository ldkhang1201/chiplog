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

