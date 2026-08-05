from sqlalchemy import String,Column,BigInteger,Integer,DateTime,ForeignKey,Enum
from sqlalchemy.orm import sessionmaker,mapped_column,Mapped
from api.database import BASE
import uuid
from datetime import datetime,timezone

class User(BASE):
   __tablename__ = 'users'

   id = Column(Integer,primary_key=True,autoincrement=True)
   first_name = Column(String,index=True,nullable=False)
   last_name = Column(String,)
   email = Column(String,index=True,nullable=False)
   password = Column(String,nullable=False)
   created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
   

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

class AccountTypeCode(Enum):
    CHECKINGS = 'CHECKINGS'
    SAVINGS = 'SAVINGS'       
    SYSTEM_FEES = 'SYSTEM_FEES'

# 2. Your AccountType Table
class AccountType(BASE):
    __tablename__ = 'account_types'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False) # e.g., "Standard Checking"

    
    # .value so SQLAlchemy stores the raw string ('CHECKINGS') in the database
    code = Column(String(20), default=AccountTypeCode.CHECKINGS.value, nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)