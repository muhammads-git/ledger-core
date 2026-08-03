# ledger-core

A wallet ledger API where the balance is never stored — it's calculated from history, every time.

> **Status:** In progress. Core ledger design and single-account deposit/withdraw in active development. See [Roadmap](#roadmap) for what's built vs. what's next.

## Why this exists

Most wallet/balance features get built the same way: one `balance` column, incremented on deposit, decremented on withdrawal. It works fine right up until two requests hit the same account at the same instant, or a server crashes mid-transfer, or a client retries a timed-out request — and then it quietly loses or duplicates money. This project is a from-scratch attempt at building a wallet system that doesn't have those failure modes, using the same principles real financial systems are built on: double-entry ledgering, transactional atomicity, row-level locking, and idempotent writes.

## Core design decision

There is no mutable `balance` field anywhere in this system. Every deposit and withdrawal is stored as an immutable row in a transactions table. Balance is always *derived* — summed from history — not edited directly. This is the same reason a bank statement shows every transaction rather than just a current number: the number alone has no story, no way to answer "where did this come from."

## What it guarantees (by design, being built toward)

- **Atomicity** — a transfer either fully happens (both sides update) or not at all. No partial state, even if the server crashes mid-operation.
- **Concurrency safety** — two simultaneous requests against the same account can never both succeed based on stale data. Row-level locking (`SELECT ... FOR UPDATE`) forces the second request to wait and re-check against the real, up-to-date balance.
- **Idempotency** — a client retry of a request that already succeeded does not process the transaction twice. Enforced via a unique idempotency key per request.
- **Balance integrity** — an account can never go negative, enforced at the data layer, not just in application code.

## Schema (early draft)

```
accounts
  id
  owner
  created_at

transactions
  id
  account_id     (FK -> accounts.id)
  amount
  type            deposit | withdrawal
  idempotency_key  (unique)
  created_at
```

Balance for an account = sum of deposits minus sum of withdrawals from its transaction history. No stored balance column.

## Roadmap

- [ ] Single-account deposit / withdraw, balance derived from transaction history
- [ ] Enforce non-negative balance at the database level
- [ ] Concurrency-safe withdrawals under simultaneous requests (`SELECT ... FOR UPDATE`)
- [ ] Idempotency keys — safe request retries
- [ ] Atomic transfers between two accounts
- [ ] Transaction history endpoint with pagination
- [ ] Basic API layer (FastAPI) wrapping the above

## Tech

Python · SQLAlchemy · PostgreSQL · FastAPI (planned)

## Notes

This is a learning-focused project built to understand the actual hard problems behind financial backends — not a production payments system. For real money movement, use a licensed payment processor (Stripe, etc.). The value here is in building, breaking, and fixing the exact failure modes those systems are designed around.
