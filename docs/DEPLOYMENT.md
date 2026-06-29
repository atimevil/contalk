# 계약똑똑 — 실서비스 배포 가이드

> 작성일: 2026-06-07
> 대상: contalktok.kr 프로덕션 배포

---

## 1. 사전 준비물

### 1.1 AWS 계정 및 도구

| 항목 | 설명 |
|------|------|
| AWS 계정 | IAM 사용자 (AdministratorAccess 또는 필요 권한) |
| AWS CLI | `aws configure` 완료 |
| Terraform | >= 1.6 설치 |
| Docker | 로컬 이미지 빌드용 |
| GitHub repo | Actions secrets 등록 가능한 권한 |

### 1.2 도메인

| 도메인 | 용도 |
|--------|------|
| `contalktok.kr` | 프론트엔드 (CloudFront) |
| `api.contalktok.kr` | 백엔드 API (EC2 or ALB) |

---

## 2. 외부 서비스 가입 및 키 발급

### 2.1 카카오 OAuth

1. [Kakao Developers](https://developers.kakao.com/) → 앱 생성
2. **플랫폼** → Web 도메인 추가: `https://contalktok.kr`
3. **카카오 로그인** 활성화
4. **Redirect URI** 등록: `https://contalktok.kr/oauth/kakao/callback`
5. **동의항목**: 닉네임, 이메일 (필수)
6. 발급 키:
   - `VITE_KAKAO_APP_KEY` = JavaScript 키
   - `KAKAO_CLIENT_ID` = REST API 키
   - `KAKAO_CLIENT_SECRET` = 보안 → Client Secret 코드

### 2.3 포트원 V2 결제

> 결제는 포트원 V2 브라우저 SDK(`@portone/browser-sdk`)로 KG이니시스 카드결제를 호출하고, 서버는 포트원 V2 REST API(`api.portone.io`)로 결제를 검증합니다.

1. [포트원](https://portone.io/) → 회원가입 → V2 콘솔에서 상점 생성
2. **연동 정보** → **채널 추가** → KG이니시스 (테스트) 채널 등록
3. **결제대행사 설정** → html5_inicis (간편결제: 카카오페이, 토스페이 추가 가능)
4. 발급 키:
   - `PORTONE_STORE_ID` = 상점 ID (store-id-xxxxxxxx)
   - `PORTONE_CHANNEL_KEY` = KG이니시스 채널 키 (channel-key-xxxxxxxx)
   - `PORTONE_V2_API_SECRET` = V2 API Secret (서버 결제 검증용)
   - `PORTONE_PG_PROVIDER` = `html5_inicis`

> 실결제 전환 시: 포트원 → 실결제 모드 전환 + PG사 사업자 심사 필요 (약 1~2주)

### 2.4 OpenAI API

1. [OpenAI Platform](https://platform.openai.com/) → API Keys 발급
2. 모델: `gpt-4o` (또는 `gpt-5.4` 설정값 확인)
3. 발급 키:
   - `OPENAI_API_KEY` = sk-...

### 2.5 국토교통부 MOLIT API

1. [공공데이터포털](https://www.data.go.kr/) → 회원가입
2. **아파트매매 실거래가** API 신청 (즉시 승인)
3. **아파트전월세 실거래가** API 신청 (별도 승인, 1~3일 소요)
4. 발급 키:
   - `MOLIT_API_KEY` = 인증키 (Encoding)

> 전세 API 미승인 상태에서도 서비스 동작 (매매 데이터만 표시, graceful degradation)

---

## 3. 인프라 배포 (Terraform)

### 3.1 Terraform 변수 설정

```bash
cd infra/terraform

cat > terraform.tfvars << 'EOF'
environment    = "production"
db_password    = "최소16자_강력한_비밀번호_여기에"
key_pair_name  = "contalktok-key"     # AWS에 미리 등록한 SSH 키페어 이름
EOF
```

### 3.2 인프라 생성

```bash
terraform init
terraform plan          # 변경사항 미리보기 (비용 확인)
terraform apply         # 실제 리소스 생성 (약 5~10분)
```

생성되는 리소스:
- VPC + 퍼블릭 서브넷 2개
- EC2 t3.small (백엔드 + Docker)
- RDS PostgreSQL t3.micro
- S3 버킷 2개 (contracts, frontend)
- CloudFront Distribution
- Security Groups

### 3.3 출력값 확인

```bash
terraform output
# ec2_public_ip       = "3.xx.xx.xx"
# rds_endpoint        = "contalktok-db.xxxxx.ap-northeast-2.rds.amazonaws.com"
# s3_frontend_bucket  = "contalktok-frontend-xxxxx"
# cloudfront_domain   = "dxxxxxxxxxx.cloudfront.net"
```

---

## 4. 도메인 + SSL 설정

### 4.1 Route 53 (또는 외부 DNS)

| 레코드 | 타입 | 값 |
|--------|------|-----|
| `contalktok.kr` | A (Alias) | CloudFront Distribution |
| `api.contalktok.kr` | A | EC2 Elastic IP |

### 4.2 ACM 인증서 발급

```bash
# CloudFront용 (us-east-1 필수!)
aws acm request-certificate \
  --domain-name contalktok.kr \
  --validation-method DNS \
  --region us-east-1

# API 서버용 (ap-northeast-2)
aws acm request-certificate \
  --domain-name api.contalktok.kr \
  --validation-method DNS \
  --region ap-northeast-2
```

DNS 검증 레코드 추가 후 → 인증서 발급 완료 (수 분 소요)

### 4.3 CloudFront에 커스텀 도메인 연결

Terraform 또는 콘솔에서:
- Alternate domain names: `contalktok.kr`
- SSL certificate: 위에서 발급한 us-east-1 인증서 선택

### 4.4 API 서버 HTTPS

EC2에서 Let's Encrypt (무료):

```bash
# EC2 접속 후
sudo apt install certbot
sudo certbot certonly --standalone -d api.contalktok.kr
# → /etc/letsencrypt/live/api.contalktok.kr/ 에 인증서 생성
```

또는 향후 ALB 전환 시 ACM 인증서 연결 (권장)

---

## 5. 환경변수 설정

### 5.1 백엔드 (.env — EC2 서버)

```env
# ─── 앱 설정 ───
APP_ENV=production
APP_VERSION=1.0.0
SECRET_KEY=openssl_rand_hex_32_결과물

# ─── 데이터베이스 ───
DATABASE_URL=postgresql+asyncpg://postgres:비밀번호@RDS엔드포인트:5432/contalktok

# ─── Redis (EC2 내 Docker) ───
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# ─── AWS S3 ───
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=시크릿키
AWS_REGION=ap-northeast-2
S3_BUCKET_NAME=contalktok-contracts

# ─── ChromaDB (EC2 내 Docker) ───
CHROMA_HOST=localhost
CHROMA_PORT=8001
CHROMA_COLLECTION_NAME=lease_law

# ─── OpenAI ───
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4

# ─── KLUE-RoBERTa ───
KLUE_ROBERTA_MODEL_PATH=foxibu/contalk-risk-classifier

# ─── OAuth (카카오) ───
KAKAO_CLIENT_ID=REST_API_키
KAKAO_CLIENT_SECRET=Client_Secret_코드

# ─── 포트원 V2 ───
PORTONE_V2_API_SECRET=V2_API_Secret
PORTONE_STORE_ID=store-id-xxxxxxxx
PORTONE_CHANNEL_KEY=channel-key-xxxxxxxx
PORTONE_PG_PROVIDER=html5_inicis

# ─── 국토교통부 ───
MOLIT_API_KEY=공공데이터포털_인증키

# ─── CORS (프로덕션 도메인) ───
CORS_ORIGINS=https://contalktok.kr

# ─── 가격 ───
PRICE_SINGLE=2900
PRICE_PASS_1MONTH=9900
PRICE_PASS_3MONTH=19900
```

### 5.2 프론트엔드 빌드 환경변수

CI/CD 빌드 시 또는 로컬 빌드 시 설정:

```env
VITE_API_BASE_URL=https://api.contalktok.kr/api/v1
VITE_KAKAO_APP_KEY=카카오_JavaScript_키
VITE_PORTONE_STORE_ID=store-id-xxxxxxxx
VITE_PORTONE_CHANNEL_KEY=channel-key-xxxxxxxx
VITE_DEMO_MODE=false
```

### 5.3 GitHub Secrets (CI/CD)

| Secret | 값 |
|--------|-----|
| `AWS_ACCESS_KEY_ID` | IAM 액세스 키 |
| `AWS_SECRET_ACCESS_KEY` | IAM 시크릿 키 |
| `ECR_REGISTRY` | 123456789.dkr.ecr.ap-northeast-2.amazonaws.com |
| `ECS_CLUSTER` | contalktok-cluster |
| `ECS_SERVICE` | contalktok-backend |
| `S3_BUCKET` | contalktok-frontend-xxxxx |
| `CF_DISTRIBUTION_ID` | E1XXXXXXXXXX |
| `VITE_KAKAO_APP_KEY` | 카카오 JavaScript 키 (프론트 빌드용) |
| `VITE_PORTONE_STORE_ID` | 포트원 V2 상점 ID (프론트 빌드용) |
| `VITE_PORTONE_CHANNEL_KEY` | 포트원 V2 채널 키 (프론트 빌드용) |

---

## 6. 초기 데이터 설정

### 6.1 DB 마이그레이션

```bash
# EC2 접속 후 (또는 docker exec)
cd /app
alembic upgrade head
```

### 6.2 ChromaDB 법령 색인

```bash
# 샘플 법령 81개 색인 (빠름, ~1분)
python backend/ai/vectordb_builder.py --sample

# 법제처 API로 실제 법령 색인 (LAW_API_KEY 필요)
python backend/ai/vectordb_builder.py --api
```

### 6.3 KLUE-RoBERTa 모델 캐시

첫 분석 요청 시 HuggingFace에서 자동 다운로드 (~500MB). 미리 캐시하려면:

```bash
python -c "from transformers import AutoModel; AutoModel.from_pretrained('foxibu/contalk-risk-classifier')"
```

---

## 7. 배포 실행

### 7.1 수동 배포 (첫 배포)

```bash
# 1. 백엔드 Docker 이미지 빌드 & ECR 푸시
cd backend
docker build -t contalktok-backend .
docker tag contalktok-backend:latest ECR_URI:latest
docker push ECR_URI:latest

# 2. 프론트엔드 빌드 & S3 업로드
cd frontend
npm ci && npm run build
aws s3 sync dist/ s3://S3_BUCKET --delete
aws cloudfront create-invalidation --distribution-id CF_ID --paths "/*"
```

### 7.2 자동 배포 (이후)

`main` 브랜치에 push → GitHub Actions 자동 실행:
1. Backend pytest + Frontend lint/test/build
2. Docker 빌드 → ECR 푸시
3. ECS 서비스 업데이트 (rolling deploy)
4. Frontend S3 sync + CloudFront invalidation

---

## 8. 배포 후 확인

```bash
# 헬스체크
curl https://api.contalktok.kr/health

# 프론트엔드
curl -I https://contalktok.kr

# DB 연결 확인
curl https://api.contalktok.kr/api/v1/health
```

---

## 9. 운영 모드 vs 시연 모드

| 환경변수 | 시연(데모) | 실서비스 |
|----------|-----------|----------|
| `VITE_DEMO_MODE` | `true` | `false` (또는 미설정) |
| `VITE_ENABLE_MOCK` | `true` | `false` |
| `APP_ENV` | `development` | `production` |

**시연 모드 동작:**
- 로그인: mock 코드로 즉시 인증 (OAuth SDK 미사용)
- 결제: mock paymentId(merchantUid)로 즉시 검증 (포트원 SDK 미사용)
- API: MSW가 모든 요청 인터셉트 (백엔드 불필요)

**실서비스 동작:**
- 로그인: 카카오 실제 리다이렉트 → 콜백 → 토큰 교환
- 결제: 포트원 V2 결제창 팝업 → 실결제 → 서버 검증 (paymentId = merchantUid)
- API: 실제 백엔드 호출

---

## 10. 예상 월 비용

| 서비스 | 월 비용 |
|--------|---------|
| EC2 t3.small (24/7) | ~₩23,000 |
| RDS t3.micro | ~₩34,000 |
| S3 + CloudFront | ~₩3,000 |
| OpenAI API (분석 100건/월) | ~₩30,000~50,000 |
| **합계** | **~₩90,000~110,000** |

> 개발 시간만 운영 시 EC2/RDS 비용 50% 절감 가능

---

## 11. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| CORS 에러 | `CORS_ORIGINS`에 프론트 도메인 누락 | `.env`에 `https://contalktok.kr` 추가 |
| OAuth 콜백 실패 | Redirect URI 불일치 | 카카오 콘솔에서 정확한 URI 등록 |
| 결제창 미표시 | Store ID / Channel Key 오류 또는 SDK 미로드 | `VITE_PORTONE_STORE_ID`·`VITE_PORTONE_CHANNEL_KEY` 확인, `@portone/browser-sdk` 로드 확인 |
| 분석 timeout | OpenAI 응답 지연 | Celery soft_time_limit 확인, 재시도 로직 동작 확인 |
| 모델 로드 실패 | HF 캐시 미다운로드 | `HF_HOME` 경로 쓰기 권한 확인 |
| 전세가율 미표시 | MOLIT 전세 API 미승인 | 공공데이터포털에서 승인 상태 확인 |
