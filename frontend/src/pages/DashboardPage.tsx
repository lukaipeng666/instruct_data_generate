import { useState } from 'react';
import { authService } from '../services/api';
import { useAuthStore } from '../store/authStore';
import TaskManagement from '../components/TaskManagement';
import DataManagement from '../components/DataManagement';
import ReportManagement from '../components/ReportManagement';

type TabType = 'task' | 'data' | 'report';

export default function DashboardPage() {
  const { username, clearAuth } = useAuthStore();
  const [activeTab, setActiveTab] = useState<TabType>('task');

  const handleLogout = async () => {
    try {
      await authService.logout();
    } catch (err) {
      console.error('登出失败:', err);
    }
    clearAuth();
    window.location.href = '/login';
  };

  const tabs = [
    { id: 'task' as TabType, name: '任务管理', icon: '⚡' },
    { id: 'data' as TabType, name: '数据管理', icon: '📁' },
    { id: 'report' as TabType, name: '报告管理', icon: '📊' },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-xl border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-semibold text-gray-900">数据生成任务管理</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600">欢迎, {username}</span>
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium text-gray-700 transition-colors"
            >
              退出登录
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Tab Navigation */}
        <div className="bg-white rounded-2xl shadow-sm p-2 mb-6">
          <div className="flex gap-2">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 px-6 py-4 rounded-xl font-semibold transition-all duration-200 ${
                  activeTab === tab.id
                    ? 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-lg'
                    : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                <span className="text-xl mr-2">{tab.icon}</span>
                {tab.name}
              </button>
            ))}
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'task' && <TaskManagement />}
        {activeTab === 'data' && <DataManagement />}
        {activeTab === 'report' && <ReportManagement />}
      </main>
    </div>
  );
}

