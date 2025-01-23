from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from book_api.database import get_db
from book_api.models import User
from book_api import schemas
from book_api.settings import config
import os 

# congig variables
SECRET_KEY = config.SECRET_KEY
ALGORITHM = config.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = int(config.ACCESS_TOKEN_EXPIRE_MINUTES)

# password context
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

# oauth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='token')

# password functions 
def verify_password(plain_password:str, hashed_password:str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password:str) -> str:
    return pwd_context.hash(password)

# user functions
def get_user(db: Session, username: str) -> User:
    return db.query(User).filter(User.username == username).first()

def authenticate_user(db: Session, username: str, password: str) -> User:
    user = get_user(db, username)
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

# token functions
def get_access_token(data: dict, request: Request):

    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        'exp': expire,
        'ip': request.headers.get('Host', ''),
        'user_agent': request.headers.get('User-Agent', ''),
        'device': request.headers.get('X-Device-Id', '')
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt

# dependency for getting current user
def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Could not validate credentials',
        headers={'WWW-Authenticate': 'Bearer'}
    )

    try:

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # check ip address
        if payload.get('ip') != request.headers.get('Host', ''):
            raise HTTPException(
                status_code=401,
                detail="IP address mismatch. Please login again."
            )

        # check browser
        if payload.get('user_agent') != request.headers.get('User-Agent', ''):
            raise HTTPException(
                status_code=401,
                detail="Browser mismatch. Please login again."
            )

        # check device
        if (payload.get('device') != request.headers.get('X-Device-Id', '')):
            raise HTTPException(
                status_code=401,
                detail="Device mismatch. Please login again."
            )

        username: str = payload.get('sub')
        if username is None:
            raise credentials_exception
            
        user = get_user(db, username)
        if user is None:
            raise credentials_exception
            
        return user

    except JWTError:
        raise credentials_exception
    

# dependency for getting current active user
def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user:
        raise HTTPException(status_code=400, detail='Inactive user')
    return current_user

# for checking roles
def check_role(allowed_roles: list) -> bool:
    def check_role_decorator(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You do not have permission to access this resource'
            )
        return current_user
    return check_role_decorator

