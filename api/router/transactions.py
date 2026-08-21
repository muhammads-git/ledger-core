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
from api.schema.schema import depositRequest,withdrawRequest,TransferCredentials

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
 
   return {
    'message': 'Transaction successful',
    'details': {
        'transaction_id': new_transaction.public_id,
        'type': new_transaction.type,
        'amount': deposit.amount,
        'description': deposit.description,
        'status': new_transaction.status
    }
}

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

   db.add(ledger_entry)
   # transaction status change
   new_transaction.status = TransactionStatus.completed

   db.commit()

   return {
    'message': 'Transaction successful',
    'details': {
        'transaction_id': new_transaction.public_id,
        'type': new_transaction.type,
        'amount': withdraw.amount,
        'description': withdraw.description,
        'status': new_transaction.status
    }
}


### double entry book keeping .... industrial way..
@trans_router.post('/transaction/transfer')
def transfer_money(transfer : TransferCredentials, db : Session = Depends(get_db),current_user=Depends(getCurrentUser)):
   user = db.query(Account).filter(Account.user_id == current_user.id).first()
   # check current_balance
   current_balance = db.execute(text('Select SUM(amount) from ledger_entries WHERE account_id =:account_id '),{
      'account_id':user.id
   }).scalar() or 0

   # check balance 
   if current_balance < transfer.amount:
      raise HTTPException(status_code=400, detail='Insufficient funds.')

   # transfer money
   # find account with this public id
   reciever_acc = db.query(Account).filter(Account.public_id == transfer.reciever_public_id).first()
   if not reciever_acc:
      raise HTTPException(status_code=404, detail='Account not found.')

   # check if the transafer is not the same account
   if reciever_acc.id == user.id:
    raise HTTPException(status_code=400, detail='Cannot transfer to yourself')
   
   # transaction
   new_transaction = Transaction(
      public_id=user.public_id,
      account_id=user.id,
      type=TransactionType.transfer,
      description=transfer.description


   )
   db.add(new_transaction)
   db.flush()

   # Entry 1 — debit sender (money leaving)
   sender_entry = LedgerEntries(
    transaction_id=new_transaction.id,
    account_id=user.id,              # sender
    amount=-transfer.amount          # negative — money leaving
)

   # Entry 2 — credit receiver (money arriving)
   receiver_entry = LedgerEntries(
    transaction_id=new_transaction.id,
    account_id=reciever_acc.id,      # receiver
    amount=transfer.amount           # positive — money arriving
)

   db.add(sender_entry)
   db.add(receiver_entry)

   # mark success
   new_transaction.status = TransactionStatus.success
   db.commit()


   return {
    'message': 'Transfer successful',
    'details': {
        'transaction_id': new_transaction.id,
        'from_account': user.public_id,
        'to_account': reciever_acc.public_id,
        'amount': transfer.amount,
        'description': transfer.description,
        'status': new_transaction.status
    }
}

@trans_router.get('/transaction/history')
def history(db : Session = Depends(get_db),current_user=Depends(getCurrentUser)):
  # fetch the user account
  user_acc = db.query(Account).filter(Account.user_id == current_user.id).first()
  if not user_acc:
     raise HTTPException(status_code=404,detail='User has no wallet account.')

  # user the account id to fetch all the transactions from table
  transactions_history = db.query(Transaction).filter(Transaction.account_id == user_acc.id).all()

  if not transactions_history:
     raise HTTPException(status_code=404,detail='No Transactions made yet from this account.')

  # return 
  return {'success':True,'detail':[{
     'transaction_id':t.id,
     'transaction_public_id':t.public_id,
     'TYPE':t.type,
     'transaction_description':t.description,
     'date_time':t.created_at,
     'STATUS':t.status
  } 
  for t in transactions_history
  ]}





@trans_router.get('/transaction/{transaction_id}')
def transaction_detail(transaction_id : int, db : Session = Depends(get_db),current_user=Depends(getCurrentUser)):
     # fetch the user account
  user_acc = db.query(Account).filter(Account.user_id == current_user.id).first()
  if not user_acc:
     raise HTTPException(status_code=404,detail='User has no wallet account.')

  # user the account id to fetch all the transactions from table
  t = db.query(Transaction).filter(Transaction.account_id == user_acc.id,Transaction.id == transaction_id).first()

  if not t:
     raise HTTPException(status_code=404,detail='No Transaction record found with this ID.')

  

  return {
    'success': True,
    'detail': {
        'transaction_id': t.id,
        'public_id': t.public_id,
        'type': t.type,
        'description': t.description,
        'status': t.status,
        'created_at': t.created_at
    }
}






