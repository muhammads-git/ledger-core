# LedgerCore — Production Double-Entry Wallet API

A production-grade digital wallet REST API built with **FastAPI** and **PostgreSQL**. Engineered around **double-entry ledger bookkeeping** and **pessimistic row-level locking** — the same core accounting and concurrency principles used by Stripe, PayPal, and modern core banking systems — ensuring every transaction is immutable, auditable, and mathematically consistent under high concurrency.

---

## Why a Double-Entry Ledger Instead of a Mutable Balance Column

Most tutorial wallet implementations mutate a column directly on the user or account record:

```python
user.balance += amount  # deposit
user.balance -= amount  # withdraw
```

At production scale, mutable balance columns fail under real-world edge cases:

* **Crash recovery:** A process failure mid-operation leaves balances out of sync with transaction logs.
* **Auditability:** There is no mathematical proof of where funds originated or settled.
* **Extensibility:** Multi-party splits, holds, reversals, and platform fees become brittle special cases.

**LedgerCore stores no mutable balance column.** An account's balance is always derived deterministically from an append-only ledger:

```sql
SELECT COALESCE(SUM(amount), 0) FROM ledger_entries WHERE account_id = :account_id;
```

Every financial movement maps to at least two immutable ledger entries whose net sum equals zero (`Debit + Credit = 0`). Financial integrity is enforced by the data model itself — not fragile application state.

---

## System Architecture

```text
Client Request
      │
      ▼
FastAPI Application (Async / Thread-Pooled Workers)
      │
      ├──► Auth & Session Security Layer
      │      ├── Access Token  → Short-lived JWT (30 min, Bearer header)
      │      └── Refresh Token → Long-lived UUID (7 days, httpOnly cookie + DB rotation)
      │
      └──► Transactional Ledger Engine (ACID + Row-Level Locking)
             ├── Layer 1: accounts        (Identity, currency, account policy FK)
             ├── Layer 2: transactions    (Immutable event header & lifecycle state)
             └── Layer 3: ledger_entries  (Signed decimal movements: SUM = 0)
                    │
                    ▼
             PostgreSQL (SQLAlchemy ORM + Alembic Migrations)
```

---

## Key Engineering & Architectural Decisions

### 1. Normalized `account_types` Table for Zero-Downtime Scale
Rather than storing account categories (`SAVINGS`, `CHECKINGS`, `SYSTEM_FEES`) as raw strings or rigid database `ENUM` types on the `accounts` table, account tiers are normalized into a dedicated `account_types` table:

* **Lock-free schema evolution:** At millions of rows, altering an inline column or `ENUM` on `accounts` acquires heavy table locks and rewrites data. Adding a new product tier in `account_types` is an instant single-row `INSERT`.
* **Centralized policy configuration:** When business rules change (e.g., updating daily transfer limits or fee tiers for `SAVINGS` accounts), updating one row in `account_types` applies globally without locking or updating millions of user rows during peak traffic.

### 2. Concurrency Control & Deadlock Prevention
Financial APIs fail catastrophically if two concurrent requests read the same balance simultaneously (the **TOCTOU / Double-Spend race condition**) or lock accounts in opposite orders (**PostgreSQL Deadlock `40P01`**).

* **Race-condition prevention:** Concurrent withdrawals and transfers serialize access at the database row level so two simultaneous `800.00` debits against a `1000.00` balance cannot both pass validation.
* **Deterministic lock ordering:** Bidirectional transfers (`Alice → Bob` and `Bob → Alice` executing at the exact same millisecond) acquire row locks in a consistent order, preventing circular wait deadlocks.

### 3. Immutable Transaction State Machine
Transactions are never overwritten or deleted. Lifecycle transitions move strictly forward (`PENDING → COMPLETED` or `FAILED`), preserving a complete, tamper-evident audit trail for reconciliation.

### 4. Fixed-Point `Numeric(12, 2)` Precision
All monetary values use PostgreSQL `NUMERIC(12, 2)` paired with Python `Decimal` — eliminating IEEE-754 floating-point rounding drift (`0.1 + 0.2 != 0.3`).

### 5. Stateful Refresh Token Rotation & `httpOnly` Cookies
Refresh tokens are stored in `httpOnly` cookies (inaccessible to client-side JavaScript/XSS) and rotated on every refresh request. Reusing a revoked token immediately invalidates the compromised session chain.

---

## Database Schema

```text
account_types
  id, name, code, created_at

accounts
  id, user_id (FK), public_id (UUID4), account_type_id (FK),
  status, currency, created_at

transactions                        ← event header (no mutable amounts)
  id, account_id (FK), public_id, type, status,
  description, created_at, updated_at

ledger_entries                      ← append-only double-entry journal
  id, transaction_id (FK), account_id (FK),
  amount (+ credit / - debit, Numeric(12,2)), created_at

users
  id, first_name, last_name, email, password (bcrypt), created_at

refresh_tokens
  id, user_id (FK), token, expires_at, is_revoked, created_at
```

**Double-Entry Journal Example — `100.00 PKR` Transfer from Alice to Bob:**

```text
transactions    → id=1, type=TRANSFER, status=COMPLETED
ledger_entries  → account=Alice, amount=-100.00  (Debit)
ledger_entries  → account=Bob,   amount=+100.00  (Credit)
────────────────────────────────────────────────────────
Net Ledger Sum  → 0.00 ✓
```

---

## Concurrency & Integrity Verification Suite

Financial correctness is verified under true multi-threaded contention using `pytest`, `ThreadPoolExecutor`, and `threading.Barrier` to force simultaneous execution against live PostgreSQL transactions.

### 1. Double-Spend / Race-Condition Withdrawal Test (`api/tests/test_withdraw.py`)
* **Scenario:** Account starts with `1000.00 PKR`. **5 concurrent threads** synchronize at a barrier and fire `POST /transaction/withdraw` for `800.00 PKR` at the exact same instant.
* **Verified Invariants:**
  * Exactly **1** request succeeds (`HTTP 200`).
  * Exactly **4** requests are rejected for insufficient funds (`HTTP 400`).
  * Final PostgreSQL ledger balance equals **`200.00 PKR`** (zero overdrafts).

### 2. Bidirectional Deadlock & Conservation of Money Test (`api/tests/test_transfer_concurrency.py`)
* **Scenario:** Alice (`1000.00 PKR`) and Bob (`1000.00 PKR`) fire **10 simultaneous transfers** (`5 × 100.00` Alice → Bob and `5 × 100.00` Bob → Alice) at a thread barrier.
* **Verified Invariants:**
  * **10/10** transfers succeed (`HTTP 200`) with **zero PostgreSQL deadlocks**.
  * Final balances settle at **`Alice: 1000.00 PKR | Bob: 1000.00 PKR`**.
  * System-wide conservation of money holds (`2000.00 PKR` before = `2000.00 PKR` after).

### Running the Verification Suite

```bash
pytest -v -s
```

**Verified Test Output:**

```text
collected 2 items

api/tests/test_transfer_concurrency.py::test_bidirectional_concurrent_transfers
[Bidirectional Transfer Proof] Status Codes: [200, 200, 200, 200, 200, 200, 200, 200, 200, 200]
[Bidirectional Transfer Proof] Alice Balance: 1000.00 | Bob Balance: 1000.00
PASSED

api/tests/test_withdraw.py::test_concurrent_withdrawals
[Concurrency Proof] Status Codes: [400, 400, 400, 200, 400]
[Concurrency Proof] Final Account Balance: 200.00
PASSED

================================= 2 passed in 4.51s =================================
```


# Non-Idempotent Retries Or Duplicate Transactions Problem/Solution

There we had a problem scenario, which goes like, imagine, if a user makes a transaction
and system process the transaction, checks balance, and commits it successfully. However, 
before Client sees the Response of request, that it was successful or failed, Client network
goes weak, and couldnt see the response of transaction.. Now the problem is that, system commited the 
transaction, transfer , withdrawl , or deposit was already done, but client couldnt see, Now client
assumes that, transaction failed, so he does a second transaction, now in system he actually did #2 transactions
instead of one. #That is the problem , a bigger one, that can do alot of damage to client.

# Idempotency-Key




---

## Tech Stack

| Layer | Technology | Role |
| :--- | :--- | :--- |
| **API Framework** | FastAPI | High-performance REST endpoints & OpenAPI docs |
| **Database** | PostgreSQL | ACID-compliant relational store & row-level locking |
| **ORM** | SQLAlchemy | Declarative models, session management & transactions |
| **Migrations** | Alembic | Version-controlled database schema migrations |
| **Security** | JWT (`python-jose`) + `bcrypt` | Stateless access tokens, salted password hashing & token rotation |
| **Validation** | Pydantic | Strict request/response schema enforcement |
| **Testing** | Pytest + `ThreadPoolExecutor` | Multi-threaded concurrency & ledger invariant verification |

---

## Local Setup & Installation

**Prerequisites:** Python 3.10+, PostgreSQL 14+

```bash
# 1. Clone the repository
git clone https://github.com/muhammads-git/wallet-api.git
cd wallet-api

# 2. Create and activate a virtual environment
python -m venv walletenv
source walletenv/bin/activate      # Linux / macOS
walletenv\Scripts\activate         # Windows PowerShell

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env

# 5. Apply database migrations
alembic upgrade head

# 6. Start the development server
uvicorn api.main:app --reload
```

### Environment Variables (`.env`)

```env
DATABASE_URL=postgresql://user:password@localhost:5432/wallet_db
APP_SECRET=your_super_secret_jwt_key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRY=30
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/register` | Register a new user with bcrypt-hashed credentials |
| `POST` | `/api/login` | Authenticate user; returns Bearer access token & sets `httpOnly` refresh cookie |
| `POST` | `/refresh` | Rotate refresh token and issue a new access token |

### Accounts

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/api/accounts` | Provision a new wallet account linked to an `AccountType` |
| `GET` | `/v1/api/accounts` | Retrieve account metadata and derived ledger balance |

### Transactions

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/transaction/deposit` | Credit funds to an account via an atomic ledger entry |
| `POST` | `/transaction/withdraw` | Debit funds with row-locked balance verification |
| `POST` | `/transaction/transfer` | Execute an atomic double-entry P2P transfer (`reciever_public_id`) |
| `GET` | `/transaction/history` | Retrieve paginated/full immutable transaction log |
| `GET` | `/transaction/{id}` | Inspect single transaction header and associated ledger entries |

---

## Transfer Execution Flow

```text
POST /transaction/transfer
  { "reciever_public_id": "...", "amount": 100.00, "description": "..." }

1. Acquire deterministic row-level locks on sender and receiver accounts
2. Verify sender has sufficient derived balance (SUM query on ledger_entries)
3. Create immutable transaction header (status = PENDING)
4. Insert debit ledger entry for sender (-100.00)
5. Insert credit ledger entry for receiver (+100.00)
6. Update transaction status to COMPLETED
7. Single atomic database commit — all or nothing
```

---

## Roadmap

- [x] Double-entry ledger schema & derived balance architecture
- [x] Stateful refresh token rotation via `httpOnly` cookies
- [x] Multi-threaded concurrency & deadlock test suite (`pytest`)
- [ ] Platform fee engine routing fees to `SYSTEM_FEES` ledger accounts
- [ ] Idempotency keys (`Idempotency-Key` header) for safe client retries
- [ ] Account freeze & daily velocity limit enforcement via `account_types`
- [ ] Docker & `docker-compose` production deployment setup
