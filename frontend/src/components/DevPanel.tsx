import { useState } from 'react';
import { useAuth } from '../context/AuthContext';

/**
 * 개발자 전용 디버그 패널 — Vite DEV 환경에서만 표시.
 * 무료/유료 모드 전환, quota 상태 확인 등.
 */
export default function DevPanel() {
  const { quota, updateQuota, isLoggedIn } = useAuth();
  const [isOpen, setIsOpen] = useState(false);

  if (!import.meta.env.DEV) return null;

  const setFreeMode = () => {
    updateQuota({ type: 'free_trial', remaining: 1 });
  };

  const setPaidSingle = () => {
    updateQuota({ type: 'single', remaining: 5 });
  };

  const setPaidPass = () => {
    updateQuota({ type: 'pass_3month', remaining: -1 });
  };

  const setNoQuota = () => {
    updateQuota({ type: 'none', remaining: 0 });
  };

  return (
    <div className="fixed bottom-20 right-3 z-[9999]">
      {!isOpen ? (
        <button
          onClick={() => setIsOpen(true)}
          className="w-10 h-10 bg-slate-800 text-white rounded-full shadow-lg flex items-center justify-center text-sm font-bold hover:bg-slate-700 transition-colors"
          title="개발자 패널"
        >
          🛠
        </button>
      ) : (
        <div className="bg-slate-900 text-white rounded-xl shadow-xl p-3 w-56 text-xs space-y-2">
          <div className="flex items-center justify-between mb-1">
            <span className="font-bold text-[10px] text-slate-400 uppercase tracking-wider">Dev Panel</span>
            <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-white text-lg leading-none">×</button>
          </div>

          <div className="bg-slate-800 rounded-lg p-2 space-y-1">
            <p className="text-[10px] text-slate-400">현재 상태</p>
            <p className="font-mono">로그인: {isLoggedIn ? '✅' : '❌'}</p>
            <p className="font-mono">quota: {quota?.type ?? 'null'} ({quota?.remaining ?? 0})</p>
          </div>

          <p className="text-[10px] text-slate-400 pt-1">Quota 모드 전환</p>
          <div className="grid grid-cols-2 gap-1.5">
            <button onClick={setFreeMode} className="bg-amber-600 hover:bg-amber-500 text-white px-2 py-1.5 rounded font-bold transition-colors">
              무료체험
            </button>
            <button onClick={setPaidSingle} className="bg-emerald-600 hover:bg-emerald-500 text-white px-2 py-1.5 rounded font-bold transition-colors">
              단건유료
            </button>
            <button onClick={setPaidPass} className="bg-blue-600 hover:bg-blue-500 text-white px-2 py-1.5 rounded font-bold transition-colors">
              월정액
            </button>
            <button onClick={setNoQuota} className="bg-red-600 hover:bg-red-500 text-white px-2 py-1.5 rounded font-bold transition-colors">
              소진(none)
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
