import { useEffect } from 'react';

interface AlertModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  type?: 'error' | 'success' | 'warning' | 'info';
  onClose: () => void;
}

export default function AlertModal({
  isOpen,
  title,
  message,
  type = 'info',
  onClose,
}: AlertModalProps) {
  if (!isOpen) return null;

  const typeStyles = {
    error: {
      icon: '❌',
      iconBg: 'bg-red-100',
      iconText: 'text-red-600',
      border: 'border-red-200',
      bg: 'bg-red-50',
    },
    success: {
      icon: '✅',
      iconBg: 'bg-green-100',
      iconText: 'text-green-600',
      border: 'border-green-200',
      bg: 'bg-green-50',
    },
    warning: {
      icon: '⚠️',
      iconBg: 'bg-yellow-100',
      iconText: 'text-yellow-600',
      border: 'border-yellow-200',
      bg: 'bg-yellow-50',
    },
    info: {
      icon: 'ℹ️',
      iconBg: 'bg-blue-100',
      iconText: 'text-blue-600',
      border: 'border-blue-200',
      bg: 'bg-blue-50',
    },
  };

  const style = typeStyles[type];



  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* 背景遮罩 */}
      <div
        className="fixed inset-0 bg-black/30 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* 提示框内容 */}
      <div className="relative z-10 w-full max-w-md animate-in fade-in zoom-in duration-200">
        <div className={`bg-white rounded-2xl shadow-2xl overflow-hidden border ${style.border}`}>
          {/* 头部 */}
          <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3">
            <div className={`w-10 h-10 ${style.iconBg} rounded-full flex items-center justify-center`}>
              <span className="text-xl">{style.icon}</span>
            </div>
            <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
            <button
              onClick={onClose}
              className="ml-auto text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* 内容 */}
          <div className="px-6 py-6">
            <p className="text-gray-600 leading-relaxed">{message}</p>
          </div>

          {/* 底部按钮 */}
          <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2.5 text-gray-700 bg-white border border-gray-300 rounded-xl hover:bg-gray-50 hover:border-gray-400 transition-all duration-200 font-medium"
            >
              确定
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}