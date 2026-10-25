from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import User
pwd=CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth=OAuth2PasswordBearer(tokenUrl="/api/auth/login")
def hash_password(v): return pwd.hash(v)
def verify_password(v,h): return pwd.verify(v,h)
def create_token(user): return jwt.encode({"sub":str(user.id),"exp":datetime.now(timezone.utc)+timedelta(days=7)},settings.secret_key,algorithm="HS256")
def current_user(token:str=Depends(oauth),db:Session=Depends(get_db)):
    try: uid=int(jwt.decode(token,settings.secret_key,algorithms=["HS256"])["sub"])
    except Exception: raise HTTPException(401,"Invalid or expired token")
    user=db.get(User,uid)
    if not user: raise HTTPException(401,"User not found")
    return user
