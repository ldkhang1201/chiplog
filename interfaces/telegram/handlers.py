from __future__ import annotations

import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from application.services import (
    ExternalContext,
    buy_chips_from_bank,
    confirm_buy_from_player,
    initiate_buy_from_player,
    reject_buy_from_player,
    sell_chips_to_bank,
)
from domain.repositories import IdentityRepository, UserRepository
from interfaces.telegram.callback_data import (
    encode_buy_from_choice,
    encode_buy_from_confirmation,
    parse_buy_from_choice,
    parse_buy_from_confirmation,
)


def _build_external_context(message) -> ExternalContext:
    """Extract a channel-agnostic context object from a Telegram message."""

    return ExternalContext(
        provider="telegram",
        provider_user_id=str(message.from_user.id),
        first_name=message.from_user.first_name or "",
        last_name=message.from_user.last_name or "",
    )


def create_telegram_bot(
    bot_token: str,
    user_repo: UserRepository,
    identity_repo: IdentityRepository,
) -> telebot.TeleBot:
    """
    Configure and return a TeleBot instance wired to the application layer.

    This module contains only Telegram-specific concerns: parsing Telegram
    messages/callbacks and mapping them to/from application services.
    """

    bot = telebot.TeleBot(bot_token)

    @bot.message_handler(commands=["start", "hello"])
    def handle_start(message):
        bot.send_message(
            message.chat.id,
            "Welcome to the poker table bot!\n"
            "Use /buy and /sell to manage chips.\n"
            "Type /help to see available commands.",
        )

    @bot.message_handler(commands=["help"])
    def handle_help(message):
        bot.send_message(
            message.chat.id,
            "/buy <amount>          - buy <amount> chips from the bank\n"
            "/buy <amount> from     - buy <amount> chips from another player\n"
            "/sell <amount>         - sell <amount> chips to the bank\n"
            "/list                  - list all players at the table\n",
        )

    @bot.message_handler(commands=["list"])
    def handle_list(message):
        users = user_repo.get_all_users()
        if not users:
            bot.send_message(message.chat.id, "No players at the table yet.")
            return

        lines = [
            f"{u.first_name} {u.last_name}: {u.balance}"
            for u in users
        ]
        total = sum(u.balance for u in users)
        lines.append(f"Total balance: {total}")

        bot.send_message(message.chat.id, "\n".join(lines))

    @bot.message_handler(commands=["buy", "sell"])
    def handle_transaction(message):
        parts = message.text.split(" ")
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Please enter amount of chips.")
            return

        op = parts[0][1:]  # strip leading '/'

        try:
            amount = int(parts[1])
        except ValueError:
            bot.send_message(message.chat.id, "Amount must be a number.")
            return

        flag = parts[2] if len(parts) > 2 else None

        external_ctx = _build_external_context(message)

        try:
            if op == "buy":
                if flag == "from":
                    # Player-to-player buy flow: show candidates.
                    result = initiate_buy_from_player(
                        external_ctx, amount, identity_repo, user_repo
                    )
                    if not result.success:
                        bot.send_message(message.chat.id, result.error_message)
                        return

                    markup = InlineKeyboardMarkup(row_width=2)
                    for candidate in result.candidates:
                        callback_data = encode_buy_from_choice(
                            source_user_id=result.source_user.id,
                            target_user_id=candidate.id,
                            amount=amount,
                        )
                        markup.add(
                            InlineKeyboardButton(
                                f"{candidate.first_name} {candidate.last_name}",
                                callback_data=callback_data,
                            )
                        )

                    bot.send_message(
                        message.chat.id,
                        "Choose one user to buy from",
                        reply_markup=markup,
                    )
                else:
                    # Bank buy.
                    result = buy_chips_from_bank(
                        external_ctx, amount, identity_repo, user_repo
                    )
                    if not result.success:
                        bot.send_message(message.chat.id, result.error_message)
                        return

                    for broadcast in result.broadcasts:
                        bot.send_message(broadcast.user_id, broadcast.text)

            elif op == "sell":
                # Bank sell.
                result = sell_chips_to_bank(
                    external_ctx, amount, identity_repo, user_repo
                )
                if not result.success:
                    bot.send_message(message.chat.id, result.error_message)
                    return

                for broadcast in result.broadcasts:
                    bot.send_message(broadcast.user_id, broadcast.text)
        except Exception as exc:  # Keep a broad catch to mirror original behavior.
            bot.send_message(message.chat.id, str(exc))

    @bot.callback_query_handler(func=lambda call: call.data.startswith("from:"))
    def handle_choice(call):
        """
        Handle selection of a seller for the buy-from-player flow.
        """

        try:
            source_id, target_id, amount = parse_buy_from_choice(call.data)
        except Exception:
            bot.answer_callback_query(call.id, "Invalid selection.")
            return

        # Ask the target user to confirm the transaction.
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton(
                "yes",
                callback_data=encode_buy_from_confirmation(
                    source_user_id=source_id,
                    target_user_id=target_id,
                    amount=amount,
                    accepted=True,
                ),
            )
        )
        markup.add(
            InlineKeyboardButton(
                "no",
                callback_data=encode_buy_from_confirmation(
                    source_user_id=source_id,
                    target_user_id=target_id,
                    amount=amount,
                    accepted=False,
                ),
            )
        )

        # The original implementation used `call.message.chat.id` to look up
        # the user initiating the request. Here we instead rely on the source
        # user ID that was encoded in the callback data.
        buyer = user_repo.get_user(source_id)
        buyer_name = (
            f"{buyer.first_name} {buyer.last_name}" if buyer is not None else "Someone"
        )

        bot.send_message(
            target_id,
            f"{buyer_name} wants to buy {amount} from you",
            reply_markup=markup,
        )
        bot.delete_message(call.message.chat.id, call.message.id)

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("yes:") or call.data.startswith("no:")
    )
    def handle_confirmation(call):
        """
        Handle seller confirmation or rejection of a buy-from-player request.
        """

        try:
            accepted, source_id, target_id, amount = parse_buy_from_confirmation(
                call.data
            )
        except Exception:
            bot.answer_callback_query(call.id, "Invalid confirmation.")
            return

        try:
            if accepted:
                result = confirm_buy_from_player(source_id, target_id, amount, user_repo)
            else:
                result = reject_buy_from_player(source_id, target_id, amount)

            if not result.success and result.error_message:
                bot.send_message(call.message.chat.id, result.error_message)
            else:
                for broadcast in result.broadcasts:
                    bot.send_message(broadcast.user_id, broadcast.text)
        finally:
            bot.delete_message(call.message.chat.id, call.message.id)

    return bot

