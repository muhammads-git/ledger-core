import threading
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.main import app
from api.database import SessionLocal
from api.models import User, Account, AccountType, AccountTypeCode, AccountTypeName, LedgerEntries
from api.auths.auths_utitlies import hashPassword


USER_A_EMAIL = "alice_qa@ledgercore.internal"
USER_B_EMAIL = "bob_qa@ledgercore.internal"
TEST_PASSWORD = "TestPassword123!"
INITIAL_BALANCE = Decimal("1000.00")


def _seed_user_and_account(db, first_name: str, email: str, acc_type_id: int) -> Account:
    user = db.query(User).filter(User.email == email).first()
    hashed_pw = hashPassword(TEST_PASSWORD)

    if not user:
        user = User(
            first_name=first_name,
            last_name="QA",
            email=email,
            password=hashed_pw,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.password = hashed_pw
        db.commit()

    account = db.query(Account).filter(Account.user_id == user.id).first()
    if not account:
        account = Account(
            user_id=user.id,
            account_type_id=acc_type_id,
            status="active",
            currency="PKR",
        )
        db.add(account)
        db.commit()
        db.refresh(account)

    # Reset balance to exactly 1000.00
    db.query(LedgerEntries).filter(LedgerEntries.account_id == account.id).delete()
    db.add(
        LedgerEntries(
            account_id=account.id,
            transaction_id=None,
            amount=INITIAL_BALANCE,
        )
    )
    db.commit()
    return account


@pytest.fixture
def setup_two_users():
    """Creates Alice and Bob with 1000.00 PKR each and returns their account details."""
    db = SessionLocal()
    try:
        acc_type = db.query(AccountType).filter(AccountType.code == AccountTypeCode.CHECKINGS.value).first()
        if not acc_type:
            acc_type = AccountType(
                name=AccountTypeName.CHECKING.value,
                code=AccountTypeCode.CHECKINGS.value,
            )
            db.add(acc_type)
            db.commit()
            db.refresh(acc_type)

        acc_a = _seed_user_and_account(db, "Alice", USER_A_EMAIL, acc_type.id)
        acc_b = _seed_user_and_account(db, "Bob", USER_B_EMAIL, acc_type.id)

        return {
            "acc_a_id": acc_a.id,
            "acc_a_public_id": acc_a.public_id,
            "acc_b_id": acc_b.id,
            "acc_b_public_id": acc_b.public_id,
        }
    finally:
        db.close()


def _login(email: str) -> str:
    with TestClient(app) as client:
        res = client.post(
            "/api/login",
            data={"username": email, "password": TEST_PASSWORD},
        )
        assert res.status_code == 200, f"Login failed for {email}: {res.text}"
        return res.json()["access_token"]


def test_bidirectional_concurrent_transfers(setup_two_users):
    """
    Fires 10 simultaneous transfers:
      - 5 threads: Alice -> Bob (100.00 each = 500.00)
      - 5 threads: Bob -> Alice (100.00 each = 500.00)
    Tests:
      1. Zero PostgreSQL deadlocks (consistent row lock ordering)
      2. Zero lost updates (conservation of total system money = 2000.00)
    """
    token_a = _login(USER_A_EMAIL)
    token_b = _login(USER_B_EMAIL)

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # NOTE: Adjust payload keys below if your /transaction/transfer route uses
    # 'recipient_account_id' / 'receiver_public_id' / 'to_account' etc.
    payload_a_to_b = {
        "reciever_public_id": setup_two_users["acc_b_public_id"],
        "amount": 100,
        "description": "Alice to Bob concurrent test",
    }
    payload_b_to_a = {
        "reciever_public_id": setup_two_users["acc_a_public_id"],
        "amount": 100,
        "description": "Bob to Alice concurrent test",
    }


    transfers_per_side = 5
    total_threads = transfers_per_side * 2
    barrier = threading.Barrier(total_threads)

    def fire_transfer(headers: dict, payload: dict):
        with TestClient(app) as client:
            barrier.wait()
            res = client.post("/transaction/transfer", json=payload, headers=headers)
            return res.status_code, res.text

    tasks = (
        [(headers_a, payload_a_to_b)] * transfers_per_side
        + [(headers_b, payload_b_to_a)] * transfers_per_side
    )

    with ThreadPoolExecutor(max_workers=total_threads) as executor:
        futures = [executor.submit(fire_transfer, h, p) for h, p in tasks]
        results = [f.result() for f in futures]

    status_codes = [code for code, _ in results]
    print(f"\n[Bidirectional Transfer Proof] Status Codes: {status_codes}")
    for code, body in results:
        if code != 200:
            print(f"[Failure Detail] {code}: {body}")

    # 1. Every transfer should succeed without deadlocks or 500 errors
    assert status_codes.count(200) == total_threads, f"Expected all {total_threads} to succeed, got {results}"

    # 2. Verify exact ledger balances in PostgreSQL
    db = SessionLocal()
    try:
        bal_a = db.execute(
            text("SELECT COALESCE(SUM(amount), 0) FROM ledger_entries WHERE account_id = :id"),
            {"id": setup_two_users["acc_a_id"]},
        ).scalar()
        bal_b = db.execute(
            text("SELECT COALESCE(SUM(amount), 0) FROM ledger_entries WHERE account_id = :id"),
            {"id": setup_two_users["acc_b_id"]},
        ).scalar()

        bal_a = Decimal(str(bal_a))
        bal_b = Decimal(str(bal_b))
        print(f"[Bidirectional Transfer Proof] Alice Balance: {bal_a} | Bob Balance: {bal_b}")

        assert bal_a == Decimal("1000.00"), f"Alice balance drift: {bal_a}"
        assert bal_b == Decimal("1000.00"), f"Bob balance drift: {bal_b}"
        assert bal_a + bal_b == Decimal("2000.00"), "Conservation of money violated!"
    finally:
        db.close()
