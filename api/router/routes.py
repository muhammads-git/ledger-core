from fastapi import FastAPI,HTTPException,Depends,APIRouter
from sqlalchemy.orm import Session
from api.database import get_db
from api.schema.schema import TransferCredentials
from api.models import Account,AccountType,Transaction,LedgerEntries
from api.auths.auths_utitlies import getCurrentUser
from api.schema.schema import CreateAccountRequest

router=APIRouter()


@router.post('/api/accounts')
def create_account(account : CreateAccountRequest,db : Session = Depends(get_db),current_user=Depends(getCurrentUser)):
   # check forms data
   if account.account_type not in ['USD','PKR']:
      raise HTTPException(status_code=422,detail=f'{account.account_type} not available.')

   # insert in account type
   new_acc_type = AccountType(name=account.name,
                      code=account.account_type)
   db.add(new_acc_type)
   db.commit()
   db.refresh(new_acc_type)

   # new account 
   new_acc = Account(user_id=current_user.id,
                     account_type_id=new_acc_type.id,
                     curreny=account.currency)
   db.add(new_acc)
   db.commit()


   




   
