from api.schema.schema import UserLogin,UserRegister
from fastapi import APIRouter,Depends,HTTPException,Response
from sqlalchemy.orm import Session
from api.database import get_db
from api.models import User,AccountType,Account,AccountTypeCode,RefreshToken
from api.auths.auths_utitlies import hashPassword,checkPassword,createAccessToken,decodeToken,createRefreshToken,getCurrentUser
from api.auths.auths_utitlies import createRefreshToken,createAccessToken

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
def login(response : Response, user_data : UserLogin, db: Session = Depends(get_db)):
    # now the OAuth2PasswordRequestForm will automatically handle forms
    print('i am hitting your login for authentication....')
    user = db.query(User).filter(
        (User.email == user_data.email)
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

   # return access token and its type
    return {'access_token': accessToken, 'token_type': 'bearer'}

##### refresh token endpoint
# making a decorator : which call this enpoint automatically when access token expires
@auths_router.post('/refresh')
def refresh_token(response : Response, db : Session = Depends(get_db), current_user = Depends(getCurrentUser)):
    """ 
    1. Check Old vd Old refresh token
    2. create fresh access token
    3. old refresh is_revoked=True
    4, create refres token save to db.
    """
    # automatically fetch token from browser cookie.
    cookie_refresh_token = response.cookies.get('refresh_token')
    if not cookie_refresh_token:
        raise HTTPException(status_code=401,detail='Refresh token is missing.')
    
    # get from db
    db_refresh_token =db.query(RefreshToken).filter(RefreshToken.user_id == current_user.id and RefreshToken.is_revoked == False).scalar()
    if not db_refresh_token:
        raise HTTPException(status_code=401,detail='Invalid or expired refresh token.')
    
    if cookie_refresh_token == db_refresh_token:
        # create Access token 
        new_access_token = createAccessToken({'sub':current_user.email})
        # is_revoked = True where refresh token is this...
        token = db.query(RefreshToken.is_revoked).filter(RefreshToken.token == db_refresh_token).first()
        token.is_revoked = True
        # create Refresh token
        new_refresh_token = createRefreshToken()
        # save to db
        new_token = RefreshToken(
            user_id=current_user.id,
            token=new_refresh_token
            )
        # add to DB
        db.add(new_token)
        db.commit()
    return {'accessToken':new_access_token,'token_type': 'bearer'}
        

        
        