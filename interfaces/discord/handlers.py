from __future__ import annotations

from typing import Dict, Tuple

import discord
from discord.ext import commands

from application.services import (
    ExternalContext,
    buy_chips_from_bank,
    confirm_buy_from_player,
    reject_buy_from_player,
    sell_chips_to_bank,
)
from domain.repositories import IdentityRepository, UserRepository


def _build_external_context(user: discord.abc.User) -> ExternalContext:
    """Create an `ExternalContext` from a Discord user."""

    # Discord has `name` and `display_name`; here we just store the full
    # display name in `first_name` to keep things simple.
    display_name = user.display_name or user.name
    return ExternalContext(
        provider="discord",
        provider_user_id=str(user.id),
        first_name=display_name,
        last_name="",
    )


def create_discord_bot(
    user_repo: UserRepository,
    identity_repo: IdentityRepository,
) -> commands.Bot:
    """
    Configure and return a Discord bot with behaviour analogous to
    the Telegram interface: /start, /help, buy/sell chips, and list players.
    """

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.members = True
    intents.reactions = True

    # Disable the default help command so we can provide our own `!help`.
    bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

    # In-memory store of pending player-to-player buy requests keyed by the
    # confirmation message ID.
    pending_requests: Dict[int, Tuple[str, str, int, int]] = {}
    # value: (buyer_internal_id, seller_internal_id, amount, seller_discord_id)

    @bot.event
    async def on_ready():
        print(f"Discord bot logged in as {bot.user} (id={bot.user.id})")

    @bot.command(name="start")
    async def start_cmd(ctx: commands.Context):
        await ctx.send(
            "Welcome to the poker table bot (Discord)!\n"
            "Use !buy and !sell to manage chips.\n"
            "Type !help to see available commands."
        )

    @bot.command(name="help")
    async def help_cmd(ctx: commands.Context):
        await ctx.send(
            "!buy <amount>              - buy <amount> chips from the bank\n"
            "!buy <amount> @player      - buy <amount> chips from another player\n"
            "!sell <amount>             - sell <amount> chips to the bank\n"
            "!list                      - list all players at the table\n"
        )

    @bot.command(name="list")
    async def list_cmd(ctx: commands.Context):
        users = user_repo.get_all_users()
        if not users:
            await ctx.send("No players at the table yet.")
            return

        lines = [f"{u.first_name}: {u.balance}" for u in users]
        total = sum(u.balance for u in users)
        lines.append(f"Total balance: {total}")
        await ctx.send("\n".join(lines))

    @bot.command(name="buy")
    async def buy_cmd(
        ctx: commands.Context,
        amount: int,
        seller: discord.Member | None = None,
    ):
        """
        !buy <amount>           -> buy from bank
        !buy <amount> @seller   -> request to buy from another player
        """

        external_ctx = _build_external_context(ctx.author)

        if seller is None:
            # Bank buy.
            result = buy_chips_from_bank(
                external_ctx,
                amount,
                identity_repo,
                user_repo,
            )
            if not result.success:
                await ctx.send(result.error_message or "Buy failed.")
                return

            # For Discord, we broadcast in the current channel.
            if result.broadcasts:
                await ctx.send(result.broadcasts[0].text)
            else:
                await ctx.send("Buy completed.")
            return

        # Player-to-player buy flow.
        buyer = identity_repo.get_or_create_user_from_external(
            "discord",
            str(ctx.author.id),
            ctx.author.display_name or ctx.author.name,
            "",
        )
        seller_user = identity_repo.get_or_create_user_from_external(
            "discord",
            str(seller.id),
            seller.display_name or seller.name,
            "",
        )

        confirmation_message = await ctx.send(
            f"{seller.mention}, {buyer.first_name} wants to buy {amount} from you.\n"
            "React with ✅ to confirm or ❌ to decline."
        )
        await confirmation_message.add_reaction("✅")
        await confirmation_message.add_reaction("❌")

        pending_requests[confirmation_message.id] = (
            buyer.id,
            seller_user.id,
            amount,
            seller.id,
        )

    @bot.command(name="sell")
    async def sell_cmd(ctx: commands.Context, amount: int):
        external_ctx = _build_external_context(ctx.author)

        result = sell_chips_to_bank(
            external_ctx,
            amount,
            identity_repo,
            user_repo,
        )
        if not result.success:
            await ctx.send(result.error_message or "Sell failed.")
            return

        if result.broadcasts:
            await ctx.send(result.broadcasts[0].text)
        else:
            await ctx.send("Sell completed.")

    @bot.event
    async def on_reaction_add(reaction: discord.Reaction, user: discord.abc.User):
        # Ignore bot reactions and reactions not on tracked messages.
        if user.bot:
            return

        message_id = reaction.message.id
        if message_id not in pending_requests:
            return

        buyer_id, seller_id, amount, seller_discord_id = pending_requests[message_id]

        # Only the intended seller can confirm/decline.
        if user.id != seller_discord_id:
            return

        emoji = str(reaction.emoji)
        channel = reaction.message.channel

        if emoji == "✅":
            result = confirm_buy_from_player(buyer_id, seller_id, amount, user_repo)
        elif emoji == "❌":
            result = reject_buy_from_player(buyer_id, seller_id, amount)
        else:
            return

        # Once reacted, remove the pending request.
        pending_requests.pop(message_id, None)

        if not result.success and result.error_message:
            await channel.send(result.error_message)
        else:
            # For Discord we broadcast the first message text in the channel.
            if result.broadcasts:
                await channel.send(result.broadcasts[0].text)

    return bot

