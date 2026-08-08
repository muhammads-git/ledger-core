from pydantic import BaseModel


class TransferCredentials(BaseModel):
   public_id : str
   money : int
   