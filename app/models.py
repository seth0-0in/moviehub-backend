from sqlalchemy import Column, Integer, String, Text, ForeignKey, Float, DateTime, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# 영화와 개인 리스트의 다대다(N:M) 관계를 위한 연결 테이블
movie_list_association = Table(
    'movie_list_association',
    Base.metadata,
    Column('movie_id', Integer, ForeignKey('movies.id')),
    Column('list_id', Integer, ForeignKey('personal_lists.id'))
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="ROLE_USER")  # ROLE_USER, ROLE_ADMIN
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    reviews = relationship("Review", back_populates="author")
    personal_lists = relationship("PersonalList", back_populates="owner")

class Movie(Base):
    __tablename__ = "movies"
    id = Column(Integer, primary_key=True, index=True) # TMDB ID와 동일하게 사용 가능
    title = Column(String(255), nullable=False)
    overview = Column(Text)
    poster_path = Column(String(255))
    rating = Column(Float, default=0.0)
    release_date = Column(String(50))
    
    reviews = relationship("Review", back_populates="movie")

class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    score = Column(Integer, default=5)
    user_id = Column(Integer, ForeignKey("users.id"))
    movie_id = Column(Integer, ForeignKey("movies.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    author = relationship("User", back_populates="reviews")
    movie = relationship("Movie", back_populates="reviews")

class PersonalList(Base):
    __tablename__ = "personal_lists"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="personal_lists")
    movies = relationship("Movie", secondary=movie_list_association)