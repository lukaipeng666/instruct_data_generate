import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { reportService } from '../services/api';
import type { Report } from '../types';
import ConfirmDialog from './ConfirmDialog';

export default function ReportManagement() {
  const navigate = useNavigate();
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedReportIds, setSelectedReportIds] = useState<string[]>([]);
  const [deleting, setDeleting] = useState(false);
  
  // 确认弹窗状态
  const [deleteConfirm, setDeleteConfirm] = useState<{ isOpen: boolean; taskId: string | null; isBatch: boolean }>({
    isOpen: false,
    taskId: null,
    isBatch: false,
  });

  useEffect(() => {
    loadReports();
  }, []);

  const loadReports = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await reportService.getAllReports();
      setReports(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载报告列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (taskId: string) => {
    try {
      setError('');
      await reportService.downloadReportData(taskId);
    } catch (err: any) {
      const errorMessage = err.message || err.response?.data?.detail || '下载失败，请检查任务是否有生成数据';
      setError(errorMessage);
    }
  };

  const handleDownloadCsv = async (taskId: string) => {
    try {
      setError('');
      await reportService.downloadReportDataAsCsv(taskId);
    } catch (err: any) {
      const errorMessage = err.message || err.response?.data?.detail || '下载CSV失败';
      setError(errorMessage);
    }
  };

  // 跳转到编辑页面
  const handleOpenEditor = (taskId: string) => {
    navigate(`/editor/${encodeURIComponent(taskId)}`);
  };

  const handleSelectReport = (taskId: string) => {
    setSelectedReportIds(prev => {
      if (prev.includes(taskId)) {
        return prev.filter(id => id !== taskId);
      } else {
        return [...prev, taskId];
      }
    });
  };

  const handleSelectAll = () => {
    if (selectedReportIds.length === reports.length) {
      setSelectedReportIds([]);
    } else {
      setSelectedReportIds(reports.map(r => r.task_id));
    }
  };

  const handleDeleteSingle = async (taskId: string) => {
    setDeleteConfirm({ isOpen: true, taskId, isBatch: false });
  };

  const confirmDelete = async () => {
    const { taskId, isBatch } = deleteConfirm;
    setDeleteConfirm({ isOpen: false, taskId: null, isBatch: false });

    setDeleting(true);
    setError('');
    try {
      if (isBatch) {
        // 批量删除
        if (selectedReportIds.length === 0) {
          setError('请至少选择一个报告');
          return;
        }
        const result = await reportService.batchDeleteReports(selectedReportIds);
        if (result.errors && result.errors.length > 0) {
          setError(`部分删除失败: ${result.errors.map((e: any) => e.error).join(', ')}`);
        }
        await loadReports();
        setSelectedReportIds([]);
      } else {
        // 单个删除
        await reportService.deleteReport(taskId!);
        await loadReports();
        setSelectedReportIds([]);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '删除报告失败');
    } finally {
      setDeleting(false);
    }
  };

  const handleBatchDelete = async () => {
    if (selectedReportIds.length === 0) {
      setError('请至少选择一个报告');
      return;
    }
    setDeleteConfirm({ isOpen: true, taskId: null, isBatch: true });
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN');
  };

  const getStatusBadge = (status: string) => {
    const statusMap: { [key: string]: { text: string; className: string } } = {
      running: { text: '运行中', className: 'bg-blue-100 text-blue-700' },
      finished: { text: '已完成', className: 'bg-green-100 text-green-700' },
      error: { text: '失败', className: 'bg-red-100 text-red-700' },
      stopped: { text: '已停止', className: 'bg-gray-100 text-gray-700' },
    };
    const { text, className } = statusMap[status] || { text: status, className: 'bg-gray-100 text-gray-700' };
    return <span className={`px-3 py-1 rounded-full text-xs font-medium ${className}`}>{text}</span>;
  };

  return (
    <div className="space-y-6">
      {/* 错误提示 */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
          {error}
        </div>
      )}

      {/* 报告列表卡片 */}
      <div className="bg-white rounded-2xl shadow-sm p-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">报告管理</h2>
          <div className="flex gap-3">
            {selectedReportIds.length > 0 && (
              <button
                onClick={handleBatchDelete}
                disabled={deleting}
                className="px-4 py-2 bg-red-500 hover:bg-red-600 disabled:bg-gray-300 text-white rounded-lg text-sm font-medium transition-colors"
              >
                {deleting ? '删除中...' : `🗑️ 批量删除 (${selectedReportIds.length})`}
              </button>
            )}
            <button
              onClick={loadReports}
              disabled={loading}
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 text-white rounded-lg text-sm font-medium transition-colors"
            >
              🔄 刷新
            </button>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
            <p className="mt-4 text-gray-500">加载中...</p>
          </div>
        ) : reports.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">📊</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">暂无报告</h3>
            <p className="text-gray-500">当您完成任务后，报告将会在这里显示</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left">
                    <input
                      type="checkbox"
                      checked={reports.length > 0 && selectedReportIds.length === reports.length}
                      onChange={handleSelectAll}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                  </th>
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
                    开始时间
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    结束时间
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {reports.map((report) => (
                  <tr key={report.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <input
                        type="checkbox"
                        checked={selectedReportIds.includes(report.task_id)}
                        onChange={() => handleSelectReport(report.task_id)}
                        className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                      />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-mono font-medium text-gray-900">{report.task_id}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getStatusBadge(report.status)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-semibold text-blue-600">{report.data_count}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{formatDate(report.started_at)}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{formatDate(report.finished_at)}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <div className="flex gap-2">
                        {report.has_data && (
                          <>
                            <button
                              onClick={() => handleOpenEditor(report.task_id)}
                              className="px-3 py-1 bg-purple-100 hover:bg-purple-200 text-purple-700 rounded-lg font-medium transition-colors"
                            >
                              ✏️ 编辑数据
                            </button>
                            <div className="relative group">
                              <button
                                className="px-3 py-1 bg-green-100 hover:bg-green-200 text-green-700 rounded-lg font-medium transition-colors"
                              >
                                💾 下载 ▼
                              </button>
                              <div className="absolute left-0 mt-1 w-36 bg-white rounded-lg shadow-lg border border-gray-200 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
                                <button
                                  onClick={() => handleDownload(report.task_id)}
                                  className="block w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 rounded-t-lg"
                                >
                                  下载 JSONL
                                </button>
                                <button
                                  onClick={() => handleDownloadCsv(report.task_id)}
                                  className="block w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 rounded-b-lg"
                                >
                                  下载 CSV
                                </button>
                              </div>
                            </div>
                          </>
                        )}
                        <button
                          onClick={() => handleDeleteSingle(report.task_id)}
                          disabled={deleting}
                          className="px-3 py-1 bg-red-100 hover:bg-red-200 disabled:bg-gray-100 text-red-700 disabled:text-gray-400 rounded-lg font-medium transition-colors"
                        >
                          🗑️ 删除
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 删除报告确认弹窗 */}
      <ConfirmDialog
        isOpen={deleteConfirm.isOpen}
        title={deleteConfirm.isBatch ? '批量删除报告' : '删除报告'}
        message={deleteConfirm.isBatch 
          ? `确认删除选中的 ${selectedReportIds.length} 个报告吗？删除后不可恢复。`
          : `确认删除报告 ${deleteConfirm.taskId} 吗？删除后不可恢复。`}
        type="danger"
        confirmText="删除"
        cancelText="取消"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteConfirm({ isOpen: false, taskId: null, isBatch: false })}
      />
    </div>
  );
}
