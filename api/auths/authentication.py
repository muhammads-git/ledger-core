from api.scehma.schema import UserLogin,UserRegister
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from api.database import get_db
from api.models import User,AccountType,Account,AccountTypeCode
from api.auths.auths_utitlies import hashPassword,checkPassword,createAccessToken,decodeToken

auths_router = APIRouter()


@auths_router.post('/api/register')
def register(user : UserRegister, db : Session = Depends(get_db)):
   # take the credentials...
   existing = db.query(User).filter(
        (User.email == user.email)
    ).first()

    # check 
   if existing:
        raise HTTPException(status_code=404, detail='Email already taken!')
   
   # hash the password 
   hashed_password = hashPassword(user.password)

   new_user = User(
      first_name = user.first_name,
      last_name = user.last_name,
      email = user.email,
      password = hashed_password
   )

   db.add(new_user)
   db.commit()
   db.refresh(new_user)

   return {'success': True,
           'message':'User registraion successful!',
           'details':{
              'email':new_user.email,
              'password':new_user.password
           }}


# Login route
@auths_router.post('/login')
def login(user : UserLogin, db: Session = Depends(get_db)):
    # now the OAuth2PasswordRequestForm will automatically handle forms
    print('i am hitting your login for authentication....')
    user = db.query(User).filter(
        (User.email == user.email)
    ).first()

    if not user or not checkPassword(user.password, User.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
   #  create token
    accessToken = createAccessToken(data={'sub':user.username})
    print(accessToken)
   # return access token and its type
    return {'access_token': accessToken, 'token_type': 'bearer'}

