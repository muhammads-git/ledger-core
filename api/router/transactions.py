from fastapi import FastAPI,HTTPException,Depends,APIRouter,Query,status
from sqlalchemy.orm import Session
from api.database import get_db
from api.schema.schema import TransferCredentials
from api.models import Account,AccountType,Transaction,LedgerEntries
from api.auths.auths_utitlies import getCurrentUser
from api.schema.schema import CreateAccountRequest
from api.models import AccountTypeCode,AccountTypeName
from api.schema.schema import CurrencyEnum

trans_router = APIRouter()


@trans_router.post('/transaction/deposit')
def deposit_money(db : Session = Depends(get_db),current_user=Depends(getCurrentUser)):
   pass



@trans_router.post('/transaction/withdraw')
def withdraw_money(db : Session = Depends(get_db),current_user=Depends(getCurrentUser)):
   pass



@trans_router.post('/transaction/transfer')
def transfer_money(db : Session = Depends(get_db),current_user=Depends(getCurrentUser)):
   pass




@trans_router.get('/transaction/history')
def history(db : Session = Depends(get_db),current_user=Depends(getCurrentUser)):
   pass



@trans_router.get('/transaction/{transaction_id}')
def transaction_detail(transaction_id : int, db : Session = Depends(get_db),current_user=Depends(getCurrentUser)):
   pass









