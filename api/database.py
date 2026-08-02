
from sqlalchemy.orm import sessionmaker,declarative_base
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os


load_dotenv()
# create physical connectio with db .. engine
engine=create_engine(os.getenv('DATABASE_URL'))
# create sessions with db
SessionLocal = sessionmaker(bind=engine)
BASE = declarative_base()

def get_db():
   db = SessionLocal()
   try:
      yield db
   finally:
      db.close()