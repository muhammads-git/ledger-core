from fastapi import FastAPI,HTTPException,Depends
from sqlalchemy.orm import Session
from api.database import get_db
from api.scehma.schema import TransferCredentials

router=FastAPI()

@router.post('/api/transfer_money')
def transfer_money(transfer: TransferCredentials, db : Session = Depends(get_db)):
   """ Search for public id in DB.
       current user ID,
       Insert into Transaction,
       Insert and Entry in LedgerEntry
   """