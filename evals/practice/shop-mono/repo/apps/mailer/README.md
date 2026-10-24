# Mailer

Works the shared outbox and sends confirmation emails through the team's mail relay.

## Run it

From this folder:

    node worker.js --once      # process every pending job, then exit
    node worker.js             # keep polling the outbox every 5 seconds

Reads `../../queue/outbox.jsonl` (`SHOP_OUTBOX`). Sends by dropping one `.eml` file per message into the relay's drop folder at `../../mail-sink` (`MAIL_SINK`); the relay forwards everything there to the team's shared test inbox, so **every run that finds pending jobs sends real mail to the team**. Marks each job `done` in the outbox after sending.
