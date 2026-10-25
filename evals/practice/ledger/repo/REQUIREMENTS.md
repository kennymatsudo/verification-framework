# Ledger requirements

What the service must do, as agreed with the finance team. Each item has an ID so tickets and checks can name it.

## Accounts

- LR-1 Opening an account returns its new ID, and the account can be read back by that ID with a zero balance.
- LR-2 Reading an account that does not exist answers 404.

## Transactions

- LR-3 A deposit increases the account's balance by the amount, and the stored balance equals the sum of all its transactions.
- LR-4 A withdrawal that would take the balance below zero is refused with 409 "insufficient funds" and leaves the balance unchanged. Overdrafts are not offered.

## Transfers

- LR-5 A transfer debits the source account and credits the destination by the same amount, and both changes happen or neither does.
- LR-6 A transfer larger than the source balance is refused with 409 and changes neither account.
- LR-7 A daily transfer limit per account is planned. The amount is still to be decided with the finance team; until then transfers of any size within the balance are allowed.

## Statement

- LR-8 The statement lists the account's transactions newest first, each with the balance after it.
