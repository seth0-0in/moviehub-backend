# MovieHub API - 영화 정보 공유 및 관리 서비스

**2025-2 Term Project (개인 과제) - 백엔드 시스템 개발**

본 프로젝트는 TMDB 외부 API를 연동하여 대량의 영화 데이터를 구축하고, JWT 기반의 인증 및 권한 관리(RBAC)를 통해 리뷰 작성 및 나만의 영화 리스트를 관리할 수 있는 RESTful API 서버입니다.

---

## 1. 프로젝트 주요 기능
* **리소스 구성**: `User`, `Movie`, `Review`, `PersonalList` 4개 이상의 핵심 리소스 구현.
* **엔드포인트**: CRUD 기능을 포함한 **30개 이상의 HTTP 엔드포인트** 확보.
* **인증/인가**: **JWT(Access Token)** 기반 인증 및 `ROLE_USER`, `ROLE_ADMIN` 권한 분리.
* **데이터 자동화**: TMDB API 연동을 통한 **200건 이상의 영화 시드 데이터** 동기화.
* **성능/보안**: **Redis**를 활용한 서버 방문자 카운팅 및 전역적인 에러 처리.

---

## 2. 기술 스택 (Tech Stack)
| 분류 | 기술 옵션 |
| :--- | :--- |
| **Framework** | **FastAPI** (Python 3.10+) |
| **Database** | **MySQL 8.0** (ORM: SQLAlchemy) |
| **Cache/NoSQL**| **Redis** (방문자 카운트 및 세션 관리용) |
| **Auth** | **JWT**, Firebase Auth 시뮬레이션 |
| **DevOps** | **Docker**, **Docker Compose** |
| **Testing** | **pytest** (20개 이상의 자동화 테스트 통과) |

---

## 3. 배포 정보 (JCloud)
JCloud의 **포트 포워딩 규칙**에 따라 인스턴스(`10.0.0.33`)에 할당된 주소입니다.

* **공인 IP**: `113.198.66.75`
* **인스턴스 내부 IP**: `10.0.0.33` (인스턴스 번호: **033**)
* **API 서버 (Swagger)**: [http://113.198.66.75:10033/docs](http://113.198.66.75:10033/docs) (8000 포트 매핑)
* **Health Check**: [http://113.198.66.75:10033/health](http://113.198.66.75:10033/health) (Redis 연동 확인용)
* **SSH 접속**: `ssh -p 19033 ubuntu@113.198.66.75` (7777 포트 매핑)

---

## 4. 설치 및 실행 방법 (Installation)

### 1) 환경 변수 설정
프로젝트 루트에 `.env` 파일을 생성하세요. 
```bash
DATABASE_URL=mysql+aiomysql://root:db_password@db/moviehub_db
REDIS_URL=redis://redis:6379/0
TMDB_API_KEY=your_api_key
JWT_SECRET=your_jwt_secret
```

### 2) 서비스 가동 (Docker Compose)
```bash
# 모든 컨테이너 빌드 및 백그라운드 실행
docker compose up -d --build
```

### 3) 자동화 테스트 실행 (pytest)
```bash
# 20개 이상의 테스트 시나리오 검증
docker compose exec app sh -c "PYTHONPATH=. pytest tests/test_main.py"
```
---

## 5. 주요 엔드포인트 요약 (총 30개 이상)
- **인증/인가: 회원가입, 로그인, 구글 소셜 로그인, 토큰 갱신, 유저 탈퇴**
- **영화 관리: 목록 조회(페이지네이션/검색/정렬), 상세 정보, 수동 생성, 평점순 조회**
- **리뷰 시스템: 영화별 리뷰 작성, 내 리뷰 수정 및 삭제, 최근 리뷰 피드**
- **나만의 리스트: 영화 보관함 생성, 보관함 내 영화 추가/삭제, 리스트 상세 보기**
- **시스템: Redis 기반 방문자 집계, 관리자 전용 서버 통계, 헬스체크** 

---

## 6. 에러 처리 및 입력 검증
모든 API는 일관된 JSON 형식의 에러 응답을 반환합니다.
```bash
{
  "timestamp": "2025-12-26T10:45:00Z",
  "path": "/movies/999",
  "status": 404,
  "code": "RESOURCE_NOT_FOUND",
  "message": "요청하신 영화 정보를 찾을 수 없습니다."
}
``` 