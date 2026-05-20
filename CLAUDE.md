# 계약똑똑 — AI 임대차 계약서 분석 서비스

## 하네스: 계약똑똑 개발 파이프라인

**목표:** 와이어프레임부터 AWS 배포까지 설계-프론트-백엔드-AI-QA-배포를 자동으로 조율한다.

**트리거:** 계약똑똑 개발, 화면 설계, 컴포넌트 구현, API 개발, 배포 등 모든 작업 요청 시 `dev-pipeline` 스킬을 사용하라. 단순 질문은 직접 응답 가능.

## 프로젝트 개요

- **서비스명**: 계약똑똑 (contalktok.kr)
- **기능**: 임대차 계약서 사진/PDF 업로드 → OCR → AI 위험도 분석 → 3단계 리포트
- **기술 스택**: React.js / FastAPI / KLUE-RoBERTa / GPT-4o RAG / ChromaDB / AWS
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
