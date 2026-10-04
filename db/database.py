import os
from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine, Session

load_dotenv()

database_url = os.getenv("DATABASE_URL")

engine = create_engine(database_url)

def init_db():
  SQLModel.metadata.create_all(engine)
  
def get_session():
  with Session(engine) as session:
    yield session