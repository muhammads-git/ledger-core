from fastapi import FastAPI,HTTPException,Depends,APIRouter,Query,status
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.database import get_db
from api.schema.schema import TransferCredentials
from api.models import Account,AccountType,Transaction,LedgerEntries
from api.auths.auths_utitlies import getCurrentUser
from api.schema.schema import CreateAccountRequest
from api.models import AccountTypeCode,AccountTypeName,Transaction,LedgerEntries,TransactionStatus,TransactionType
from api.schema.schema import CurrencyEnum
from api.schema.schema import depositRequest,withdrawRequest

trans_router = APIRouter()


@trans_router.post('/transaction/deposit')
def deposit_money(deposit : depositRequest ,db : Session = Depends(get_db),current_user=Depends(getCurrentUser)):

   # fetch account details of this user 
   user = db.query(Account).filter(Account.user_id == current_user.id).first()
   # transaction 
   new_transaction = Transaction(account_id=user.id,
   public_id=user.public_id,
   type=TransactionType.deposit,
   description = deposit.description
   )
   db.add(new_transaction) # add the transaction
   db.flush() # gets the generated ID without committing

   # ledger entry for this tranaction
   ledger_entry = LedgerEntries(transaction_id=new_transaction.id,
                                account_id=new_transaction.account_id,
                                amount=deposit.amount
                                )
   db.add(ledger_entry)
   # trasaction status chagne
   new_transaction.status = TransactionStatus.completed
   # atomic commits
   db.commit()

   return {'success':True}

@trans_router.post('/transaction/withdraw')
def withdraw_money(withdraw : withdrawRequest,db : Session = Depends(get_db),current_user=Depends(getCurrentUser)):
   # trasaction entry
   user = db.query(Account).filter(Account.user_id == current_user.id).first()
   # check current_balance
   current_balance = db.execute(text('Select SUM(amount) from ledger_entries WHERE account_id =:account_id '),{
      'account_id':user.id
   }).scalar() or 0

   # check balance 
   if current_balance < withdraw.amount:
      raise HTTPException(status_code=400, detail='Insufficient funds.')

   # transaction 
   new_transaction = Transaction(account_id=user.id,
   public_id=user.public_id,
   type=TransactionType.withdrawl,
   description = withdraw.description
   )
   db.add(new_transaction) # add the transaction
   db.flush()

   # ledger entry
   ledger_entry = LedgerEntries(transaction_id=new_transaction.id,
                                account_id=new_transaction.account_id,
                                amount=withdraw.amount)

   # transaction status change
   new_transaction.status = TransactionStatus.completed
   db.commit()

   return {'success':True}


@trans_router.post('/transaction/transfer')
def transfer_money(db : Session = Depends(get_db),current_user=Depends(getCurrentUser)):
   pass




@trans_router.get('/transaction/history')
def history(db : Session = Depends(get_db),current_user=Depends(getCurrentUser)):
   pass



@trans_router.get('/transaction/{transaction_id}')
def transaction_detail(transaction_id : int, db : Session = Depends(get_db),current_user=Depends(getCurrentUser)):
   pass









