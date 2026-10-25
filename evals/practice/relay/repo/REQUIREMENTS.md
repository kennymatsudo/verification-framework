# Relay requirements

- CR-1 Every input row becomes one output row with the same name and the amount in whole cents, exact for amounts with up to two decimals (12.30 is 1230).
- CR-2 The output's total equals the sum of every row's cents.
- CR-3 An input with a malformed amount is rejected: exit code 2, a message naming the line number, and no output file written, not even a partial one.
- CR-4 Converting the same input again produces an identical output file, replacing any earlier output at that path.
- CR-5 Amounts in currencies other than dollars are planned. Which currencies, and how they are marked in the input, is not decided.
