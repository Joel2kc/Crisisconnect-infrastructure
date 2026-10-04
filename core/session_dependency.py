from db.database import get_session
from typing import Annotated
from fastapi import Depends
from sqlmodel import Session

sessionDep = Annotated[Session, Depends(get_session)]