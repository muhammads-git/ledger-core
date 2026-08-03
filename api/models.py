from sqlalchemy import String,Column,BigInteger
from sqlalchemy.orm import sessionmaker,mapped_column,Mapped
from api.database import BASE
import uuid


class Account(BASE):
   __tablename__ = 'accounts'

   id : Mapped[int] = mapped_column(BigInteger=True,primary_key=True,autoincrement=True)
   
   public_id : Mapped[uuid.UUID] = mapped_column()