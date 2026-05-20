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
    label: '건당 이용',
    price: 2900,
    features: ['계약서 1건 분석', '특약사항 추천 포함', '결과 PDF 다운로드'],
  },
  {
    plan: 'pass_3month',
    label: '3개월 패스',
    price: 4900,
    features: ['3개월간 무제한 분석', '이력 저장 및 재열람', '우선 고객 지원'],
    badge: '인기',
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

      // MSW 환경에서는 포트원 SDK 없이 바로 검증 호출
      // 실제 환경에서는 window.IMP를 통한 결제 후 검증
      const mockImpUid = `mock-imp-${Date.now()}`;

      // 결제 검증
      const verifyData = await paymentApi.verify({
        impUid: mockImpUid,
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
            {PRODUCTS.map((product) => (
              <button
                key={product.plan}
                onClick={() => setSelectedPlan(product.plan)}
                className={`w-full text-left rounded-xl border-2 p-4 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  selectedPlan === product.plan
                    ? 'border-blue-600 bg-blue-50'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                }`}
                aria-pressed={selectedPlan === product.plan}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span
                      className={`flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                        selectedPlan === product.plan
                          ? 'border-blue-600 bg-blue-600'
                          : 'border-gray-300'
                      }`}
                      aria-hidden="true"
                    >
                      {selectedPlan === product.plan && (
                        <span className="w-2 h-2 bg-white rounded-full" />
                      )}
                    </span>
                    <span className="font-semibold text-gray-900">{product.label}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {product.badge && (
                      <span className="text-xs bg-red-500 text-white px-2 py-0.5 rounded-full font-medium">
                        {product.badge}
                      </span>
                    )}
                    <span className="text-xl font-bold text-blue-600">
                      {product.price.toLocaleString()}원
                    </span>
                  </div>
                </div>

                <ul className="mt-3 ml-8 space-y-1">
                  {product.features.map((feature) => (
                    <li key={feature} className="text-sm text-gray-600 flex items-center gap-2">
                      <span className="text-green-500 text-xs" aria-hidden="true">·</span>
                      {feature}
                    </li>
                  ))}
                </ul>
              </button>
            ))}
          </div>
        </section>

        {/* 결제 수단 */}
        <section>
          <h2 className="text-base font-semibold text-gray-900 mb-3">결제 수단</h2>
          <div className="flex gap-2">
            {PAYMENT_METHODS.map((method) => (
              <button
                key={method.id}
                onClick={() => setSelectedMethod(method.id)}
                className={`flex-1 flex flex-col items-center gap-1 py-3 rounded-xl border-2 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  selectedMethod === method.id
                    ? 'border-blue-600 bg-blue-50'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                }`}
                aria-pressed={selectedMethod === method.id}
              >
                <span className="text-xl" aria-hidden="true">{method.icon}</span>
                <span className={`text-xs font-medium ${selectedMethod === method.id ? 'text-blue-600' : 'text-gray-600'}`}>
                  {method.label}
                </span>
              </button>
            ))}
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
