import os
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, String, Float, Boolean, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.exc import IntegrityError

DATABASE_URL = "postgresql://user:password@db:5432/movie_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI()


# Модели для базы данных
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    is_admin = Column(Boolean, default=False)

    movies = relationship("Movie", back_populates="owner")


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    rating = Column(Float)
    review = Column(String)

    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="movies")


Base.metadata.create_all(bind=engine)


# Схемы для FastAPI
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    is_admin: bool = False


class MovieCreate(BaseModel):
    title: str
    rating: float
    review: str


# Получаем сессию БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Зарегистрировать пользователя
@app.post("/users/", status_code=201)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="User already exists")
    db_user = User(email=user.email, full_name=user.full_name, is_admin=user.is_admin)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": "User created successfully"}

# Просмотреть информацию по отдельному пользователю
@app.get("/users/{email}")
def get_user(email: EmailStr, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == email).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


# Добавляем фильм на платформу (только с роли админа)
@app.post("/movies/", status_code=201)
def add_movie(movie: MovieCreate, email: EmailStr, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == email).first()
    if db_user is None or not db_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admin can add movies")

    db_movie = Movie(title=movie.title, rating=movie.rating, review=movie.review, owner_id=db_user.id)
    db.add(db_movie)
    db.commit()
    db.refresh(db_movie)
    return {"message": "Movie added successfully"}

# Смотрим какие фильмы добавлены на платформу
@app.get("/movies/")
def get_all_movies(db: Session = Depends(get_db)):
    return db.query(Movie).all()

# Оцениваем фильм и добавляем его в коллекцию пользователя
@app.post("/users/{email}/movies/", status_code=201)
def rate_movie(email: EmailStr, movie: MovieCreate, db: Session = Depends(get_db)):
    db_movie = db.query(Movie).filter(Movie.title == movie.title).first()
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie not found on the platform")

    db_user = db.query(User).filter(User.email == email).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db_movie.owner = db_user
    db.commit()
    db.refresh(db_movie)
    return {"message": "Movie rated successfully"}

# Смотрим рецензии на фильмы отдельного пользователя
@app.get("/users/{email}/movies/")
def get_movies(email: EmailStr, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == email).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user.movies
