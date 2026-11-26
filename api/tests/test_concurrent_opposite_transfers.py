import threading
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.main import app
from api.database import SessionLocal
from api.models import (
    User,
    Account,
    AccountType,
    AccountTypeCode,
    AccountTypeName,
    LedgerEntries,
    Transaction,
    TransactionType,
)
from api.auths.auths_utitlies import hashPassword


TEST_PASSWORD = "TestPassword123!"


@pytest.fixture
def opposite_transfer_setup():
    """Create two fresh users, accounts, and initial balances."""

    db = SessionLocal()

    try:
        # 1. Get or create account type
        acc_type = db.query(AccountType).filter(
            AccountType.code == AccountTypeCode.CHECKINGS.value
        ).first()

        if not acc_type:
            acc_type = AccountType(
                name=AccountTypeName.CHECKING.value,
                code=AccountTypeCode.CHECKINGS.value,
            )
            db.add(acc_type)
            db.flush()

        # 2. Generate unique test users
        unique_id = uuid4().hex

        user_a = User(
            first_name="Sender",
            last_name="A",
            email=f"sender_a_{unique_id}@ledgercore.internal",
            password=hashPassword(TEST_PASSWORD),
        )

        user_b = User(
            first_name="Sender",
            last_name="B",
            email=f"sender_b_{unique_id}@ledgercore.internal",
            password=hashPassword(TEST_PASSWORD),
        )

        db.add_all([user_a, user_b])
        db.flush()

        # 3. Create both accounts
        account_a = Account(
            user_id=user_a.id,
            account_type_id=acc_type.id,
            status="active",
            currency="PKR",
        )

        account_b = Account(
            user_id=user_b.id,
            account_type_id=acc_type.id,
            status="active",
            currency="PKR",
        )

        db.add_all([account_a, account_b])
        db.flush()

        # 4. Give both accounts Rs. 1000
        db.add_all([
            LedgerEntries(
                account_id=account_a.id,
                transaction_id=None,
                amount=Decimal("1000.00"),
            ),
            LedgerEntries(
                account_id=account_b.id,
                transaction_id=None,
                amount=Decimal("1000.00"),
            ),
        ])

        db.commit()

        return {
            "user_a_email": user_a.email,
            "user_b_email": user_b.email,
            "account_a_id": account_a.id,
            "account_b_id": account_b.id,
            "account_a_public_id": str(account_a.public_id),
            "account_b_public_id": str(account_b.public_id),
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def test_concurrent_opposite_transfers(opposite_transfer_setup):

    setup = opposite_transfer_setup

    # 1. Authenticate both users
    with TestClient(app) as client:

        login_a = client.post(
            "/api/login",
            data={
                "username": setup["user_a_email"],
                "password": TEST_PASSWORD,
            },
        )

        login_b = client.post(
            "/api/login",
            data={
                "username": setup["user_b_email"],
                "password": TEST_PASSWORD,
            },
        )

        assert login_a.status_code == 200, login_a.text
        assert login_b.status_code == 200, login_b.text

        token_a = login_a.json()["access_token"]
        token_b = login_b.json()["access_token"]

    # 2. Prepare opposite transfer requests
    barrier = threading.Barrier(2)

    def transfer_a_to_b():

        with TestClient(app) as client:

            barrier.wait()

            return client.post(
                "/transaction/transfer",
                json={
                    "reciever_public_id": setup["account_b_public_id"],
                    "amount": "100.00",
                    "description": "Concurrent A to B",
                },
                headers={
                    "Authorization": f"Bearer {token_a}",
                    "Idempotency-Key": str(uuid4()),
                },
            )

    def transfer_b_to_a():

        with TestClient(app) as client:

            barrier.wait()

            return client.post(
                "/transaction/transfer",
                json={
                    "reciever_public_id": setup["account_a_public_id"],
                    "amount": "100.00",
                    "description": "Concurrent B to A",
                },
                headers={
                    "Authorization": f"Bearer {token_b}",
                    "Idempotency-Key": str(uuid4()),
                },
            )

    # 3. Execute both transfers concurrently
    with ThreadPoolExecutor(max_workers=2) as executor:

        future_a = executor.submit(transfer_a_to_b)
        future_b = executor.submit(transfer_b_to_a)

        response_a = future_a.result(timeout=20)
        response_b = future_b.result(timeout=20)

    print("\n[Deadlock Test]")
    print("A -> B:", response_a.status_code, response_a.text)
    print("B -> A:", response_b.status_code, response_b.text)

    # 4. Both transfers should succeed
    assert response_a.status_code == 200, response_a.text
    assert response_b.status_code == 200, response_b.text

    # 5. Verify database state
    db = SessionLocal()

    try:
        account_ids = [
            setup["account_a_id"],
            setup["account_b_id"],
        ]

        # Both balances should return to Rs. 1000
        for account_id in account_ids:

            balance = db.execute(
                text("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM ledger_entries
                    WHERE account_id = :account_id
                """),
                {"account_id": account_id},
            ).scalar()

            assert Decimal(str(balance)) == Decimal("1000.00")

        # Exactly two transfer transactions should exist
        transactions = db.query(Transaction).filter(
            Transaction.account_id.in_(account_ids),
            Transaction.type == TransactionType.transfer,
        ).all()

        assert len(transactions) == 2

        # Each transaction must have two ledger entries
        for transaction in transactions:

            entries = db.query(LedgerEntries).filter(
                LedgerEntries.transaction_id == transaction.id
            ).all()

            assert len(entries) == 2

            transaction_total = sum(
                (entry.amount for entry in entries),
                Decimal("0.00"),
            )

            assert transaction_total == Decimal("0.00")

        print("[Deadlock Test] Both transfers completed.")
        print("[Deadlock Test] Both balances: Rs. 1000.00")
        print("[Deadlock Test] Ledger entries balanced.")

    finally:
        db.close()


        # read the code, and review the simultenous tranfers , not 1 first 2 later... 
        # the reason of using threading module is to ensure boht request run with two threads, 
        # each thread runs its transaction, using brarier reason is that, barrier would stop and start
        # the request at the same time, mean both threads start executing the code at the exact milisecond ..
        ## DONE ... 