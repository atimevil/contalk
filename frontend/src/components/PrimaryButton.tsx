import React from 'react';

interface PrimaryButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
  className?: string;
  type?: 'button' | 'submit';
}

const variantStyles = {
  primary:
    'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800 disabled:bg-gray-200 disabled:text-gray-400',
  secondary:
    'bg-white text-blue-600 border-2 border-blue-600 hover:bg-blue-50 disabled:bg-gray-100 disabled:text-gray-400 disabled:border-gray-300',
  ghost:
    'bg-transparent text-gray-600 hover:bg-gray-100 disabled:text-gray-300',
  danger:
    'bg-red-500 text-white hover:bg-red-600 active:bg-red-700 disabled:bg-gray-200 disabled:text-gray-400',
};

const sizeStyles = {
  sm: 'h-9 px-4 text-sm',
  md: 'h-12 px-6 text-base',
  lg: 'h-14 px-8 text-lg',
};

function Spinner() {
  return (
    <svg
      className="animate-spin h-5 w-5"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

export default function PrimaryButton({
  children,
  onClick,
  disabled = false,
  loading = false,
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  className = '',
  type = 'button',
}: PrimaryButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={[
        'inline-flex items-center justify-center rounded-xl font-semibold transition-all active:scale-95 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:active:scale-100',
        variantStyles[variant],
        sizeStyles[size],
        fullWidth ? 'w-full' : '',
        className,
      ].join(' ')}
      aria-busy={loading}
    >
      {loading ? (
        <span className="relative flex items-center justify-center">
          <Spinner />
          <span className="ml-2 opacity-0 pointer-events-none select-none absolute">{children}</span>
        </span>
      ) : (
        children
      )}
    </button>
  );
}
