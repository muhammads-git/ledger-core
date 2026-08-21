

"I'll use junction table for memberships so users can be in multiple orgs"
→ that's data architecture

"I'll use two ledger entries per transfer summing to zero"
→ that's financial architecture

"I'll store ConnectionManager in app.state so all routes share one instance"
→ that's state management architecture
Every single one of these is an architectural decision. You made all of them. You can explain all of them.

Architecture is just answers to these questions
How is data stored?          → database schema, relationships
How does data flow?          → request → cache → DB → response
How do components connect?   → API → queue → worker → DB
What happens when X fails?   → fallback, retry, error handling
How does it scale?           → caching, queues, load balancing
You've answered all of these questions in your projects. That IS architecture.

Why it felt "far from reach"
Because people use the word to sound impressive. "Microservices architecture." "Event-driven architecture." "Hexagonal architecture."
# Wallet API

A production-grade digital wallet REST API built with FastAPI. Implements double-entry ledger bookkeeping — the same accounting principle used by Stripe, PayPal, and modern banks — ensuring every transaction is immutable, auditable, and mathematically consistent.

---

## Why Double-Entry Ledger Instead of a Balance Column

Most wallet tutorials do this:

```python
user.balance += amount  # deposit
user.balance -= amount  # withdraw
```

This breaks in production. What happens during a database crash mid-transaction? What happens when you need to audit where every penny went? What happens when you add platform fees or multi-party splits?

This API stores no balance column anywhere. Balance is always calculated:

```sql
SELECT SUM(amount) FROM ledger_entries WHERE account_id = X
```

Every transaction maps to at least two ledger entries that must sum to zero. Debit one account, credit another. The math is in the data structure itself — not in application logic.

---

## Architecture Overview

```
Client Request
      ↓
FastAPI Application
      ↓
┌─────────────────────────────────────────┐
│  Auth Layer (JWT + Refresh Tokens)      │
│  Access Token  → 30 min, in memory      │
│  Refresh Token → 7 days, httpOnly cookie│
│  Rotation on every refresh              │
└─────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────┐
│  Double-Entry Ledger                    │
│                                         │
│  Layer 1 — accounts                     │
│  Layer 2 — transactions (event header)  │
│  Layer 3 — ledger_entries (debits/credits)│
│                                         │
│  Every transfer = 1 transaction         │
│                 + 2 ledger entries      │
│                 that sum to zero        │
└─────────────────────────────────────────┘
      ↓
PostgreSQL (SQLAlchemy ORM + Alembic)
```

---

## Key Design Decisions

**Immutable transactions**
Transactions are never updated after creation. Status moves from PENDING → SUCCESS or FAILED. No record is ever deleted. Full audit trail always available.

**Balance calculation from ledger**
No balance column exists. Current balance is always a SUM query over ledger entries. Impossible to have a balance that doesn't match transaction history.

**Atomic commits**
Every transfer creates a transaction header, a debit entry, and a credit entry in a single database transaction. If anything fails — nothing is saved. No partial transfers possible.

**Refresh token rotation**
Every time a refresh token is used to get a new access token, the old refresh token is immediately revoked in the database and a new one is issued. Stolen refresh tokens become useless after first legitimate use.

**httpOnly cookie for refresh token**
Refresh token is stored in an httpOnly cookie — inaccessible to JavaScript. XSS attacks that steal tokens from memory cannot reach the refresh token.

---

## Database Schema

```
account_types
  id, name, code, created_at

accounts
  id, user_id (FK), public_id, account_type_id (FK),
  currency, created_at

transactions                    ← event header, no amounts
  id, account_id (FK), public_id, type, status,
  description, created_at

ledger_entries                  ← where money actually moves
  id, transaction_id (FK), account_id (FK),
  amount (+ credit / - debit), created_at

users
  id, first_name, last_name, email, password, created_at

refresh_tokens
  id, user_id (FK), token, expires_at, is_revoked, created_at
```

**Transfer example — $100 from Alice to Bob:**

```
transaction (id=1, type=transfer, status=SUCCESS)
  ledger_entry (account=Alice, amount=-100.00)  ← debit
  ledger_entry (account=Bob,   amount=+100.00)  ← credit
  SUM = 0 ✓
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Framework | FastAPI | Async REST API |
| Database | PostgreSQL | Primary data store |
| ORM | SQLAlchemy | Models and queries |
| Migrations | Alembic | Schema version control |
| Auth | JWT + bcrypt | Stateless authentication |
| Validation | Pydantic | Request/response schemas |
| Server | Uvicorn | ASGI server |

---

## Setup & Installation

**Requirements:** Python 3.10+, PostgreSQL

```bash
# Clone
git clone https://github.com/muhammads-git/wallet-api.git
cd wallet-api

# Virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# Fill in your values

# Run migrations
alembic upgrade head

# Start the API
uvicorn main:app --reload
```

---

## Environment Variables

```
DATABASE_URL=your_postgresql_connection_string
SECRET_KEY=your_jwt_secret_key
ALGORITHM=HS256
```

---

## API Endpoints

### Authentication
```
POST /api/register       Register new user
POST /api/login          Login — returns access token + sets refresh cookie
POST /refresh            Refresh access token using httpOnly cookie
```

### Accounts
```
POST /v1/api/accounts    Create wallet account
GET  /v1/api/accounts    Get account details
```

### Transactions
```
POST /transaction/deposit      Deposit funds
POST /transaction/withdraw     Withdraw funds (balance check enforced)
POST /transaction/transfer     Transfer to another account (double-entry)
GET  /transaction/history      Full transaction history
GET  /transaction/{id}         Single transaction detail
```

---

## Authentication Flow

```
POST /api/login
  → returns access_token in body (30 min)
  → sets refresh_token in httpOnly cookie (7 days)

Every protected request:
  → Authorization: Bearer <access_token>

When access token expires:
  → POST /refresh (cookie sent automatically)
  → returns new access_token
  → old refresh token revoked
  → new refresh token set in cookie
```

---

## Transfer Flow

```
POST /transaction/transfer
  { "receiver_public_id": "...", "amount": 100.00, "description": "..." }

1. Verify sender has sufficient balance (SUM query on ledger)
2. Find receiver account by public_id
3. Create transaction header (PENDING)
4. Create debit ledger entry for sender (-100.00)
5. Create credit ledger entry for receiver (+100.00)
6. Mark transaction SUCCESS
7. Single atomic commit — all or nothing
```

---

## Planned Improvements

- Transaction fees with SYSTEM_FEES account (third ledger entry per transfer)
- Account freezing
- Pagination on transaction history
- Rate limiting per account
- Docker + docker-compose setup
- pytest test coverage

































