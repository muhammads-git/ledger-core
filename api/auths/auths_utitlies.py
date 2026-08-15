import bcrypt
from jose import jwt,JWTError
from dotenv import load_dotenv
import os
from datetime import datetime , timedelta
from datetime import datetime,timezone,timedelta
from fastapi import Depends,HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import uuid
load_dotenv()



# ==========================================
# HASHING UTILITIES
# ==========================================

def hashPassword(password: str) -> str:
    """Generates a salt and returns a string-decoded bcrypt hash."""
    salt = bcrypt.gensalt()
    # Fixed: Uncommented the hashing line so 'hashed' is defined
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def checkPassword(plainPassword: str, hashedPassword: str) -> bool:
    """Verifies a plain password against its stored hash."""
    return bcrypt.checkpw(plainPassword.encode('utf-8'), hashedPassword.encode('utf-8'))


# ==========================================
# JWT AUTHENTICATION
# ==========================================

ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
SECRET_KEY = os.getenv('APP_SECRET')


expiry_env = os.getenv('ACCESS_TOKEN_EXPIRY', '30')
ACCESS_TOKEN_EXPIRE_MINUTES = int(expiry_env)

############## TOKENS ##################
def createAccessToken(data: dict) -> str:
    """Generates a JWT token with an expiration timestamp.
     Assumes 'sub' contains a pre-lowercased email.
    """
    toEncode = data.copy()
    
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    toEncode.update({'exp': expire})
    
    encodedJWT = jwt.encode(toEncode, SECRET_KEY, algorithm=ALGORITHM)
    return encodedJWT

def createRefreshToken() -> str:
    """ just a uuid4 string """
    return str(uuid.uuid4())

############## Decode ################
def decodeToken(token: str) -> str | None:
    """Decodes a JWT token and returns the user email string if valid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get('sub')  # Returns the pre-lowercased string directly
    except JWTError:
        return None


################ GET CURRENT USER ######################
oauth_scheme = OAuth2PasswordBearer(tokenUrl='/api/login')
def getCurrentUser(token: str = Depends(oauth_scheme)):
    payload = decodeToken(token)
    if not payload:
        raise HTTPException(status_code=401, detail='Invalid or expired token')
    email = payload.get('sub')
    return email