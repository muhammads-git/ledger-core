from pydantic import BaseModel

class CreateAccount(BaseModel):
   account_type : str
   first_name : str
   last_name : str
   currency : str
   
class TransferCredentials(BaseModel):
   public_id : str
   money : int
   