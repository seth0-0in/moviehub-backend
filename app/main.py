from fastapi import FastAPI, Depends, HTTPException, status, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import selectinload
from app.database import engine, get_db
from app.models import Base, Movie, User, Review, PersonalList
from app.tmdb import fetch_popular_movies
from app.auth import get_password_hash, verify_password, create_access_token, SECRET_KEY, ALGORITHM
from pydantic import BaseModel, EmailStr
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional, List
from datetime import datetime
import os
import redis
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="MovieHub API", version="1.0.0")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# --- [Redis 설정] ---
rd = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

# --- [1-4. 에러 응답 통일 규격] ---
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "path": request.url.path,
            "status": exc.status_code,
            "code": getattr(exc, "code", "SYSTEM_ERROR"),
            "message": exc.detail
        }
    )

# --- [DTO / Schema] ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class ReviewCreate(BaseModel):
    content: str
    score: int

class ListCreate(BaseModel):
    title: str
    description: Optional[str] = None

class SocialLoginRequest(BaseModel):
    id_token: str

# --- [의존성: 인증 및 권한 관리] ---
async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None: raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError: raise HTTPException(status_code=401, detail="Token expired")
    
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user: raise HTTPException(status_code=401, detail="User not found")
    return user

async def get_admin_user(current_user: User = Depends(get_current_user)):
    if current_user.role != "ROLE_ADMIN":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# --- 1. System & Health (2개) ---
@app.get("/health", tags=["System"])
async def health_check():
    visits = rd.incr("api_visits")
    return {"status": "ok", "visits": visits, "redis": "connected"}

@app.get("/", tags=["System"])
async def root():
    return {"message": "Welcome to MovieHub API"}

# --- 2. Auth & User (8개) ---
@app.post("/auth/register", status_code=201, tags=["Auth"])
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == user_data.email))
    if res.scalar_one_or_none(): raise HTTPException(status_code=409, detail="Email exists")
    user = User(email=user_data.email, hashed_password=get_password_hash(user_data.password), role="ROLE_USER")
    db.add(user); await db.commit(); return {"message": "Registered"}

@app.post("/auth/login", tags=["Auth"])
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == form_data.username))
    user = res.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Login failed")
    return {"access_token": create_access_token({"sub": user.email, "role": user.role}), "token_type": "bearer"}

@app.post("/auth/google", tags=["Auth"])
async def google_login(data: SocialLoginRequest, db: AsyncSession = Depends(get_db)):
    test_email = "google_user@example.com"
    result = await db.execute(select(User).where(User.email == test_email))
    user = result.scalar_one_or_none()
    if not user:
        user = User(email=test_email, hashed_password="social_user", role="ROLE_USER")
        db.add(user); await db.commit()
    return {"access_token": create_access_token({"sub": test_email, "role": user.role}), "token_type": "bearer"}

@app.get("/users/me", tags=["User"])
async def my_page(u: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == u.id).options(selectinload(User.reviews), selectinload(User.personal_lists)))
    return res.scalar_one()

@app.put("/users/me", tags=["User"])
async def update_my_role(role: str, u: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    u.role = role; await db.commit(); return {"message": "Role updated"}

@app.delete("/users/me", tags=["User"])
async def delete_my_account(u: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.delete(u); await db.commit(); return {"message": "Deleted"}

@app.get("/admin/users", tags=["Admin"])
async def get_all_users(admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User)); return res.scalars().all()

@app.get("/admin/stats", tags=["Admin"])
async def get_stats(admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    u_cnt = await db.execute(select(func.count(User.id)))
    m_cnt = await db.execute(select(func.count(Movie.id)))
    return {"total_users": u_cnt.scalar(), "total_movies": m_cnt.scalar()}

# --- 3. Movie (7개) ---
@app.post("/movies/sync", tags=["Movie"])
async def sync_movies(db: AsyncSession = Depends(get_db)):
    for page in range(1, 11):
        tmdb_movies = await fetch_popular_movies(page=page)
        for m in tmdb_movies:
            res = await db.execute(select(Movie).where(Movie.id == m['id']))
            if not res.scalar_one_or_none():
                new_m = Movie(id=m['id'], title=m['title'], overview=m['overview'], rating=m['vote_average'])
                db.add(new_m)
    await db.commit(); return {"status": "synced"}

@app.get("/movies", tags=["Movie"])
async def list_movies(page: int = 1, size: int = 20, q: str = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Movie).offset((page-1)*size).limit(size)
    if q: stmt = stmt.where(Movie.title.contains(q))
    res = await db.execute(stmt); return res.scalars().all()

@app.get("/movies/{movie_id}", tags=["Movie"])
async def movie_detail(movie_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Movie).where(Movie.id == movie_id)); return res.scalar_one_or_none()

@app.post("/movies", tags=["Movie"])
async def create_movie(title: str, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    m = Movie(title=title, id=int(datetime.now().timestamp())); db.add(m); await db.commit(); return m

@app.put("/movies/{movie_id}", tags=["Movie"])
async def update_movie(movie_id: int, title: str, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    await db.execute(update(Movie).where(Movie.id == movie_id).values(title=title)); await db.commit(); return {"msg": "updated"}

@app.delete("/movies/{movie_id}", tags=["Movie"])
async def delete_movie(movie_id: int, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Movie).where(Movie.id == movie_id)); await db.commit(); return {"msg": "deleted"}

@app.get("/movies/top-rated", tags=["Movie"])
async def top_movies(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Movie).order_by(Movie.rating.desc()).limit(5)); return res.scalars().all()

# --- 4. Review (7개) ---
@app.post("/movies/{movie_id}/reviews", tags=["Review"])
async def add_review(movie_id: int, r: ReviewCreate, u: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    new_r = Review(content=r.content, score=r.score, user_id=u.id, movie_id=movie_id)
    db.add(new_r); await db.commit(); return new_r

@app.get("/reviews", tags=["Review"])
async def all_reviews(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Review).limit(50)); return res.scalars().all()

@app.get("/movies/{movie_id}/reviews", tags=["Review"])
async def movie_reviews(movie_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Review).where(Review.movie_id == movie_id)); return res.scalars().all()

@app.get("/reviews/{review_id}", tags=["Review"])
async def get_review(review_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Review).where(Review.id == review_id)); return res.scalar_one_or_none()

@app.put("/reviews/{review_id}", tags=["Review"])
async def update_review(review_id: int, content: str, u: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Review).where(Review.id == review_id, Review.user_id == u.id))
    review = res.scalar_one_or_none()
    if not review: raise HTTPException(403, "Not your review")
    review.content = content; await db.commit(); return review

@app.delete("/reviews/{review_id}", tags=["Review"])
async def delete_review(review_id: int, u: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Review).where(Review.id == review_id, Review.user_id == u.id)); await db.commit(); return {"msg": "deleted"}

@app.get("/reviews/recent", tags=["Review"])
async def recent_reviews(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Review).order_by(Review.created_at.desc()).limit(10)); return res.scalars().all()

# --- 5. Personal List (8개) ---
@app.post("/lists", tags=["List"])
async def create_list(l: ListCreate, u: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    new_l = PersonalList(title=l.title, description=l.description, user_id=u.id)
    db.add(new_l); await db.commit(); return new_l

@app.get("/lists", tags=["List"])
async def get_my_lists(u: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(PersonalList).where(PersonalList.user_id == u.id)); return res.scalars().all()

@app.get("/lists/{list_id}", tags=["List"])
async def list_detail(list_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(PersonalList).where(PersonalList.id == list_id).options(selectinload(PersonalList.movies)))
    return res.scalar_one_or_none()

@app.put("/lists/{list_id}", tags=["List"])
async def update_list(list_id: int, title: str, u: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(update(PersonalList).where(PersonalList.id == list_id, PersonalList.user_id == u.id).values(title=title))
    await db.commit(); return {"msg": "updated"}

@app.delete("/lists/{list_id}", tags=["List"])
async def delete_list(list_id: int, u: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(PersonalList).where(PersonalList.id == list_id, PersonalList.user_id == u.id))
    await db.commit(); return {"msg": "deleted"}

@app.post("/lists/{list_id}/movies/{movie_id}", tags=["List"])
async def add_to_list(list_id: int, movie_id: int, u: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(PersonalList).where(PersonalList.id == list_id).options(selectinload(PersonalList.movies)))
    l = res.scalar_one(); m = await db.get(Movie, movie_id); l.movies.append(m); await db.commit(); return {"status": "added"}

@app.delete("/lists/{list_id}/movies/{movie_id}", tags=["List"])
async def remove_from_list(list_id: int, movie_id: int, u: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(PersonalList).where(PersonalList.id == list_id).options(selectinload(PersonalList.movies)))
    l = res.scalar_one(); l.movies = [m for m in l.movies if m.id != movie_id]; await db.commit(); return {"status": "removed"}

@app.get("/lists/all", tags=["List"]) # 관리자용 전체 리스트 조회
async def get_all_lists(admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(PersonalList)); return res.scalars().all()