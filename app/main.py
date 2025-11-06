from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .database import engine, SessionLocal
from .models import Base, UserDB
from .schemas import UserCreate, UserRead

app = FastAPI()
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
# Health check endpoint
@app.get("/health") 
def health_check():
    return {"status": "ok"}

# List users
@app.get("/api/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)):
    stmt = select(UserDB).order_by(UserDB.id) # Order by user ID
    return list(db.execute(stmt).scalars())

# Get user by ID
@app.get("/api/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)):
    # Fetch user by ID
    user = db.get(UserDB, user_id)
    if not user: # Handle user not found
        raise HTTPException(status_code=404, detail="User not found")
    return user

# create user
@app.post("/api/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def add_user(payload: UserCreate, db: Session = Depends(get_db)): # Create new user
    user = UserDB(**payload.model_dump()) #
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError: # Handle duplicate user error
        db.rollback()
        raise HTTPException(status_code=409, detail="User already exists")
    return user

#update users 
@app.put("/api/users/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserCreate, db: Session = Depends(get_db)): # Update existing user
    user = db.get(UserDB, user_id) # Fetch user by ID
    if not user: 
        raise HTTPException(status_code=404, detail="User not found")
    # Updating user fields that are provided in the payload through a loop
    for key, value in payload.model_dump().items(): 
        setattr(user, key, value) 
    try: # Save changes
        db.commit()
        db.refresh(user)
    except IntegrityError: 
        db.rollback()
        raise HTTPException(status_code=409, detail="User already exists") 
    return user

#delete users
@app.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)): # Delete user
    user = db.get(UserDB, user_id) # Fetch user by ID
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user) # Delete user
    db.commit()
    return