# QA coverage

| Check | Behavior | Strength |
| --- | --- | --- |
| check_create.py | opening an account | strong |
| check_deposit.py | a deposit raises the balance | strong |
| check_transfer.py | a transfer moves money between accounts | strong |
| check_statement.py | the statement matches the stored transactions | strong |
| check_overdraft.py | withdrawals beyond the balance | strong |

"Strong" means the check has been seen to fail on a bug. None of these have a recorded failure yet; the ratings are the authors' judgment.
