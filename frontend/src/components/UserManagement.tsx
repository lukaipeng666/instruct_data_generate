import { useState, useEffect } from 'react';
import { adminService } from '../services/api';
import type { AdminUser, Report } from '../types';
import ConfirmDialog from './ConfirmDialog';

export default function UserManagement() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // 用户报告相关状态
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);
  const [userReports, setUserReports] = useState<Report[]>([]);
  const [loadingReports, setLoadingReports] = useState(false);
  
  // 确认弹窗状态
  const [deleteConfirm, setDeleteConfirm] = useState<{ isOpen: boolean; user: AdminUser | null }>({
    isOpen: false,
    user: null,
  });

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const data = await adminService.getAllUsers();
      setUsers(data);
    } catch (err: any) {
      setError(err.response?.data?.error || '加载用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (user: AdminUser) => {
    setDeleteConfirm({ isOpen: true, user });
  };

  const confirmDelete = async () => {
    const { user } = deleteConfirm;
    if (!user) return;
    
    setDeleteConfirm({ isOpen: false, user: null });
    
    try {
      setLoading(true);
      setError('');
      setSuccess('');
      await adminService.deleteUser(user.id);
      setSuccess(`用户 ${user.username} 已删除`);
      loadUsers();
      if (selectedUser?.id === user.id) {
        setSelectedUser(null);
        setUserReports([]);
      }
    } catch (err: any) {
      setError(err.response?.data?.error || '删除失败');
    } finally {
      setLoading(false);
    }
  };

  const handleViewReports = async (user: AdminUser) => {
    try {
      setLoadingReports(true);
      setError('');
      setSelectedUser(user);
      const response = await adminService.getUserReports(user.id);
      setUserReports(response.reports);
    } catch (err: any) {
      setError(err.response?.data?.error || '加载用户报告失败');
    } finally {
      setLoadingReports(false);
    }
  };

  const handleDownloadReport = async (report: Report) => {
    if (!selectedUser) return;
    
    try {
      setError('');
      await adminService.downloadUserReport(selectedUser.id, report.task_id);
    } catch (err: any) {
      setError(err.message || '下载失败');
    }
  };

  const handleBackToUsers = () => {
    setSelectedUser(null);
    setUserReports([]);
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('zh-CN');
  };

  // 用户报告列表视图
  if (selectedUser) {
    return (
      <div>
        {/* Alerts */}
        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
            {error}
          </div>
        )}

        {/* Header with back button */}
        <div className="mb-6 flex items-center gap-4">
          <button
            onClick={handleBackToUsers}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium text-gray-700 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            返回用户列表
          </button>
        </div>

        <div className="mb-6">
          <h2 className="text-2xl font-semibold text-gray-900">
            {selectedUser.username} 的报告
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            共 {userReports.length} 个报告
          </p>
        </div>

        {/* Reports Table */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          {loadingReports ? (
            <div className="p-12 text-center text-gray-500">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
              加载中...
            </div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    任务ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    状态
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    数据条数
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    审核状态
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    开始时间
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    完成时间
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {userReports.map((report) => (
                  <tr key={report.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900 max-w-xs truncate" title={report.task_id}>
                        {report.task_id}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-medium ${
                          report.status === 'completed'
                            ? 'bg-green-100 text-green-700'
                            : report.status === 'running'
                            ? 'bg-blue-100 text-blue-700'
                            : report.status === 'failed'
                            ? 'bg-red-100 text-red-700'
                            : 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {report.status === 'completed' ? '已完成' : 
                         report.status === 'running' ? '运行中' : 
                         report.status === 'failed' ? '失败' : report.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`text-sm ${report.data_count > 0 ? 'text-green-600 font-medium' : 'text-gray-500'}`}>
                        {report.data_count} 条
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {report.has_data ? (
                        report.is_fully_reviewed ? (
                          <span className="px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">
                            ✅ 已审核完毕
                          </span>
                        ) : (
                          <span className="px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">
                            {report.confirmed_count || 0}/{report.data_count} 已审核
                          </span>
                        )
                      ) : (
                        <span className="text-sm text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(report.started_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(report.finished_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <button
                        onClick={() => handleDownloadReport(report)}
                        disabled={!report.has_data}
                        className={`${
                          report.has_data
                            ? 'text-blue-600 hover:text-blue-900'
                            : 'text-gray-400 cursor-not-allowed'
                        }`}
                        title={report.has_data ? '下载 JSONL' : '暂无数据可下载'}
                      >
                        下载
                      </button>
                    </td>
                  </tr>
                ))}
                {userReports.length === 0 && !loadingReports && (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                      该用户暂无报告数据
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    );
  }

  // 用户列表视图
  return (
    <div>
      {/* Alerts */}
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-xl text-green-600 text-sm">
          {success}
        </div>
      )}

      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-semibold text-gray-900">用户管理</h2>
        <p className="text-sm text-gray-500 mt-1">查看和管理系统用户，点击用户查看其报告</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="text-sm text-gray-500">总用户数</div>
          <div className="text-3xl font-bold text-gray-900 mt-2">{users.length}</div>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="text-sm text-gray-500">管理员</div>
          <div className="text-3xl font-bold text-purple-600 mt-2">
            {users.filter(u => u.is_admin).length}
          </div>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="text-sm text-gray-500">普通用户</div>
          <div className="text-3xl font-bold text-blue-600 mt-2">
            {users.filter(u => !u.is_admin).length}
          </div>
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                用户名
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                角色
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                状态
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                报告数
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                创建时间
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                操作
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {users.map((user) => (
              <tr 
                key={user.id} 
                className="hover:bg-gray-50 cursor-pointer"
                onClick={() => handleViewReports(user)}
              >
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <div className="flex-shrink-0 h-10 w-10 bg-blue-100 rounded-full flex items-center justify-center">
                      <span className="text-blue-600 font-medium text-sm">
                        {user.username.charAt(0).toUpperCase()}
                      </span>
                    </div>
                    <div className="ml-4">
                      <div className="text-sm font-medium text-gray-900">{user.username}</div>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-medium ${
                      user.is_admin
                        ? 'bg-purple-100 text-purple-700'
                        : 'bg-blue-100 text-blue-700'
                    }`}
                  >
                    {user.is_admin ? '管理员' : '普通用户'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`px-2 py-1 rounded-full text-xs font-medium ${
                      user.is_active
                        ? 'bg-green-100 text-green-700'
                        : 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {user.is_active ? '活跃' : '禁用'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="text-sm text-blue-600 font-medium">
                    {user.report_count} 个报告
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {formatDate(user.created_at)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  <div className="flex gap-3">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleViewReports(user);
                      }}
                      className="text-blue-600 hover:text-blue-900"
                      title="查看报告"
                    >
                      查看报告
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(user);
                      }}
                      disabled={loading || user.is_admin}
                      className={`${
                        user.is_admin
                          ? 'text-gray-400 cursor-not-allowed'
                          : 'text-red-600 hover:text-red-900'
                      }`}
                      title={user.is_admin ? '不能删除管理员账号' : '删除用户'}
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {users.length === 0 && !loading && (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                  暂无用户数据
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Warning */}
      <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-xl">
        <div className="flex items-start">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-yellow-800">注意</h3>
            <div className="mt-2 text-sm text-yellow-700">
              <ul className="list-disc list-inside space-y-1">
                <li>点击用户行可以查看该用户的所有报告</li>
                <li>删除用户将同时删除该用户的所有任务和报告数据</li>
                <li>管理员账号不能被删除</li>
                <li>删除操作不可恢复，请谨慎操作</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* 删除用户确认弹窗 */}
      <ConfirmDialog
        isOpen={deleteConfirm.isOpen}
        title="删除用户"
        message={`确定要删除用户 "${deleteConfirm.user?.username}" 及其所有关联数据吗？此操作不可恢复！`}
        type="danger"
        confirmText="删除"
        cancelText="取消"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteConfirm({ isOpen: false, user: null })}
      />
    </div>
  );
}
