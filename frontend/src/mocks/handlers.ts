import { http, HttpResponse, delay } from 'msw';

const BASE = '/api/v1';

// 분석 상태 시뮬레이션을 위한 인메모리 상태
const jobStatusMap = new Map<string, { step: number; startTime: number }>();

export const handlers = [
  // ============================================================
  // 인증 API
  // ============================================================

  // 카카오 로그인
  http.post(`${BASE}/auth/kakao`, async () => {
    await delay(800);
    return HttpResponse.json({
      success: true,
      data: {
        accessToken: 'mock-access-token-kakao',
        refreshToken: 'mock-refresh-token-kakao',
        user: {
          id: 'user-mock-001',
          email: 'mock@kakao.com',
          nickname: '김테스트',
          profileImageUrl: undefined,
          provider: 'kakao',
          createdAt: new Date().toISOString(),
        },
        isNewUser: false,
      },
    });
  }),

  // 구글 로그인
  http.post(`${BASE}/auth/google`, async () => {
    await delay(800);
    return HttpResponse.json({
      success: true,
      data: {
        accessToken: 'mock-access-token-google',
        refreshToken: 'mock-refresh-token-google',
        user: {
          id: 'user-mock-002',
          email: 'mock@gmail.com',
          nickname: '이테스트',
          profileImageUrl: undefined,
          provider: 'google',
          createdAt: new Date().toISOString(),
        },
        isNewUser: true,
      },
    });
  }),

  // 내 프로필
  http.get(`${BASE}/auth/me`, async () => {
    await delay(300);
    const token = localStorage.getItem('accessToken');
    if (!token) {
      return HttpResponse.json(
        { success: false, error: { code: 'AUTH_TOKEN_EXPIRED', message: '로그인이 필요합니다.' }, requestId: 'req-001' },
        { status: 401 }
      );
    }
    return HttpResponse.json({
      success: true,
      data: {
        user: {
          id: 'user-mock-001',
          email: 'mock@kakao.com',
          nickname: '김테스트',
          provider: 'kakao',
          createdAt: new Date().toISOString(),
        },
        quota: {
          type: 'single',
          remaining: 3,
        },
      },
    });
  }),

  // 약관 동의
  http.post(`${BASE}/auth/agree`, async () => {
    await delay(400);
    return HttpResponse.json({
      success: true,
      data: {
        agreed: true,
        agreedAt: new Date().toISOString(),
      },
    });
  }),

  // 로그아웃
  http.post(`${BASE}/auth/logout`, async () => {
    await delay(200);
    return HttpResponse.json({ success: true });
  }),

  // 토큰 갱신
  http.post(`${BASE}/auth/refresh`, async () => {
    await delay(300);
    return HttpResponse.json({
      success: true,
      data: {
        accessToken: 'mock-access-token-refreshed',
        refreshToken: 'mock-refresh-token-refreshed',
      },
    });
  }),

  // ============================================================
  // 분석 API
  // ============================================================

  // 파일 업로드 + 분석 시작
  http.post(`${BASE}/analysis/upload`, async () => {
    await delay(1200);
    const jobId = `job-${Date.now()}`;
    jobStatusMap.set(jobId, { step: 0, startTime: Date.now() });
    return HttpResponse.json(
      {
        success: true,
        data: {
          jobId,
          estimatedSeconds: 15,
          status: 'queued',
        },
      },
      { status: 202 }
    );
  }),

  // 분석 상태 폴링
  http.get(`${BASE}/analysis/:jobId/status`, async ({ params }) => {
    await delay(500);
    const { jobId } = params as { jobId: string };
    const jobState = jobStatusMap.get(jobId) || { step: 0, startTime: Date.now() };
    const elapsed = (Date.now() - jobState.startTime) / 1000;

    const steps: Array<{ status: string; completedSteps: string[]; currentStep: string; progress: number }> = [
      { status: 'uploading', completedSteps: [], currentStep: 'upload', progress: 10 },
      { status: 'ocr', completedSteps: ['upload'], currentStep: 'ocr', progress: 30 },
      { status: 'analyzing', completedSteps: ['upload', 'ocr'], currentStep: 'analyze', progress: 65 },
      { status: 'generating', completedSteps: ['upload', 'ocr', 'analyze'], currentStep: 'clause', progress: 85 },
      { status: 'completed', completedSteps: ['upload', 'ocr', 'analyze', 'clause'], currentStep: 'clause', progress: 100 },
    ];

    // 약 3초마다 단계 진행
    const stepIndex = Math.min(Math.floor(elapsed / 3), steps.length - 1);
    const currentStepData = steps[stepIndex];

    if (currentStepData.status === 'completed') {
      const reportId = `report-${jobId}`;
      return HttpResponse.json({
        success: true,
        data: {
          jobId,
          status: 'completed',
          progress: 100,
          currentStep: 'clause',
          completedSteps: ['upload', 'ocr', 'analyze', 'clause'],
          reportId,
        },
      });
    }

    return HttpResponse.json({
      success: true,
      data: {
        jobId,
        ...currentStepData,
      },
    });
  }),

  // 분석 결과
  http.get(`${BASE}/analysis/:reportId/result`, async ({ params }) => {
    await delay(600);
    const { reportId } = params as { reportId: string };
    return HttpResponse.json({
      success: true,
      data: {
        reportId,
        jobId: `job-mock`,
        createdAt: new Date().toISOString(),
        contractType: 'jeonse',
        riskScore: 72,
        riskLevel: 'high',
        summary: { high: 2, medium: 3, caution: 4, safe: 8 },
        clauses: [
          {
            id: 'clause-001',
            risk: 'high',
            clauseNumber: '제3조',
            originalText:
              '계약 만료 후 별도 통보 없이 계약이 종료된 것으로 간주하며, 임차인은 즉시 목적물을 반환하여야 한다.',
            explanation:
              '집주인에게 미리 연락하지 않으면 자동으로 계약이 끝나버릴 수 있어요. 이는 주택임대차보호법 제6조에서 보장하는 묵시적 갱신(자동 연장)을 제한하는 조항으로 세입자에게 매우 불리합니다.',
            lawReference: {
              lawName: '주택임대차보호법',
              article: '제6조 제1항',
              summary: '묵시적 갱신 — 계약 만료 전 일정 기간 내 이의제기가 없으면 계약이 자동 연장됨',
              url: 'https://www.law.go.kr/lsInfoP.do?lsiSeq=226389',
            },
            recommendation: '이 조항을 삭제하거나, 묵시적 갱신 관련 특약을 추가하세요.',
          },
          {
            id: 'clause-002',
            risk: 'high',
            clauseNumber: '제7조',
            originalText:
              '임대인은 보증금 반환 의무를 임차인의 원상복구 의무 이행 확인 후 30일 이내에 이행한다.',
            explanation:
              '보증금을 돌려받는 시기가 원상복구 확인 후 30일로 제한되어 있어요. 이사 나간 뒤 보증금을 빠르게 받지 못할 수 있어요.',
            lawReference: {
              lawName: '주택임대차보호법',
              article: '제3조의2',
              summary: '보증금 반환 — 임대차 종료 시 보증금을 즉시 반환해야 함',
            },
          },
          {
            id: 'clause-003',
            risk: 'medium',
            clauseNumber: '제5조',
            originalText: '임차인은 임대인의 동의 없이 목적물을 개조하거나 수선할 수 없다.',
            explanation:
              '집 안에서 못 하나 박거나 간단한 수리도 집주인 동의가 필요해요. 일상적인 생활이 불편할 수 있어요.',
            lawReference: {
              lawName: '민법',
              article: '제623조',
              summary: '임대인의 수선의무 — 임대목적물의 수선은 원칙적으로 임대인 의무',
            },
          },
          {
            id: 'clause-004',
            risk: 'medium',
            clauseNumber: '제8조',
            originalText:
              '천재지변, 화재, 기타 불가항력으로 인한 손해에 대해 임대인은 책임을 지지 아니한다.',
            explanation:
              '화재나 자연재해로 집이 손상되어도 집주인이 책임지지 않아요. 세입자가 별도 보험을 들어야 할 수 있어요.',
          },
          {
            id: 'clause-005',
            risk: 'medium',
            clauseNumber: '제9조',
            originalText:
              '임차인이 월세를 2회 이상 연체할 경우 임대인은 즉시 계약을 해지할 수 있다.',
            explanation:
              '월세를 두 번 밀리면 바로 퇴거 통보를 받을 수 있어요. 법적으로는 3회 연체가 기준인데 이보다 엄격한 조항이에요.',
            lawReference: {
              lawName: '주택임대차보호법',
              article: '제6조의3',
              summary: '계약 해지 — 월세 3회 연체 시 임대인의 해지 권리',
            },
          },
          {
            id: 'clause-006',
            risk: 'caution',
            clauseNumber: '제4조',
            originalText: '임차인은 계약 종료 30일 전까지 서면으로 해지 의사를 통보하여야 한다.',
            explanation:
              '이사 계획이 생기면 30일 전에 서면으로 알려야 해요. 이를 지키지 않으면 추가 비용이 발생할 수 있어요.',
          },
          {
            id: 'clause-007',
            risk: 'caution',
            originalText: '주차 공간은 1대로 제한하며, 추가 차량은 별도 협의한다.',
            explanation: '주차 공간이 1대로 제한돼요. 차가 2대 이상이라면 미리 협의가 필요해요.',
          },
          {
            id: 'clause-008',
            risk: 'caution',
            originalText: '반려동물은 임대인의 사전 서면 동의 후 허용된다.',
            explanation:
              '반려동물을 키우려면 집주인의 서면 동의가 필요해요. 미리 확인하지 않으면 나중에 분쟁이 생길 수 있어요.',
          },
          {
            id: 'clause-009',
            risk: 'safe',
            clauseNumber: '제1조',
            originalText:
              '임대인은 위 표시 부동산을 임차인에게 임대하고 임차인은 이를 임차하기로 한다.',
            explanation: '기본 임대차 계약 조항으로 특별히 문제될 내용이 없어요.',
          },
          {
            id: 'clause-010',
            risk: 'safe',
            clauseNumber: '제2조',
            originalText:
              '임대차 기간은 2024년 3월 1일부터 2026년 2월 28일까지 24개월로 한다.',
            explanation: '2년 계약 기간이 명확히 명시되어 있어요.',
          },
        ],
      },
    });
  }),

  // 잔여 할당량
  http.get(`${BASE}/user/quota`, async () => {
    await delay(300);
    return HttpResponse.json({
      success: true,
      data: {
        type: 'single',
        remaining: 3,
      },
    });
  }),

  // 분석 PDF 다운로드 (목업 — 빈 blob)
  http.get(`${BASE}/analysis/:reportId/pdf`, async () => {
    await delay(1000);
    return new HttpResponse(new Blob(['Mock PDF content'], { type: 'application/pdf' }), {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'attachment; filename="contract_analysis.pdf"',
      },
    });
  }),

  // ============================================================
  // 특약사항 API
  // ============================================================

  http.get(`${BASE}/analysis/:reportId/special-clauses`, async ({ params }) => {
    await delay(500);
    const { reportId } = params as { reportId: string };
    return HttpResponse.json({
      success: true,
      data: {
        reportId,
        clauses: [
          {
            id: 'sc-001',
            relatedRiskClauseId: 'clause-001',
            relatedRisk: 'high',
            title: '묵시적 갱신 관련 특약',
            text: '임대인은 계약 만료 6개월 전부터 2개월 전까지 갱신 거절 또는 조건 변경 의사를 서면으로 통지하여야 하며, 이를 위반할 경우 묵시적 갱신으로 본다. 묵시적 갱신 시 전 계약과 동일한 조건으로 2년간 연장된 것으로 간주한다.',
            category: 'renewal',
            isEditable: true,
          },
          {
            id: 'sc-002',
            relatedRiskClauseId: 'clause-002',
            relatedRisk: 'high',
            title: '보증금 반환 특약',
            text: '임대인은 임대차 계약 종료일로부터 14일 이내에 보증금 전액을 임차인에게 반환하여야 한다. 반환이 지체될 경우 지체 기간에 대해 연 12%의 지연이자를 지급한다.',
            category: 'deposit',
            isEditable: true,
          },
          {
            id: 'sc-003',
            relatedRiskClauseId: 'clause-003',
            relatedRisk: 'medium',
            title: '수선비 부담 특약',
            text: '시설물의 노후화, 자연마모 및 기능 저하로 인한 수선비는 임대인이 부담한다. 단, 임차인의 고의 또는 과실로 인한 파손 및 훼손은 임차인이 부담하며, 소액 수선(50,000원 미만)은 임차인이 부담하되 영수증을 첨부하여 임대인에게 청구할 수 있다.',
            category: 'repair',
            isEditable: true,
          },
        ],
      },
    });
  }),

  http.patch(`${BASE}/analysis/:reportId/special-clauses/:clauseId`, async ({ params, request }) => {
    await delay(400);
    const { clauseId } = params as { reportId: string; clauseId: string };
    const body = await request.json() as { text: string };
    return HttpResponse.json({
      success: true,
      data: {
        id: clauseId,
        text: body.text,
        updatedAt: new Date().toISOString(),
      },
    });
  }),

  http.get(`${BASE}/analysis/:reportId/special-clauses/pdf`, async () => {
    await delay(1000);
    return new HttpResponse(new Blob(['Mock Special Clauses PDF'], { type: 'application/pdf' }), {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'attachment; filename="special_clauses.pdf"',
      },
    });
  }),

  // ============================================================
  // 결제 API
  // ============================================================

  http.post(`${BASE}/payment/prepare`, async ({ request }) => {
    await delay(500);
    const body = await request.json() as { plan: string };
    const isPass = body.plan === 'pass_3month';
    return HttpResponse.json({
      success: true,
      data: {
        merchantUid: `order-${Date.now()}`,
        amount: isPass ? 4900 : 2900,
        plan: body.plan,
        planLabel: isPass ? '3개월 패스' : '건당 이용권',
        pgProvider: 'html5_inicis',
      },
    });
  }),

  http.post(`${BASE}/payment/verify`, async () => {
    await delay(800);
    return HttpResponse.json({
      success: true,
      data: {
        success: true,
        paymentId: `pay-${Date.now()}`,
        plan: 'single',
        amount: 2900,
        paidAt: new Date().toISOString(),
        quota: {
          type: 'single',
          remaining: 1,
        },
      },
    });
  }),

  // ============================================================
  // 헬스체크
  // ============================================================

  http.get(`${BASE}/health`, async () => {
    return HttpResponse.json({
      status: 'ok',
      version: '1.0.0',
      timestamp: new Date().toISOString(),
    });
  }),
];
