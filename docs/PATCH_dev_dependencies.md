# 패치 초안 — 개발(테스트) 의존성 재현성 정리

> 상태: **미적용 (초안)**. 백엔드 동시 작업이 일단락된 뒤 한 번에 반영하세요.
> 목적: `pip install pytest anyio aiosqlite ...` 를 매번 수동으로 끼우지 않고,
> `docker compose run --rm backend python -m pytest -q` / CI가 그대로 녹색이 되게 한다.

## 배경 — 왜 필요한가 (발견된 문제)

- `backend/requirements.txt`에 **테스트 의존성이 없음** (pytest·aiosqlite 등).
- 테스트는 `@pytest.mark.anyio` + `conftest.py`의 `anyio_backend` 픽스처를 쓰고,
  `DATABASE_URL = sqlite+aiosqlite:///:memory:` 로 동작한다 → **anyio·aiosqlite 필수**.
- 그런데 CI(`.github/workflows/deploy.yml`)는 `pytest pytest-asyncio httpx`만 설치하고
  `--asyncio-mode=auto`(pytest-asyncio 옵션)로 실행 → **aiosqlite·anyio 누락 + 플러그인 불일치**.
- `httpx==0.28.0`은 이미 `requirements.txt`에 있으므로 dev에는 불필요(중복 금지).

검증된 동작 조합(동료분 수동 실행, 245/245 통과): `pytest · anyio · aiosqlite` + 평범한 `python -m pytest`.

---

## 1) 신설: `backend/requirements-dev.txt`

```text
# 테스트/개발 전용 의존성 (프로덕션 이미지에는 포함하지 않는다)
# httpx 는 requirements.txt(0.28.0)에 이미 있으므로 여기 넣지 않는다.
pytest==8.3.4
anyio==4.6.2.post1
aiosqlite==0.20.0
```

> 버전 핀은 컨테이너에서 실제 해석값으로 굳히는 것을 권장:
> `docker compose run --rm backend pip freeze | grep -Ei "^(pytest|anyio|aiosqlite)=="`
> (anyio 는 fastapi/starlette·httpx와 충돌 없는 값이어야 함 — 위 핀은 일반적 호환값)

---

## 2) `backend/Dockerfile` — dev 의존성 선택 설치 (프로덕션 이미지엔 미포함)

빌드 인자 `INSTALL_DEV`로 분기. 프로덕션 빌드는 기본값(false)이라 영향 없음.

```diff
 # Install Python dependencies
-COPY requirements.txt .
-RUN pip install --no-cache-dir -r requirements.txt
+ARG INSTALL_DEV=false
+COPY requirements.txt requirements-dev.txt ./
+RUN pip install --no-cache-dir -r requirements.txt \
+    && if [ "$INSTALL_DEV" = "true" ]; then \
+         pip install --no-cache-dir -r requirements-dev.txt; \
+       fi
```

## 2-1) `docker-compose.yml` — 로컬 backend 이미지에 dev 포함

backend 서비스의 build에 인자 추가(로컬/개발용). 프로덕션 ECR 빌드(CI)는 이 인자를 주지 않으므로 dev 미포함.

```diff
   backend:
     build:
-      context: ./backend
+      context: ./backend
+      args:
+        INSTALL_DEV: "true"
```

이후 한 번 재빌드하면 설치 단계 없이 그대로 실행:

```bash
docker compose build backend
docker compose run --rm --no-deps backend python -m pytest -q
```

---

## 3) `.github/workflows/deploy.yml` — test-backend job 정정

aiosqlite·anyio 누락과 플러그인 불일치를 함께 수정.

```diff
       - name: Install dependencies
-        run: pip install --no-cache-dir -r requirements.txt pytest pytest-asyncio httpx
+        run: pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt
```

```diff
         run: |
-          pytest tests/ -v --tb=short --asyncio-mode=auto \
+          python -m pytest tests/ -v --tb=short \
             --ignore=tests/e2e \
             -x
```

> 참고: CI는 `DATABASE_URL`을 postgres로 주지만 단위테스트는 대부분 mock DB라 무관하다.
> anyio 마커 기반이므로 `--asyncio-mode=auto`(pytest-asyncio 전용)는 제거한다.
> `cache-dependency-path: backend/requirements.txt` 는 그대로 두거나
> `backend/requirements-dev.txt`까지 배열로 추가해도 된다.

---

## 적용 체크리스트 (동료 작업 종료 후, 한 번에)

1. `backend/requirements-dev.txt` 생성 (위 1번)
2. `backend/Dockerfile` 패치 (위 2번)
3. `docker-compose.yml` backend build args 추가 (위 2-1번)
4. `.github/workflows/deploy.yml` test-backend 2줄 수정 (위 3번)
5. 검증:
   - 로컬: `docker compose build backend && docker compose run --rm --no-deps backend python -m pytest -q` → 245 passed
   - CI: 푸시 후 test-backend job 녹색 확인
6. (선택) `pytest-asyncio`는 더 이상 사용처가 없으므로 잔재 제거 확인
