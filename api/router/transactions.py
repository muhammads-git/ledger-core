from fastapi import FastAPI,HTTPException,Depends,APIRouter,Query,status,Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi.responses import JSONResponse
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


from fastapi import HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.services.request_hash import hashRequest


@trans_router.post('/transaction/transfer')
def transfer_money(
    request: Request,
    transfer: TransferCredentials,
    db: Session = Depends(get_db),
    current_user=Depends(getCurrentUser)
):
    try:
        user = db.query(Account).filter(
            Account.user_id == current_user.id
        ).first()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="Account not found."
            )

        # 1. Get idempotency key
        idempotency_key_from_header = request.headers.get(
            'Idempotency-Key'
        )

        if not idempotency_key_from_header:
            raise HTTPException(
                status_code=400,
                detail="Idempotency-Key header is required."
            )

        # 2. Calculate request hash
        request_hash = hashRequest(transfer)

        # 3. Check for an existing idempotency record
        existing_record = db.query(IdempotencyRecords).filter(
            IdempotencyRecords.user_id == current_user.id,
            IdempotencyRecords.idempotency_key == idempotency_key_from_header
        ).first()

        # 4. Handle retry/ means idempotecy key found with two cases!!
        if existing_record:

            # Same key, different request data
            if existing_record.request_hash != request_hash:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency key reused with different request data."
                )

            # Same key, same request data: replay original response
            return JSONResponse(
                status_code=existing_record.response_status,
                content=existing_record.response_payload
            )

        # 5. Process a new transfer

        current_balance = db.execute(
            text("""
                SELECT SUM(amount)
                FROM ledger_entries
                WHERE account_id = :account_id
            """),
            {"account_id": user.id}
        ).scalar() or 0

        if current_balance < transfer.amount:
            raise HTTPException(
                status_code=400,
                detail="Insufficient funds."
            )

        # Find receiver
        receiver_acc = db.query(Account).filter(
            Account.public_id == str(transfer.reciever_public_id)
        ).first()

        if not receiver_acc:
            raise HTTPException(
                status_code=404,
                detail="Account not found."
            )

        if receiver_acc.id == user.id:
            raise HTTPException(
                status_code=400,
                detail="Cannot transfer to yourself."
            )

        # 6. Create transaction
        new_transaction = Transaction(
            public_id=user.public_id,
            account_id=user.id,
            type=TransactionType.transfer,
            description=transfer.description
        )

        db.add(new_transaction)
        db.flush()

        # 7. Create double-entry ledger records
        sender_entry = LedgerEntries(
            transaction_id=new_transaction.id,
            account_id=user.id,
            amount=-transfer.amount
        )

        receiver_entry = LedgerEntries(
            transaction_id=new_transaction.id,
            account_id=receiver_acc.id,
            amount=transfer.amount
        )

        db.add(sender_entry)
        db.add(receiver_entry)

        # 8. Mark transaction completed
        new_transaction.status = TransactionStatus.completed

        # 9. Construct response
        response_payload = {
            "message": "Transfer successful",
            "details": {
                "transaction_id": new_transaction.id,
                "from_account": user.public_id,
                "to_account": receiver_acc.public_id,
                "amount": transfer.amount,
                "description": transfer.description,
                "status": new_transaction.status.value
                if hasattr(new_transaction.status, "value")
                else new_transaction.status
            }
        }

        # 10. Create idempotency record
        new_idempotency_record = IdempotencyRecords(
            user_id=current_user.id,
            idempotency_key=idempotency_key_from_header,
            transaction_id=new_transaction.id,
            response_payload=response_payload,
            response_status=200,
            request_hash=request_hash
        )

        db.add(new_idempotency_record)

        # 11. Commit everything together
        db.commit()

        # 12. Return original response
        return JSONResponse(
            status_code=200,
            content=response_payload
        )

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise


      



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






