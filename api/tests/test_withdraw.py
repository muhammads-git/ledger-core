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


TEST_EMAIL = "qa_test@ledgercore.internal"
TEST_PASSWORD = "TestPassword123!"


@pytest.fixture(autouse=True)
def ensure_test_user_and_balance():
    """Creates or resets the QA user, account type, account, and 1000.00 ledger balance."""
    db = SessionLocal()
    try:
        # 1. Ensure an AccountType exists (required by Account.account_type_id)
        acc_type = db.query(AccountType).filter(AccountType.code == AccountTypeCode.CHECKINGS.value).first()
        if not acc_type:
            acc_type = AccountType(
                name=AccountTypeName.CHECKING.value,
                code=AccountTypeCode.CHECKINGS.value,
            )
            db.add(acc_type)
            db.commit()
            db.refresh(acc_type)

        # 2. Create or update the QA User with a valid bcrypt hash
        user = db.query(User).filter(User.email == TEST_EMAIL).first()
        hashed_pw = hashPassword(TEST_PASSWORD)

        if not user:
            user = User(
                first_name="QA",
                last_name="Tester",
                email=TEST_EMAIL,
                password=hashed_pw,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.password = hashed_pw
            db.commit()

        # 3. Ensure the User has an active Account
        account = db.query(Account).filter(Account.user_id == user.id).first()
        if not account:
            account = Account(
                user_id=user.id,
                account_type_id=acc_type.id,
                status="active",
                currency="PKR",
            )
            db.add(account)
            db.commit()
            db.refresh(account)

        # 4. Reset LedgerEntries so starting balance is strictly 1000.00
        db.query(LedgerEntries).filter(LedgerEntries.account_id == account.id).delete()
        db.add(
            LedgerEntries(
                account_id=account.id,
                transaction_id=None,
                amount=Decimal("1000.00"),
            )
        )
        db.commit()
    finally:
        db.close()


def test_concurrent_withdrawals():
    # 1. Authenticate via your real OAuth2PasswordBearer login route
    with TestClient(app) as auth_client:
        login_res = auth_client.post(
            "/api/login",
            data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Synchronize 5 threads at a Barrier to fire simultaneously
    num_threads = 5
    barrier = threading.Barrier(num_threads)

    def attempt_withdraw():
        with TestClient(app) as client:
            barrier.wait()
            res = client.post(
                "/transaction/withdraw",
                json={"amount": 800, "description": "Concurrency lock test"},
                headers=headers,
            )
            return res.status_code

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(attempt_withdraw) for _ in range(num_threads)]
        status_codes = [f.result() for f in futures]

    print(f"\n[Concurrency Proof] Status Codes: {status_codes}")

    # 3. Assert exact QA invariants
    assert status_codes.count(200) == 1, f"Expected 1 success, got {status_codes}"
    assert status_codes.count(400) == 4, f"Expected 4 rejections, got {status_codes}"

    # 4. Verify final balance in PostgreSQL
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == TEST_EMAIL).first()
        account = db.query(Account).filter(Account.user_id == user.id).first()
        final_balance = db.execute(
            text("SELECT COALESCE(SUM(amount), 0) FROM ledger_entries WHERE account_id = :acc_id"),
            {"acc_id": account.id},
        ).scalar()

        print(f"[Concurrency Proof] Final Account Balance: {final_balance}")
        assert Decimal(str(final_balance)) == Decimal("200.00")
    finally:
        db.close()
