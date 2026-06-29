import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import * as PortOne from '@portone/browser-sdk/v2';
import NavBar from '../components/NavBar';
import BottomNavBar from '../components/BottomNavBar';
import PrimaryButton from '../components/PrimaryButton';
import { paymentApi } from '../api/payment';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import type { PaymentPlan } from '../types/api';

const IS_DEMO = import.meta.env.VITE_DEMO_MODE === 'true';
const STORE_ID = import.meta.env.VITE_PORTONE_STORE_ID || '';
const CHANNEL_KEY = import.meta.env.VITE_PORTONE_CHANNEL_KEY || '';

interface ProductOption {
  plan: PaymentPlan;
  label: string;
  price: number;
  features: string[];
  badge?: string;
}

const PRODUCTS: ProductOption[] = [
  {
    plan: 'single',
    label: '단건 분석',
    price: 2900,
    features: ['계약서 1건 즉시 분석', 'AI 조항별 위험도 상세 리포트', '특약사항 추천 + PDF 저장'],
  },
  {
    plan: 'pass_3month',
    label: '월정액 무제한',
    price: 9900,
    features: ['한 달간 횟수 제한 없이 무제한 분석', '과거 분석 이력 무제한 열람', '우선 고객 지원'],
    badge: '추천',
  },
];

export default function PaymentPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isLoggedIn, user, updateQuota, refreshUser } = useAuth();
  const { showToast } = useToast();
  const [selectedPlan, setSelectedPlan] = useState<PaymentPlan>('single');

  const selectedProduct = PRODUCTS.find((p) => p.plan === selectedPlan)!;

  const payMutation = useMutation({
    mutationFn: async () => {
      if (!isLoggedIn) {
        navigate('/login', { state: { from: '/payment' } });
        throw new Error('LOGIN_REQUIRED');
      }

      // 결제 준비 (백엔드에서 merchant_uid = paymentId 발급)
      const prepareData = await paymentApi.prepare({ plan: selectedPlan });

      // 데모 모드: 포트원 SDK 없이 mock으로 즉시 검증
      if (IS_DEMO) {
        const verifyData = await paymentApi.verify({
          merchantUid: prepareData.merchantUid,
        });
        return verifyData;
      }

      // 실제 결제: 포트원 V2 SDK 호출
      // 이니시스 V2는 구매자 이메일 필수. placeholder(@kakao.local)면 기본 이메일 사용
      const buyerEmail =
        user?.email && !user.email.endsWith('@kakao.local')
          ? user.email
          : 'customer@contalktok.kr';

      const response = await PortOne.requestPayment({
        storeId: STORE_ID,
        channelKey: CHANNEL_KEY,
        paymentId: prepareData.merchantUid,
        orderName: selectedProduct.label,
        totalAmount: prepareData.amount,
        currency: 'CURRENCY_KRW',
        payMethod: 'CARD',
        customer: {
          email: buyerEmail,
          fullName: user?.nickname || '계약똑똑 사용자',
          phoneNumber: '010-0000-0000',
        },
      });

      if (response?.code !== undefined) {
        // 결제 실패 또는 취소
        throw new Error(response.message || '결제가 취소되었어요.');
      }

      // 결제 검증 (paymentId = merchantUid)
      const verifyData = await paymentApi.verify({
        merchantUid: prepareData.merchantUid,
      });

      return verifyData;
    },
    onSuccess: async (data) => {
      updateQuota(data.quota);
      await refreshUser();
      showToast({ type: 'success', message: '결제가 완료되었어요! 🎉' });
      // 결제 전 보던 화면으로 복귀 (없으면 홈)
      const from = (location.state as { from?: string })?.from;
      navigate(from || '/', { replace: true });
    },
    onError: (error: unknown) => {
      const err = error as { message?: string };
      if (err?.message === 'LOGIN_REQUIRED') return;

      const msg = '결제에 실패했어요. 다시 시도해주세요.';
      showToast({ type: 'error', message: msg });
    },
  });

  return (
    <div className="min-h-screen bg-slate-50 pb-24">
      <NavBar title="이용권 구매" showBack />

      <main className="max-w-3xl mx-auto px-4 pt-20 pb-6 space-y-5">
        {/* 상품 선택 */}
        <section>
          <h2 className="text-sm font-bold text-slate-900 mb-3">이용권을 선택해주세요</h2>
          <div className="space-y-3">
            {PRODUCTS.map((product) => {
              const isSelected = selectedPlan === product.plan;
              return (
                <button
                  key={product.plan}
                  onClick={() => setSelectedPlan(product.plan)}
                  className={`w-full text-left rounded-xl border-2 p-5 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-brand-600 shadow-card relative overflow-hidden ${
                    isSelected
                      ? 'border-brand-600 bg-brand-50/50 scale-[1.01]'
                      : 'border-slate-200 bg-white hover:border-slate-300 hover:scale-[1.005]'
                  }`}
                  aria-pressed={isSelected}
                >
                  {/* 가장 추천 요금제일 시 미묘한 백그라운드 그라데이션 장식 */}
                  {product.plan === 'pass_3month' && isSelected && (
                    <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-br from-yellow-300/10 to-transparent rounded-full -mr-8 -mt-8 pointer-events-none" />
                  )}

                  <div className="flex items-start justify-between gap-3 relative z-10">
                    <div className="flex items-center gap-3">
                      <span
                        className={`flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all ${
                          isSelected
                            ? 'border-brand-600 bg-brand-600'
                            : 'border-slate-300'
                        }`}
                        aria-hidden="true"
                      >
                        {isSelected && (
                          <span className="w-2.5 h-2.5 bg-white rounded-full" />
                        )}
                      </span>
                      <span className="font-bold text-base text-slate-900">{product.label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {product.badge && (
                        <span className="text-[10px] bg-gradient-to-r from-amber-500 to-red-500 text-white px-2.5 py-0.5 rounded-full font-bold shadow-sm uppercase tracking-wider animate-pulse">
                          {product.badge}
                        </span>
                      )}
                      <span className="text-xl font-extrabold text-brand-600">
                        {product.price.toLocaleString()}원
                      </span>
                    </div>
                  </div>

                  <ul className="mt-3.5 ml-8 space-y-1.5 relative z-10">
                    {product.features.map((feature) => (
                      <li key={feature} className="text-sm text-slate-600 flex items-center gap-2">
                        <span className="text-brand-600 text-sm font-bold" aria-hidden="true">✓</span>
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>
                </button>
              );
            })}
          </div>
        </section>

        {/* 결제 수단 */}
        <section>
          <h2 className="text-sm font-bold text-slate-900 mb-3">결제 수단</h2>
          <div className="card flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center border border-brand-100">
              <svg className="w-5 h-5 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-bold text-slate-900">신용 / 체크카드</p>
              <p className="text-xs text-slate-500">KG이니시스 안전결제</p>
            </div>
          </div>
        </section>

        {/* 주문 요약 */}
        <section className="card">
          <h2 className="text-sm font-bold text-slate-700 mb-3">주문 요약</h2>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">상품</span>
              <span className="text-slate-900 font-medium">{selectedProduct.label}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">금액</span>
              <span className="text-slate-900 font-medium">
                {selectedProduct.price.toLocaleString()}원
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">부가세</span>
              <span className="text-slate-900">포함</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">결제 수단</span>
              <span className="text-slate-900">
                신용/체크카드
              </span>
            </div>
            <div className="border-t border-slate-200 pt-2 flex justify-between font-bold">
              <span className="text-slate-900">최종 결제 금액</span>
              <span className="text-brand-600 text-lg">
                {selectedProduct.price.toLocaleString()}원
              </span>
            </div>
          </div>
        </section>

        {/* 결제 버튼 */}
        <PrimaryButton
          size="lg"
          fullWidth
          loading={payMutation.isPending}
          onClick={() => payMutation.mutate()}
        >
          {payMutation.isPending ? '결제 처리 중...' : `${selectedProduct.price.toLocaleString()}원 결제하기 →`}
        </PrimaryButton>

        {/* 신뢰 문구 */}
        <div className="text-center space-y-1">
          <p className="text-xs text-slate-500 flex items-center justify-center gap-1">
            <span aria-hidden="true">🔒</span> 안전하게 암호화된 결제
          </p>
          <p className="text-xs text-slate-400">포트원(iamport) 결제 시스템 사용</p>
        </div>
      </main>

      <BottomNavBar />
    </div>
  );
}
