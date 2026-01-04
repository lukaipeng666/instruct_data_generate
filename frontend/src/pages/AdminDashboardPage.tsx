import { useState } from 'react';
import { authService } from '../services/api';
import { useAuthStore } from '../store/authStore';
import ModelManagement from '../components/ModelManagement';
import UserManagement from '../components/UserManagement';

type TabType = 'models' | 'users';

export default function AdminDashboardPage() {
  const { username, clearAuth } = useAuthStore();
  const [activeTab, setActiveTab] = useState<TabType>('models');

  const handleLogout = async () => {
    try {
      await authService.logout();
    } catch (err) {
      console.error('登出失败:', err);
    }
    clearAuth();
    window.location.href = '/login';
  };

  const tabs: { key: TabType; label: string; icon: string }[] = [
    { key: 'models', label: '模型管理', icon: '🤖' },
    { key: 'users', label: '用户管理', icon: '👥' },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-xl border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">管理员控制台</h1>
            <p className="text-sm text-gray-500 mt-1">系统管理与配置</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-xs font-medium">
                管理员
              </span>
              <span className="text-sm text-gray-600">{username}</span>
            </div>
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium text-gray-700 transition-colors"
            >
              退出登录
            </button>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6">
          <nav className="flex gap-8">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`py-4 px-2 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.key
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <span className="mr-2">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {activeTab === 'models' && <ModelManagement />}
        {activeTab === 'users' && <UserManagement />}
      </main>
    </div>
  );
}
