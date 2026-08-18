from api.schema.schema import UserLogin,UserRegister
from fastapi import APIRouter,Depends,HTTPException,Response,Request
from sqlalchemy.orm import Session
from api.database import get_db
from api.models import User,AccountType,Account,AccountTypeCode,RefreshToken
from api.auths.auths_utitlies import hashPassword,checkPassword,createAccessToken,decodeToken,createRefreshToken,getCurrentUser
from api.auths.auths_utitlies import createRefreshToken,createAccessToken
from datetime import datetime,timezone
from fastapi.security import OAuth2PasswordRequestForm

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
              'email':new_user.email
           }}


# Login route
@auths_router.post('/api/login')
def login(response : Response, user_data : OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # now the OAuth2PasswordRequestForm will automatically handle forms
    print('i am hitting your login for authentication....')
    user = db.query(User).filter(
        (User.email == user_data.username) # username is email
    ).first()

    if not user or not checkPassword(user_data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

   # user lowercase subjects for better 
    lowerCaseEmail= user.email.strip().lower()
    accessToken = createAccessToken(data={'sub':lowerCaseEmail})

    # create refresh token
    refreshToken = createRefreshToken()
    # save to httOnly cookie
    response.set_cookie(key='refresh_token',
                        value = refreshToken,
                        max_age=604800,
                        secure=False,
                        httponly=True,
                        samesite='lax')

    # save into db
    new_token = RefreshToken(
        user_id=user.id,
        token=refreshToken
        )
    db.add(new_token)
    db.commit()

   # return access token and its type
    return {'access_token': accessToken, 'token_type': 'bearer'}

@auths_router.post('/refresh')
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    
    # read refresh token from cookie
    cookie_refresh_token = request.cookies.get('refresh_token')
    if not cookie_refresh_token:
        raise HTTPException(status_code=401, detail='Refresh token missing')
    
    # validate in DB
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == cookie_refresh_token,
        RefreshToken.is_revoked == False
    ).first()
    
    if not db_token:
        raise HTTPException(status_code=401, detail='Invalid or revoked refresh token')
    
    # check expiry
    if db_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail='Refresh token expired')
    
    # get user
    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail='User not found')
    
    # revoke old token
    db_token.is_revoked = True
    db.commit()
    
    # create new tokens
    new_access_token = createAccessToken({'sub': user.email})
    new_refresh_token = createRefreshToken()
    
    # save new refresh token to DB
    db.add(RefreshToken(
        user_id=user.id,
        token=new_refresh_token
    ))
    db.commit()
    
    # set new refresh token in cookie
    response.set_cookie(
        key='refresh_token',
        value=new_refresh_token,
        max_age=604800,
        httponly=True,
        secure=False,
        samesite='lax'
    )
    
    return {'access_token': new_access_token, 'token_type': 'bearer'}

# 563d17fd-a514-4e97-bb74-49819b508de8