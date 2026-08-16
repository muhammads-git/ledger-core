from pydantic import BaseModel,Field
import uuid
from decimal import Decimal
from enum import Enum


############  AUTHENTICATIONS
class UserRegister(BaseModel):
   first_name : str
   last_name : str
   email : str
   password : str

class UserLogin(BaseModel):
   email : str
   password : str


####################### 
class CurrencyEnum(str,Enum):
   PKR = 'PKR'
   USD = 'USD'

class CreateAccountRequest(BaseModel):
   name : Enum
   account_type : str
   currency : CurrencyEnum

class TransferCredentials(BaseModel):
   reciever_public_id : uuid.UUID
   money : Decimal = Field(gt=0, decimal_places=2)

   