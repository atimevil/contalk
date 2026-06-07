import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import NavBar from '../components/NavBar';
import BottomNavBar from '../components/BottomNavBar';
import PrimaryButton from '../components/PrimaryButton';
import { paymentApi } from '../api/payment';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import type { PaymentPlan } from '../types/api';

type PaymentMethod = 'card' | 'kakaopay' | 'tosspay';

const IS_DEMO = import.meta.env.VITE_DEMO_MODE === 'true';
const IMP_CODE = import.meta.env.VITE_PORTONE_IMP_CODE || '';

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
    label: '단건 분석 이용권',
    price: 2900,
    features: ['계약서 1건 즉시 분석', 'AI 조항별 특약사항 제공', '분석 결과 PDF 평생 소장'],
  },
  {
    plan: 'pass_3month',
    label: '3개월 프리패스',
    price: 19900,
    features: ['3개월간 횟수 제한 없이 무제한 분석', '과거 분석 이력 무제한 재열람 및 보관', '우선 고객 지원 및 VIP 케어'],
    badge: '가장 추천',
  },
];

const PAYMENT_METHODS: { id: PaymentMethod; label: string; icon: string }[] = [
  { id: 'card', label: '카드', icon: '💳' },
  { id: 'kakaopay', label: '카카오페이', icon: '🟡' },
  { id: 'tosspay', label: '토스페이', icon: '🔵' },
];

export default function PaymentPage() {
  const navigate = useNavigate();
  const { isLoggedIn, updateQuota } = useAuth();
  const { showToast } = useToast();
  const [selectedPlan, setSelectedPlan] = useState<PaymentPlan>('single');
  const [selectedMethod, setSelectedMethod] = useState<PaymentMethod>('card');

  const selectedProduct = PRODUCTS.find((p) => p.plan === selectedPlan)!;

  const payMutation = useMutation({
    mutationFn: async () => {
      if (!isLoggedIn) {
        navigate('/login', { state: { from: '/payment' } });
        throw new Error('LOGIN_REQUIRED');
      }

      // 결제 준비
      const prepareData = await paymentApi.prepare({ plan: selectedPlan });

      // 데모 모드: 포트원 SDK 없이 mock uid로 즉시 검증
      if (IS_DEMO) {
        const mockImpUid = `mock-imp-${Date.now()}`;
        const verifyData = await paymentApi.verify({
          impUid: mockImpUid,
          merchantUid: prepareData.merchantUid,
        });
        return verifyData;
      }

      // 실제 결제: 포트원 SDK 호출
      if (!window.IMP) {
        throw new Error('포트원 결제 모듈을 불러올 수 없습니다.');
      }

      window.IMP.init(IMP_CODE);

      // PG사 매핑
      const pgMap: Record<PaymentMethod, string> = {
        card: prepareData.pgProvider || 'html5_inicis',
        kakaopay: 'kakaopay',
        tosspay: 'tosspay',
      };

      const impUid = await new Promise<string>((resolve, reject) => {
        window.IMP!.request_pay(
          {
            pg: pgMap[selectedMethod],
            pay_method: selectedMethod === 'card' ? 'card' : 'point',
            merchant_uid: prepareData.merchantUid,
            name: selectedProduct.label,
            amount: prepareData.amount,
            m_redirect_url: `${window.location.origin}/payment/complete`,
          },
          (response) => {
            if (response.success) {
              resolve(response.imp_uid);
            } else {
              reject(new Error(response.error_msg || '결제가 취소되었어요.'));
            }
          }
        );
      });

      // 결제 검증
      const verifyData = await paymentApi.verify({
        impUid,
        merchantUid: prepareData.merchantUid,
      });

      return verifyData;
    },
    onSuccess: (data) => {
      updateQuota(data.quota);
      showToast({ type: 'success', message: '결제가 완료되었어요! 🎉' });
      navigate('/upload');
    },
    onError: (error: unknown) => {
      const err = error as { message?: string };
      if (err?.message === 'LOGIN_REQUIRED') return;

      const msg = '결제에 실패했어요. 다시 시도해주세요.';
      showToast({ type: 'error', message: msg });
    },
  });

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar title="이용권 구매" showBack />

      <main className="max-w-2xl mx-auto px-4 pt-20 pb-6 space-y-5">
        {/* 상품 선택 */}
        <section>
          <h2 className="text-base font-semibold text-gray-900 mb-3">이용권을 선택해주세요</h2>
          <div className="space-y-3">
            {PRODUCTS.map((product) => {
              const isSelected = selectedPlan === product.plan;
              return (
                <button
                  key={product.plan}
                  onClick={() => setSelectedPlan(product.plan)}
                  className={`w-full text-left rounded-2xl border-2 p-5 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm relative overflow-hidden ${
                    isSelected
                      ? 'border-blue-600 bg-blue-50/50 scale-[1.01]'
                      : 'border-gray-200 bg-white hover:border-gray-300 hover:scale-[1.005]'
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
                            ? 'border-blue-600 bg-blue-600'
                            : 'border-gray-300'
                        }`}
                        aria-hidden="true"
                      >
                        {isSelected && (
                          <span className="w-2.5 h-2.5 bg-white rounded-full" />
                        )}
                      </span>
                      <span className="font-bold text-base text-gray-900">{product.label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {product.badge && (
                        <span className="text-[10px] bg-gradient-to-r from-amber-500 to-red-500 text-white px-2.5 py-0.5 rounded-full font-bold shadow-sm uppercase tracking-wider animate-pulse">
                          {product.badge}
                        </span>
                      )}
                      <span className="text-xl font-extrabold text-blue-600">
                        {product.price.toLocaleString()}원
                      </span>
                    </div>
                  </div>

                  <ul className="mt-3.5 ml-8 space-y-1.5 relative z-10">
                    {product.features.map((feature) => (
                      <li key={feature} className="text-sm text-gray-600 flex items-center gap-2">
                        <span className="text-blue-500 text-sm font-bold" aria-hidden="true">✓</span>
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
          <h2 className="text-base font-semibold text-gray-900 mb-3">결제 수단 선택</h2>
          <div className="flex gap-3">
            {PAYMENT_METHODS.map((method) => {
              const isSelected = selectedMethod === method.id;
              // 결제 수단별 세련된 컬러 테두리 및 그림자 칩 정의
              const activeStyles = {
                card: 'border-blue-600 bg-blue-50/50 text-blue-600 shadow-sm',
                kakaopay: 'border-yellow-400 bg-yellow-50/50 text-yellow-800 shadow-sm',
                tosspay: 'border-blue-500 bg-blue-50/40 text-blue-800 shadow-sm',
              }[method.id];

              return (
                <button
                  key={method.id}
                  onClick={() => setSelectedMethod(method.id)}
                  className={`flex-1 flex flex-col items-center gap-1.5 py-3.5 rounded-xl border-2 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-blue-500 ${
                    isSelected
                      ? activeStyles
                      : 'border-gray-200 bg-white hover:border-gray-300 hover:scale-[1.02] shadow-sm'
                  }`}
                  aria-pressed={isSelected}
                >
                  <span className="text-2xl" aria-hidden="true">{method.icon}</span>
                  <span className={`text-xs font-bold transition-colors ${isSelected ? '' : 'text-gray-500'}`}>
                    {method.label}
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        {/* 주문 요약 */}
        <section className="bg-white border border-gray-200 rounded-xl p-4 shadow-card">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">주문 요약</h2>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">상품</span>
              <span className="text-gray-900 font-medium">{selectedProduct.label}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">금액</span>
              <span className="text-gray-900 font-medium">
                {selectedProduct.price.toLocaleString()}원
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">부가세</span>
              <span className="text-gray-900">포함</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">결제 수단</span>
              <span className="text-gray-900">
                {PAYMENT_METHODS.find((m) => m.id === selectedMethod)?.label}
              </span>
            </div>
            <div className="border-t border-gray-200 pt-2 flex justify-between font-bold">
              <span className="text-gray-900">최종 결제 금액</span>
              <span className="text-blue-600 text-lg">
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
          <p className="text-xs text-gray-500 flex items-center justify-center gap-1">
            <span aria-hidden="true">🔒</span> 안전하게 암호화된 결제
          </p>
          <p className="text-xs text-gray-400">포트원(iamport) 결제 시스템 사용</p>
        </div>
      </main>

      <BottomNavBar />
    </div>
  );
}
