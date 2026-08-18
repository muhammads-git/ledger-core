from fastapi import FastAPI,HTTPException,Depends,APIRouter,Query,status
from sqlalchemy.orm import Session
from api.database import get_db
from api.schema.schema import TransferCredentials
from api.models import Account,AccountType,Transaction,LedgerEntries
from api.auths.auths_utitlies import getCurrentUser
from api.schema.schema import CreateAccountRequest
from api.models import AccountTypeCode,AccountTypeName
from api.schema.schema import CurrencyEnum

router=APIRouter()


@router.post('/api/accounts', status_code=status.HTTP_201_CREATED)
def create_account(
    # This 'name' field now shows as a dropdown with "Savings Account", "Standard Checking", etc.
    name: AccountTypeName = Query(..., description="Select the account type name"),
    account_code: AccountTypeCode = Query(..., description="Select the system account code"),
    currency: CurrencyEnum = Query(..., description="Select the currency"),
    db: Session = Depends(get_db),
    current_user = Depends(getCurrentUser)
):
    # 1. Handle AccountType insertion
    # We use .value to get the string from the Enum selection
    new_acc_type = AccountType(
        name=name.value,         # e.g., "Standard Checking"
        code=account_code.value   # e.g., "CHECKINGS"
    )
    db.add(new_acc_type)

    # 2. Link to new Account
    new_acc = Account(
        user_id=current_user.id,
        account_type_id=new_acc_type.id,
        currency=currency.value
    )
    db.add(new_acc)
    db.commit()
    db.refresh(new_acc)

    return {
        'success': True,
        'message': 'Account created successfully.',
        'details': {
            'public_id': new_acc.public_id,
            'account_status': new_acc.status,
            'currency': new_acc.currency
        }
    }


@router.get('/api/accounts')
def get_account_details(db : Session = Depends(get_db),current_user = Depends(getCurrentUser)):

   """ fetch account details """
   pass

