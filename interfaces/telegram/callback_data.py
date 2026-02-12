from __future__ import annotations


def encode_buy_from_choice(source_user_id: str, target_user_id: str, amount: int) -> str:
    """
    Encode a "choose seller" callback.

    Format: from:{source_id}:to:{target_id}:{amount}
    """

    return f"from:{source_user_id}:to:{target_user_id}:{amount}"


def parse_buy_from_choice(data: str) -> tuple[str, str, int]:
    parts = data.split(":")
    if len(parts) != 5 or parts[0] != "from" or parts[2] != "to":
        raise ValueError(f"Invalid buy-from choice callback data: {data}")

    source_id = parts[1]
    target_id = parts[3]
    amount = int(parts[4])
    return source_id, target_id, amount


def encode_buy_from_confirmation(
    source_user_id: str,
    target_user_id: str,
    amount: int,
    accepted: bool,
) -> str:
    """
    Encode a confirmation/decline callback.

    Format:
      yes:{source_id}:{target_id}:{amount}
      no:{source_id}:{target_id}:{amount}
    """

    prefix = "yes" if accepted else "no"
    return f"{prefix}:{source_user_id}:{target_user_id}:{amount}"


def parse_buy_from_confirmation(data: str) -> tuple[bool, str, str, int]:
    parts = data.split(":")
    if len(parts) != 4 or parts[0] not in ("yes", "no"):
        raise ValueError(f"Invalid buy-from confirmation callback data: {data}")

    accepted = parts[0] == "yes"
    source_id = parts[1]
    target_id = parts[2]
    amount = int(parts[3])
    return accepted, source_id, target_id, amount

