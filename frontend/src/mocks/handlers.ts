import { http, HttpResponse, delay } from 'msw';

const BASE = '/api/v1';

// UUID 생성 도우미 함수 (MSW 가짜 환경에서도 실제 프로덕션과 똑같이 UUID를 보여주기 위해)
function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// 분석 상태 시뮬레이션을 위한 인메모리 상태
const jobStatusMap = new Map<string, { step: number; startTime: number }>();

export const handlers = [
  // ============================================================
  // 인증 API
  // ============================================================

  // 개발 테스트 로그인 (백엔드 APP_ENV=development 전용 — MSW 폴백)
  http.post(`${BASE}/auth/dev-login`, async () => {
    await delay(300);
    return HttpResponse.json({
      success: true,
      data: {
        accessToken: 'mock-dev-access-token',
        refreshToken: 'mock-dev-refresh-token',
        user: {
          id: 'dev-user-001',
          email: 'dev-test@contalktok.kr',
          nickname: '테스트유저',
          profileImageUrl: null,
          provider: 'kakao',
          createdAt: new Date().toISOString(),
        },
        isNewUser: false,
      },
    });
  }),

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
    const jobId = generateUUID();
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
      const reportId = generateUUID();
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
    const isPass = body.plan === 'pass_1month' || body.plan === 'pass_3month';
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
  // 시세 조회 API (market)
  // ============================================================

  // 시도·시군구 코드 목록
  http.get(`${BASE}/market/districts`, async () => {
    await delay(300);
    return HttpResponse.json({
      items: [
        {
          name: '서울특별시', code: '11',
          시군구: [
            { name: '강남구', code: '11680' },
            { name: '강동구', code: '11740' },
            { name: '강북구', code: '11305' },
            { name: '강서구', code: '11500' },
            { name: '관악구', code: '11620' },
            { name: '광진구', code: '11215' },
            { name: '구로구', code: '11530' },
            { name: '금천구', code: '11545' },
            { name: '노원구', code: '11350' },
            { name: '도봉구', code: '11320' },
            { name: '동대문구', code: '11230' },
            { name: '동작구', code: '11590' },
            { name: '마포구', code: '11440' },
            { name: '서대문구', code: '11410' },
            { name: '서초구', code: '11650' },
            { name: '성동구', code: '11200' },
            { name: '성북구', code: '11290' },
            { name: '송파구', code: '11710' },
            { name: '양천구', code: '11470' },
            { name: '영등포구', code: '11560' },
            { name: '용산구', code: '11170' },
            { name: '은평구', code: '11380' },
            { name: '종로구', code: '11110' },
            { name: '중구', code: '11140' },
            { name: '중랑구', code: '11260' },
          ],
        },
        {
          name: '경기도', code: '41',
          시군구: [
            { name: '성남시 분당구', code: '41135' },
            { name: '수원시 영통구', code: '41117' },
            { name: '고양시 일산동구', code: '41285' },
            { name: '용인시 수지구', code: '41465' },
            { name: '안양시 동안구', code: '41173' },
            { name: '부천시', code: '41190' },
            { name: '화성시', code: '41590' },
            { name: '남양주시', code: '41360' },
          ],
        },
        {
          name: '인천광역시', code: '28',
          시군구: [
            { name: '연수구', code: '28185' },
            { name: '남동구', code: '28200' },
            { name: '부평구', code: '28237' },
            { name: '서구', code: '28260' },
          ],
        },
        {
          name: '부산광역시', code: '26',
          시군구: [
            { name: '해운대구', code: '26350' },
            { name: '수영구', code: '26410' },
            { name: '남구', code: '26290' },
          ],
        },
      ],
    });
  }),

  // 시군구 내 법정동(동) 목록
  http.get(`${BASE}/market/dongs`, async ({ request }) => {
    await delay(300);
    const url = new URL(request.url);
    const districtCode = url.searchParams.get('district_code') || '';

    const mockDongs: Record<string, string[]> = {
      '11680': ['개포동', '논현동', '대치동', '도곡동', '삼성동', '세곡동', '수서동', '신사동', '압구정동', '역삼동', '일원동', '청담동'],
      '11740': ['강일동', '고덕동', '길동', '둔촌동', '명일동', '상일동', '성내동', '암사동', '천호동'],
      '11305': ['미아동', '번동', '수유동', '우이동'],
      '11500': ['가양동', '공항동', '방화동', '염창동', '우장산동', '화곡동'],
      '11620': ['봉천동', '신림동'],
      '11215': ['광장동', '구의동', '군자동', '능동', '자양동', '중곡동', '화양동'],
      '11530': ['가리봉동', '개봉동', '고척동', '구로동', '신도림동', '오류동', '온수동', '항동'],
      '11545': ['가산동', '독산동', '시흥동'],
      '11350': ['공릉동', '상계동', '월계동', '중계동', '하계동'],
      '11320': ['도봉동', '방학동', '쌍문동', '창동'],
      '11230': ['답십리동', '신설동', '용두동', '이문동', '전농동', '제기동', '청량리동', '휘경동'],
      '11590': ['대방동', '동작동', '본동', '사당동', '상도동', '신대방동', '흑석동'],
      '11440': ['공덕동', '대흥동', '도화동', '마포동', '망원동', '상암동', '성산동', '아현동', '염리동', '용강동', '합정동'],
      '11410': ['남가좌동', '냉천동', '대현동', '미근동', '북가좌동', '신촌동', '연희동', '창천동', '천연동', '홍제동', '홍은동'],
      '11650': ['내곡동', '반포동', '방배동', '서초동', '양재동', '잠원동'],
      '11200': ['금호동', '마장동', '사근동', '성수동', '송정동', '용답동', '하왕십리동', '행당동', '홍익동'],
      '11290': ['길음동', '돈암동', '동선동', '보문동', '석관동', '성북동', '장위동', '정릉동', '종암동'],
      '11710': ['가락동', '거여동', '마천동', '문정동', '방이동', '삼전동', '석촌동', '송파동', '오금동', '위례동', '잠실동', '장지동', '풍납동'],
      '11470': ['목동', '신정동'],
      '11560': ['당산동', '대림동', '도림동', '문래동', '신길동', '양평동', '여의도동', '영등포동'],
      '11170': ['동빙고동', '서빙고동', '원효로동', '이촌동', '이태원동', '한강로동', '한남동', '후암동'],
      '11380': ['갈현동', '녹번동', '대조동', '불광동', '수색동', '신사동', '역촌동', '응암동', '증산동'],
      '11110': ['계동', '교남동', '궁정동', '내수동', '누상동', '누하동', '명륜동', '묘동', '부암동', '사직동', '삼청동', '세종로', '소격동', '신교동', '청진동', '체부동', '통의동', '팔판동', '평동', '혜화동', '홍지동', '효자동'],
      '11140': ['광희동', '남대문로', '남산동', '다산동', '만리동', '명동', '묵정동', '봉래동', '신당동', '을지로', '의주로', '장충동', '저동', '주교동', '청구동', '태평로', '필동', '회현동'],
      '11260': ['면목동', '묵동', '상봉동', '신내동', '중화동'],
      // 경기도
      '41135': ['구미동', '금곡동', '대장동', '동원동', '백현동', '분당동', '삼평동', '서현동', '석운동', '수내동', '야탑동', '운중동', '이매동', '정자동'],
      '41117': ['광교동', '매탄동', '망포동', '신동', '원천동', '이의동', '하동'],
      '41285': ['대화동', '마두동', '백석동', '식사동', '장항동', '정발산동', '중산동', '풍동'],
      '41465': ['동천동', '상현동', '성복동', '신봉동', '풍덕천동'],
      '41173': ['관양동', '귀인동', '달안동', '비산동', '호계동'],
      '41190': ['괴안동', '소사동', '심곡동', '역곡동', '원미동', '중동'],
      '41590': ['동탄동', '반송동', '반정동', '봉담읍', '향남읍'],
      '41360': ['다산동', '별내동', '오남읍', '와부읍', '진건읍'],
      // 인천
      '28185': ['동춘동', '송도동', '연수동', '옥련동'],
      '28200': ['간석동', '구월동', '만수동', '서창동'],
      '28237': ['갈산동', '부평동', '산곡동', '삼산동'],
      '28260': ['가좌동', '검단동', '검암동', '당하동', '마전동'],
      // 부산
      '26350': ['반송동', '반여동', '석대동', '우동', '재송동', '중동'],
      '26410': ['광안동', '남천동', '민락동', '수영동', '망미동'],
      '26290': ['대연동', '문현동', '용당동', '용호동'],
    };

    const dongs = mockDongs[districtCode] ?? ['중앙동', '신흥동', '동부동', '서부동'];

    return HttpResponse.json({
      district_code: districtCode,
      dongs,
    });
  }),

  // 매매+전세 통합 시세 요약 (전세가율 계산용)
  http.get(`${BASE}/market/summary`, async ({ request }) => {
    await delay(800);
    const url = new URL(request.url);
    const districtCode = url.searchParams.get('district_code') || '11680';

    // 지역별 실거래가 목업 데이터
    // 실거래가 목업 (2025-03 MOLIT API 실측 기준)
    const mockData: Record<string, { name: string; avgTrade: number; avgDeposit: number }> = {
      '11680': { name: '서울특별시 강남구', avgTrade: 2_900_000_000, avgDeposit: 1_200_000_000 },
      '11740': { name: '서울특별시 강동구', avgTrade: 1_050_000_000, avgDeposit: 550_000_000 },
      '11350': { name: '서울특별시 노원구', avgTrade: 650_000_000, avgDeposit: 277_350_000 }, // 실측: 평균 27,735만원
      '11305': { name: '서울특별시 강북구', avgTrade: 450_000_000, avgDeposit: 230_000_000 },
      '11710': { name: '서울특별시 송파구', avgTrade: 1_400_000_000, avgDeposit: 700_000_000 },
      '11650': { name: '서울특별시 서초구', avgTrade: 2_600_000_000, avgDeposit: 1_100_000_000 },
      '11440': { name: '서울특별시 마포구', avgTrade: 1_100_000_000, avgDeposit: 560_000_000 },
      '41135': { name: '경기도 성남시 분당구', avgTrade: 1_100_000_000, avgDeposit: 560_000_000 },
      '41590': { name: '경기도 화성시', avgTrade: 480_000_000, avgDeposit: 240_000_000 },
      '28185': { name: '인천광역시 연수구', avgTrade: 550_000_000, avgDeposit: 290_000_000 },
    };

    const region = mockData[districtCode] ?? {
      name: '해당 지역',
      avgTrade: 700_000_000,
      avgDeposit: 380_000_000,
    };

    const jeonseRatio = Math.round((region.avgDeposit / region.avgTrade) * 100 * 10) / 10;

    return HttpResponse.json({
      district_code: districtCode,
      district_name: region.name,
      deal_ym: new Date().toISOString().slice(0, 7).replace('-', ''),
      trade: {
        count: Math.floor(Math.random() * 50) + 30,
        avg_price_krw: region.avgTrade,
        min_price_krw: Math.round(region.avgTrade * 0.65),
        max_price_krw: Math.round(region.avgTrade * 1.35),
      },
      rent: {
        count: Math.floor(Math.random() * 30) + 15,
        avg_deposit_krw: region.avgDeposit,
        min_deposit_krw: Math.round(region.avgDeposit * 0.6),
        max_deposit_krw: Math.round(region.avgDeposit * 1.4),
      },
      jeonse_ratio_pct: jeonseRatio,
      market_queries_remaining: 2,
      market_queries_limit: 3,
      disclaimer: '본 시세 정보는 국토교통부 실거래가 자료를 기반으로 하며 참고용으로만 활용하세요.',
    });
  }),

  // 아파트 매매 실거래가 통계
  http.get(`${BASE}/market/apt-trade`, async ({ request }) => {
    await delay(700);
    const url = new URL(request.url);
    const districtCode = url.searchParams.get('district_code') || '11680';

    return HttpResponse.json({
      district_code: districtCode,
      district_name: '서울특별시 강남구',
      deal_ym: '202503',
      count: 42,
      avg_price_krw: 2_900_000_000,
      min_price_krw: 1_800_000_000,
      max_price_krw: 4_500_000_000,
      items: [
        { apartment: '래미안대치팰리스', area: 84.97, price_krw: 3_100_000_000, floor: '12', deal_date: '2025-03-15' },
        { apartment: '도곡렉슬', area: 59.97, price_krw: 2_350_000_000, floor: '8', deal_date: '2025-03-10' },
      ],
    });
  }),

  // 아파트 전세 실거래가 통계
  http.get(`${BASE}/market/apt-rent`, async ({ request }) => {
    await delay(700);
    const url = new URL(request.url);
    const districtCode = url.searchParams.get('district_code') || '11680';

    return HttpResponse.json({
      district_code: districtCode,
      district_name: '서울특별시 강남구',
      deal_ym: '202503',
      count: 28,
      avg_deposit_krw: 1_200_000_000,
      min_deposit_krw: 700_000_000,
      max_deposit_krw: 1_800_000_000,
      items: [
        { apartment: '래미안대치팰리스', area: 84.97, deposit_krw: 1_300_000_000, monthly_rent_krw: 0, is_jeonse: true, floor: '5', deal_date: '2025-03-12' },
        { apartment: '도곡렉슬', area: 59.97, deposit_krw: 900_000_000, monthly_rent_krw: 0, is_jeonse: true, floor: '3', deal_date: '2025-03-08' },
      ],
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
