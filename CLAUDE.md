# 계약똑똑 — AI 임대차 계약서 분석 서비스

## 하네스: 계약똑똑 개발 파이프라인

**목표:** 와이어프레임부터 AWS 배포까지 설계-프론트-백엔드-AI-QA-배포를 자동으로 조율한다.

**트리거:** 계약똑똑 개발, 화면 설계, 컴포넌트 구현, API 개발, 배포 등 모든 작업 요청 시 `dev-pipeline` 스킬을 사용하라. 단순 질문은 직접 응답 가능.

## 프로젝트 개요

- **서비스명**: 계약똑똑 (contalktok.kr)
- **기능**: 임대차 계약서 사진/PDF 업로드 → OCR → AI 위험도 분석 → 3단계 리포트
- **기술 스택**: React.js / FastAPI / KLUE-RoBERTa / GPT RAG(OPENAI_MODEL, 기본 gpt-5.4) / ChromaDB / AWS
- **일정**: 2026.4.1 ~ 2026.10.1
- **팀**: 김지환(AI/BE) · 정욱(FE) · 이원중(AI) · 조영서(UX) · 김태우(QA/마케팅)

## 에이전트 팀

| 에이전트 | 역할 | 스킬 |
|---------|------|------|
| design-architect | 와이어프레임 / UI 스펙 | wireframe-design |
| frontend-developer | React.js 컴포넌트 | react-frontend |
| backend-developer | FastAPI + DB | fastapi-backend |
| ai-engineer | OCR/RAG/모델 | ai-pipeline |
| qa-engineer | 통합 테스트 | qa-testing |
| devops-engineer | AWS 배포 | aws-deploy |

## 변경 이력

| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-05-19 | 초기 하네스 구성 | 전체 | PDF 계획서 기반 신규 구축 |
| 2026-05-27 | 분석 이력 표시 텍스트 개선 | MyPage.tsx | "분석서 (#id)" → "분석 결과" |
| 2026-05-27 | Vite usePolling 추가 | vite.config.ts | Windows+Docker 환경 파일 변경 감지 |
| 2026-05-27 | 계약 유형 자동 감지 | pipeline.py, tasks/analysis.py | OCR 텍스트에서 전세/월세 파싱 → 사용자 수동 선택 제거 |
| 2026-05-27 | UploadPage 계약 유형 선택 UI 제거 | UploadPage.tsx | 계약 유형 자동 감지로 대체 |
| 2026-05-27 | 시세 조회 다중 월 집계 | market_service.py, market.py | 단일 월 → 최근 N개월 병렬 수집 합산 평균 |
| 2026-05-27 | 시세 조회 전세/월세 분리 | market_service.py, market.py, schemas/market.py | 월세 계약자에게 전세가율 대신 월세 시세 제공 |
| 2026-05-27 | ChecklistPage 전면 개편 | ChecklistPage.tsx | 전세/월세 탭 + 최근 계약서 자동 선택 + 집계 기간(1·3·6개월) 선택 |
| 2026-05-27 | market.py NameError 수정 | market.py | `ym` 미정의 변수 → `trade.deal_ym` 으로 교체 |
| 2026-06-07 | ESLint 설정 파일 추가 | frontend/.eslintrc.cjs | CI lint job 통과를 위한 설정 생성 |
| 2026-06-07 | Vitest + Testing Library 설정 | frontend/ (vite.config.ts, package.json, test/) | 프론트엔드 자동화 테스트 프레임워크 구축 (11개 테스트) |
| 2026-06-07 | package-lock.json 생성 | frontend/package-lock.json | 빌드 재현성 확보 |
| 2026-06-07 | CI에 Vitest 추가 | .github/workflows/deploy.yml | test-frontend job에 `npm run test` 단계 추가 |
| 2026-06-07 | QA 잔여 이슈 재검증 | 03_qa_bugs.md | BUG-002 잔여·NOTE-001 이미 해결 확인, 7/7 완전 해결 |
| 2026-06-07 | 카카오/구글 OAuth 실제 SDK 연동 | LoginPage.tsx, OAuthCallbackPage.tsx, index.html | VITE_DEMO_MODE 분기 방식 |
| 2026-06-07 | 포트원 실제 결제 SDK 연동 | PaymentPage.tsx, index.html | VITE_DEMO_MODE 분기 방식 |
| 2026-06-07 | 실서비스 배포 가이드 작성 | docs/DEPLOYMENT.md | 전체 배포 체크리스트 및 환경변수 가이드 |
