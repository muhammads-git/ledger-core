import bcrypt
from jose import jwt,JWTError
from dotenv import load_dotenv
import os
from datetime import datetime , timedelta

load_dotenv()



######################### HASHING ###########################33
def hashPassword(password: str) -> str:
   # create saltvi
   salt = bcrypt.gensalt()
   # 
   hashed = bcrypt.hashpw(password.encode('utf-8'),salt)
   return hashed.decode('utf-8')  # store as string

def checkPassword(plainPassword: str, hashedPassword: str) -> bool:
   return bcrypt.checkpw(plainPassword.encode('utf-8'),hashedPassword.encode('utf-8'))

################JWT AUTHENTICATIONS ###############3

ALGORITHM = os.getenv('JWT_ALGORITHM')
SECRET_KEY = os.getenv('APP_SECRET')
ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv(int('ACCESS_TOKEN_EXPIRY'))

def createAccessToken(data : dict) -> str :
    # 
    toEncode = data.copy()
    # set expiry
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # add to existing dict
    toEncode.update({'exp':expire})

    # create token
    encodedJWT = jwt.encode(toEncode, SECRET_KEY, algorithm=ALGORITHM)
    # print("Encoded tokens: ", encodedJWT) 
    return encodedJWT


def decodeToken(token : str):
   # return the email of user if token is valid

   try:
       payload = jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM)
       email: str = payload.get('sub')
       return email
   except JWTError:
       return None