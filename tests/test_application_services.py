import unittest

from application.services import (
    ExternalContext,
    buy_chips_from_bank,
    confirm_buy_from_player,
    initiate_buy_from_player,
    sell_chips_to_bank,
)
from domain.models import User
from domain.repositories import IdentityRepository, UserRepository


class InMemoryUserRepository(UserRepository):
    def __init__(self):
        self.users = {}

    def get_user(self, user_id: str):
        return self.users.get(user_id)

    def get_all_users(self):
        return list(self.users.values())

    def add_user(self, user: User) -> None:
        self.users[user.id] = user

    def update_balance(self, user_id: str, delta: int) -> None:
        user = self.users[user_id]
        user.balance += delta


class InMemoryIdentityRepository(IdentityRepository):
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
        self.mapping = {}

    def get_or_create_user_from_external(
        self,
        provider: str,
        provider_user_id: str,
        first_name: str,
        last_name: str,
    ) -> User:
        key = (provider, provider_user_id)
        if key in self.mapping:
            return self.user_repo.get_user(self.mapping[key])

        user = User(
            id=provider_user_id,
            first_name=first_name,
            last_name=last_name,
            balance=0,
        )
        self.user_repo.add_user(user)
        self.mapping[key] = user.id
        return user

    def find_user_by_external(
        self,
        provider: str,
        provider_user_id: str,
    ):
        key = (provider, provider_user_id)
        user_id = self.mapping.get(key)
        if not user_id:
            return None
        return self.user_repo.get_user(user_id)


class ApplicationServicesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user_repo = InMemoryUserRepository()
        self.identity_repo = InMemoryIdentityRepository(self.user_repo)
        self.ctx = ExternalContext(
            provider="telegram",
            provider_user_id="12345",
            first_name="John",
            last_name="Doe",
        )

    def test_buy_chips_from_bank_creates_user_and_broadcasts(self):
        result = buy_chips_from_bank(self.ctx, 100, self.identity_repo, self.user_repo)
        self.assertTrue(result.success)
        # User should be created and have negative balance (owes the bank).
        user = self.user_repo.get_user("12345")
        self.assertIsNotNone(user)
        self.assertEqual(user.balance, -100)
        # Broadcast to at least this user.
        self.assertGreaterEqual(len(result.broadcasts), 1)

    def test_sell_chips_to_bank_increases_balance(self):
        # First buy 100, then sell 50.
        buy_chips_from_bank(self.ctx, 100, self.identity_repo, self.user_repo)
        result = sell_chips_to_bank(self.ctx, 50, self.identity_repo, self.user_repo)
        self.assertTrue(result.success)
        user = self.user_repo.get_user("12345")
        self.assertEqual(user.balance, -50)

    def test_initiate_and_confirm_buy_from_player_flow(self):
        # Create two users.
        ctx1 = self.ctx
        ctx2 = ExternalContext(
            provider="telegram",
            provider_user_id="67890",
            first_name="Jane",
            last_name="Smith",
        )
        self.identity_repo.get_or_create_user_from_external(
            ctx1.provider, ctx1.provider_user_id, ctx1.first_name, ctx1.last_name
        )
        self.identity_repo.get_or_create_user_from_external(
            ctx2.provider, ctx2.provider_user_id, ctx2.first_name, ctx2.last_name
        )

        # Give seller some chips.
        self.user_repo.update_balance("67890", 200)

        initiate_result = initiate_buy_from_player(
            ctx1, 50, self.identity_repo, self.user_repo
        )
        self.assertTrue(initiate_result.success)
        self.assertEqual(len(initiate_result.candidates), 1)

        confirm_result = confirm_buy_from_player("12345", "67890", 50, self.user_repo)
        self.assertTrue(confirm_result.success)
        buyer = self.user_repo.get_user("12345")
        seller = self.user_repo.get_user("67890")
        self.assertEqual(buyer.balance, -50)
        self.assertEqual(seller.balance, 150)


if __name__ == "__main__":
    unittest.main()

