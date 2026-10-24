# Orders requirements

- SR-1 Placing an order stores it with the customer's email, its lines, and a total of price times quantity (mug 1200, tee 2500, cap 1800 cents).
- SR-2 Each stored order puts exactly one job in the shared outbox naming the order ID and the customer's email.
- SR-3 The mailer sends exactly one confirmation per outbox job to the customer's email, with the order ID in the subject, and marks the job done so it is never sent twice.
