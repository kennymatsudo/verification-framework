import unittest

from ledger import store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.db = store.connect(":memory:")

    def test_deposit_raises_balance(self):
        acct = store.create_account(self.db, "Ada")
        store.post_transaction(self.db, acct["id"], 500, "salary")
        self.assertEqual(store.account(self.db, acct["id"])["balance"], 500)

    def test_transfer_moves_money(self):
        a = store.create_account(self.db, "A")["id"]
        b = store.create_account(self.db, "B")["id"]
        store.post_transaction(self.db, a, 300, "")
        store.transfer(self.db, a, b, 100)
        self.assertEqual(store.account(self.db, a)["balance"], 200)
        self.assertEqual(store.account(self.db, b)["balance"], 100)

    def test_transfer_refuses_overdraft(self):
        a = store.create_account(self.db, "A")["id"]
        b = store.create_account(self.db, "B")["id"]
        with self.assertRaises(store.InsufficientFunds):
            store.transfer(self.db, a, b, 1)


if __name__ == "__main__":
    unittest.main()
