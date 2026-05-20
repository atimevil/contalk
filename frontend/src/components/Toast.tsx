import { useToast } from '../context/ToastContext';

const typeConfig = {
  success: { bg: 'bg-green-600', icon: '✅' },
  error: { bg: 'bg-red-600', icon: '❌' },
  warning: { bg: 'bg-yellow-500', icon: '⚠️' },
  info: { bg: 'bg-blue-600', icon: 'ℹ️' },
};

export default function ToastContainer() {
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed top-4 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2 w-full max-w-sm px-4"
      aria-live="assertive"
      aria-atomic="false"
    >
      {toasts.map((toast) => {
        const config = typeConfig[toast.type];
        return (
          <div
            key={toast.id}
            className={`${config.bg} text-white rounded-xl px-4 py-3 shadow-lg flex items-start gap-3 animate-slide-down`}
            role="alert"
          >
            <span className="text-base flex-shrink-0 mt-0.5" aria-hidden="true">{config.icon}</span>
            <p className="text-sm flex-1 leading-snug">{toast.message}</p>
            {toast.action && (
              <button
                onClick={toast.action.onClick}
                className="text-xs underline font-medium flex-shrink-0 hover:opacity-80"
              >
                {toast.action.label}
              </button>
            )}
            <button
              onClick={() => removeToast(toast.id)}
              className="flex-shrink-0 hover:opacity-80 focus:outline-none"
              aria-label="알림 닫기"
            >
              ✕
            </button>
          </div>
        );
      })}
    </div>
  );
}
