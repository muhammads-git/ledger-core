from sqlalchemy import String,Column,BigInteger,Integer,DateTime,ForeignKey,Numeric,Index,Boolean,Enum as sqlEnum
from sqlalchemy.orm import sessionmaker,mapped_column,Mapped
from api.database import BASE
import uuid
from datetime import datetime,timezone,timedelta
import enum


# ENUMSSS
class AccountTypeCode(str,enum.Enum):
    CHECKINGS = 'CHECKINGS'
    SAVINGS = 'SAVINGS'       
    SYSTEM_FEES = 'SYSTEM_FEES'


class TransactionStatus(str,enum.Enum):
    pending = "PENDING"
    completed = "COMPLETED"
    failed = "FAILED"

class TransactionType(str,enum.Enum):
    transfer = "TRANSFER"
    withdrawl = "WITHDRAWL"
    deposit = "DEPOSIT"

class AccountTypeName(str, enum.Enum):
    SAVINGS = "Savings Account"
    CHECKING = "Standard Checking"
    BUSINESS = "Business Account"
    WALLET = "Digital Wallet"

class User(BASE):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(50), nullable=False)
    
    last_name = Column(String(50), nullable=True) 
    
    email = Column(String(100), index=True, unique=True, nullable=False)
    password = Column(String(255), nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    #  Composite Index on full name search
    __table_args__ = (
        Index('idx_user_full_name', 'first_name', 'last_name'),
    )

# refresh token schema
class RefreshToken(BASE):
    __tablename__ = 'refresh_tokens'

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String, unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'))
    expires_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc) + timedelta(days=7))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_revoked = Column(Boolean, default=False, nullable=False)
    
class Account(BASE):
    __tablename__ = 'accounts'
    
    # BigInteger is best for high-volume banking primary keys
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Public ID: Stored as a string, defaults to a random UUID4
    public_id = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)

    # account type id, 
    account_type_id = Column(Integer, ForeignKey('account_types.id'),nullable=False)

    # Account status (e.g., 'active', 'frozen', 'closed')
    status = Column(String(20), default='active', nullable=False)
    
    # Financial architecture: currency USD,PKR
    currency = Column(String(3), default='PKR', nullable=False) 
    
    # Timezone-aware creation time
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)



# 2. Your AccountType Table
class AccountType(BASE):
    __tablename__ = 'account_types'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(sqlEnum(AccountTypeName), nullable=False) # e.g., "Standard Checking"

    # .value so SQLAlchemy stores the raw string ('CHECKINGS') in the database
    code = Column(String(20), default=AccountTypeCode.CHECKINGS.value, nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class Transaction(BASE):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True,autoincrement=True)

    public_id = Column(String(36),default=lambda: str(uuid.uuid4()),unique=True, nullable=False)

    account_id = Column(Integer,ForeignKey('accounts.id'),nullable=False)

    status = Column(String, default=TransactionStatus.pending)

    # default transaction type is transfer
    type = Column(String, default=TransactionType.transfer)

    created_at = Column(DateTime,default=lambda: datetime.now(timezone.utc),nullable=False)

    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc),nullable=False)

    description = Column(String(255),nullable=False)


class LedgerEntries(BASE):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True,autoincrement=True)

    transaction_id = Column(Integer,ForeignKey('transactions.id'),nullable=True)

    account_id = Column(Integer,ForeignKey('accounts.id'),nullable=False)

    # Numeric not flaot.
    amount = Column(Numeric(precision=12,scale=2),nullable=False)

    created_at = Column(DateTime,default=lambda: datetime.now(timezone.utc),nullable=False)
    
