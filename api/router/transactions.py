from fastapi import FastAPI,HTTPException,Depends,APIRouter,Query,status,Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.database import get_db
from api.schema.schema import TransferCredentials
from api.models import Account,AccountType,Transaction,LedgerEntries,IdempotencyRecords
from api.auths.auths_utitlies import getCurrentUser
from api.schema.schema import CreateAccountRequest
from api.models import AccountTypeCode,AccountTypeName,Transaction,LedgerEntries,TransactionStatus,TransactionType
from api.schema.schema import CurrencyEnum
from api.schema.schema import depositRequest,withdrawRequest,TransferCredentials
from uuid import UUID


trans_router = APIRouter()

SYSTEM_CLEARING_PUBLIC_ID = "00000000-0000-4000-8000-000000000001"

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


   
   ### get SYSTEM ACCOUNT DETAILS
   clearing_acc = db.query(Account).filter(Account.public_id == str(SYSTEM_CLEARING_PUBLIC_ID)).first()
   if not clearing_acc:
    raise HTTPException(status_code=500, detail="System clearing account not configured.")


   # ledger entry for this tranaction
   ledger_entry = LedgerEntries(transaction_id=new_transaction.id,
                                account_id=new_transaction.account_id,
                                amount=deposit.amount
                               )
   # balance - from bank account
   ledger_entry2 = LedgerEntries(transaction_id=new_transaction.id,
                                 account_id=clearing_acc.id,
                                 amount=-deposit.amount)
   
   db.add(ledger_entry)
   db.add(ledger_entry2)
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
   # user details
   user = db.query(Account).filter(Account.user_id == current_user.id).with_for_update().first()  #lock this ID row...
   # check current_balance
   current_balance = db.execute(text('Select SUM(amount) from ledger_entries WHERE account_id =:account_id '),{
      'account_id':user.id
   }).scalar() or 0

   # check balance 
   if current_balance < withdraw.amount:
      raise HTTPException(status_code=400, detail='Insufficient funds.')

   ### get SYSTEM ACCOUNT DETAILS
   clearing_acc = db.query(Account).filter(Account.public_id == str(SYSTEM_CLEARING_PUBLIC_ID)).first()
   if not clearing_acc:
    raise HTTPException(status_code=500, detail="System clearing account not configured.")


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
                                amount=-withdraw.amount)

   # an entry to BANK added amount to bank
   ledger_entry2 = LedgerEntries(transaction_id=new_transaction.id,
                                account_id= clearing_acc.id,
                                amount=withdraw.amount)

   db.add(ledger_entry)
   db.add(ledger_entry2)
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
def transfer_money(request: Request,transfer : TransferCredentials, db : Session = Depends(get_db),current_user=Depends(getCurrentUser)):
   user = db.query(Account).filter(Account.user_id == current_user.id).first()
   # get the request header
   idempotency_key_from_header = request.headers.get('Idempotency-Key')
   # check key in db
   idempotency_key = db.query(IdempotencyRecords).filter(IdempotencyRecords.user_id == current_user.id,
                          
                                                    idempotency_key == idempotency_key_from_header).first()
   # check if the idempotency key is same but request hash is diiff and reject with 409 conflict

   if not idempotency_key:

     # process the 
      # check current_balance
      current_balance = db.execute(text('Select SUM(amount) from ledger_entries WHERE account_id =:account_id '),{
         'account_id':user.id
      }).scalar() or 0

      # check balance 
      if current_balance < transfer.amount:
         raise HTTPException(status_code=400, detail='Insufficient funds.')

      # transfer money
      # find account with this public id
      reciever_acc = db.query(Account).filter(Account.public_id == str(transfer.reciever_public_id)).first()
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
      amount=-transfer.amount          # - negative — money leaving
   )

      # Entry 2 — credit receiver (money arriving)
      receiver_entry = LedgerEntries(
      transaction_id=new_transaction.id,
      account_id=reciever_acc.id,      # receiver
      amount=transfer.amount           # + positive — money arriving
   )

      db.add(sender_entry)
      db.add(receiver_entry)

      response_payload =  {
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
      # hash the request data... using hashRequest
      from api.services.request_hash import hashRequest
      request_hash = hashRequest(transfer)

      ## add idempotency key to db
      new_idempotency_key = IdempotencyRecords(
         user_id = user.id,
         idempotency_key=idempotency_key_from_header,
         transaction_id = new_transaction.id,
         response_payload = response_payload,
         response_status=200,
         request_hash=request_hash
      )

      # mark success
      new_transaction.status = TransactionStatus.completed
      db.commit()



   elif idempotency_key and idempotency_key.request_hash
      # fetch previous request data and return
      prev_trans = db.query(IdempotencyRecords).filter(IdempotencyRecords.idempotency_key == idempotency_key).first()
      # get the transaction
      transaction_history = db.query(Transaction).filter(Transaction.id == prev_trans.transaction_id, Transaction.account_id == prev_trans.account_id).first()
      # get the ledger entries of that transaction
      ledger_entries = db.query(LedgerEntries).filter(LedgerEntries.transaction_id == transaction_history.id).all()
      for entry in ledger_entries:
         account=entry.account_id
         amount = entry.amount
         # check for senders and reciever 
         if amount < 0:
            sender_amount  = amount
            sender_account_id = account
         else:
            reciever_amount = amount
            reciever_account_id = account

      #fetch the public id for these IDS
      sender_details = db.query(Account).filter(Account.user_id == sender_account_id).first()            
      reciever_details = db.query(Account).filter(Account.user_id == reciever_account_id).first()


      return {
         'message':'Transaction successful.',
         'details' : {
            'from_account':sender_details.public_id,
            'to_account':reciever_details.public_id,
            'TYPE':TransactionType.transfer,
            'sender_amount':sender_amount,
            'reciver_amount':reciever_amount,
            'STATUS':transaction_history.status
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






