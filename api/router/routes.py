from fastapi import FastAPI,HTTPException,Depends,APIRouter
from sqlalchemy.orm import Session
from api.database import get_db
from api.schema.schema import TransferCredentials
from api.models import Account,AccountType,Transaction,LedgerEntries


router=APIRouter()

@router.post('/api/transfer_money')
def transfer_money(transfer: TransferCredentials, db : Session = Depends(get_db)):
   """ Search for public id in DB.
       current user ID,
       Insert into Transaction,
       Insert and Entry in LedgerEntry
   """
   return 'Transfer successful!'

@router.post('/api/create_account')
def create_account(db : Session = Depends(get_db)):
   pass
