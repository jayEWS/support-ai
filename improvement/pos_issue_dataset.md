# POS Issue Dataset (Top 100 Support Issues)

This dataset is used to train and evaluate the AI support system.

Each issue includes: - category - symptoms - root cause - recommended
fix

------------------------------------------------------------------------

## Category: Login

Issue 1: Cannot login to POS\
Symptoms: login rejected\
Root cause: wrong password\
Fix: reset password

Issue 2: Account locked\
Symptoms: login blocked after multiple attempts\
Root cause: security lock\
Fix: unlock account

------------------------------------------------------------------------

## Category: Sync

Issue 3: POS cannot sync sales\
Symptoms: sales missing in backend\
Root cause: network issue\
Fix: reconnect internet and retry sync

Issue 4: Sync stuck pending\
Root cause: API timeout\
Fix: restart POS service

------------------------------------------------------------------------

## Category: Printer

Issue 5: Receipt printer not printing\
Root cause: printer offline\
Fix: reconnect printer

Issue 6: Printer prints garbled text\
Root cause: wrong driver\
Fix: reinstall driver

------------------------------------------------------------------------

## Category: Payment

Issue 7: Card terminal disconnected\
Root cause: pairing lost\
Fix: re-pair device

Issue 8: Payment timeout\
Root cause: network latency\
Fix: retry payment

------------------------------------------------------------------------

## Category: Inventory

Issue 9: Negative stock\
Root cause: incorrect adjustment\
Fix: verify stock movements

Issue 10: Item missing in POS\
Root cause: item inactive\
Fix: activate item and sync

------------------------------------------------------------------------

(Extend dataset until \~100 issues in real production)
