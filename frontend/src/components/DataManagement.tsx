import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { dataService } from '../services/api';
import type { DataFile } from '../types';
import ConfirmDialog from './ConfirmDialog';

export default function DataManagement() {
  const navigate = useNavigate();
  const [files, setFiles] = useState<DataFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<Set<number>>(new Set());
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{ [key: string]: number }>({});
  const [downloading, setDownloading] = useState<Set<number>>(new Set());
  const [converting, setConverting] = useState(false);
  const [convertingFiles, setConvertingFiles] = useState<{ [key: string]: number }>({});
  const fileInputRef = useRef<HTMLInputElement>(null);
  const convertInputRef = useRef<HTMLInputElement>(null);
  
  // 确认弹窗状态
  const [deleteConfirm, setDeleteConfirm] = useState<{ isOpen: boolean; fileId: number | null; isBatch: boolean }>({
    isOpen: false,
    fileId: null,
    isBatch: false,
  });
  
  // 查看文件内容状态
  const [viewingFile, setViewingFile] = useState<{ id: number; filename: string; data: any[] } | null>(null);
  const [viewLoading, setViewLoading] = useState(false);

  useEffect(() => {
    loadFiles();
  }, []);

  const loadFiles = async () => {
    try {
      setLoading(true);
      const data = await dataService.getDataFiles();
      setFiles(data);
    } catch (err: any) {
      setError(err.response?.data?.error || '加载文件列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (selectedFiles.length === 0) return;

    // 检查文件格式，支持jsonl和csv
    const invalidFiles = selectedFiles.filter(file => !file.name.endsWith('.jsonl') && !file.name.endsWith('.csv'));
    if (invalidFiles.length > 0) {
      setError(`不支持的文件格式：${invalidFiles.map(f => f.name).join(', ')}`);
      return;
    }

    try {
      setUploading(true);
      setError('');
      setSuccess('');

      // 逐个上传文件
      const uploadPromises = selectedFiles.map(async (file) => {
        const progressKey = file.name;
        setUploadProgress(prev => ({ ...prev, [progressKey]: 0 }));

        try {
          await dataService.uploadDataFile(file);
          setUploadProgress(prev => ({ ...prev, [progressKey]: 100 }));
          const isCSV = file.name.endsWith('.csv');
          return { success: true, file: file.name, message: `文件 ${file.name} 上传成功${isCSV ? '（已转换为JSONL格式）' : ''}` };
        } catch (err: any) {
          setUploadProgress(prev => ({ ...prev, [progressKey]: -1 }));
          return { success: false, file: file.name, message: err.response?.data?.detail || '上传失败' };
        }
      });

      const results = await Promise.all(uploadPromises);

      // 统计结果
      const successCount = results.filter(r => r.success).length;
      const failureCount = results.filter(r => !r.success).length;

      if (failureCount > 0) {
        setError(`${successCount} 个文件成功，${failureCount} 个文件失败`);
      } else {
        setSuccess(`成功上传 ${successCount} 个文件`);
      }

      await loadFiles();
      // 清空文件选择
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      setUploadProgress({});
    } catch (err: any) {
      setError(err.response?.data?.detail || '上传文件失败');
    } finally {
      setUploading(false);
    }
  };

  // 处理文件转换
  const handleConvert = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (selectedFiles.length === 0) return;

    // 检查文件格式
    const invalidFiles = selectedFiles.filter(file => !file.name.endsWith('.jsonl') && !file.name.endsWith('.csv'));
    if (invalidFiles.length > 0) {
      setError(`不支持的文件格式：${invalidFiles.map(f => f.name).join(', ')}`);
      return;
    }

    try {
      setConverting(true);
      setError('');
      setSuccess('');

      // 初始化转换进度
      selectedFiles.forEach(file => {
        setConvertingFiles(prev => ({ ...prev, [file.name]: 0 }));
      });

      // 模拟进度更新（因为后端直接返回ZIP，无法获取真实进度）
      let progress = 0;
      const progressInterval = setInterval(() => {
        progress += 20;
        if (progress >= 90) {
          clearInterval(progressInterval);
        }
        selectedFiles.forEach(file => {
          setConvertingFiles(prev => ({ ...prev, [file.name]: Math.min(progress, 90) }));
        });
      }, 200);

      await dataService.convertFilesDirect(selectedFiles);

      clearInterval(progressInterval);

      // 设置100%完成
      selectedFiles.forEach(file => {
        setConvertingFiles(prev => ({ ...prev, [file.name]: 100 }));
      });

      const message = selectedFiles.length === 1
        ? '成功转换 1 个文件（CSV ↔ JSONL）'
        : `成功转换 ${selectedFiles.length} 个文件（已打包成 ZIP）`;
      setSuccess(message);

      // 清空文件选择
      if (convertInputRef.current) {
        convertInputRef.current.value = '';
      }
      setConvertingFiles({});
    } catch (err: any) {
      setError(err.message || '文件转换失败');
      setConvertingFiles({});
    } finally {
      setConverting(false);
    }
  };

  const handleDelete = async (fileId: number) => {
    setDeleteConfirm({ isOpen: true, fileId, isBatch: false });
  };

  const confirmDelete = async () => {
    const { fileId, isBatch } = deleteConfirm;
    setDeleteConfirm({ isOpen: false, fileId: null, isBatch: false });

    try {
      setError('');
      setSuccess('');
      
      if (isBatch) {
        // 批量删除
        const result = await dataService.batchDeleteDataFiles(Array.from(selectedFiles));
        
        if (result.errors.length > 0) {
          setError(`删除完成，${result.deleted_count} 个成功，${result.errors.length} 个失败`);
        } else {
          setSuccess(`成功删除 ${result.deleted_count} 个文件`);
        }
        setSelectedFiles(new Set());
      } else {
        // 单个删除
        await dataService.deleteDataFile(fileId!);
        setSuccess('文件删除成功');
        setSelectedFiles(prev => {
          const newSet = new Set(prev);
          newSet.delete(fileId!);
          return newSet;
        });
      }
      
      await loadFiles();
    } catch (err: any) {
      setError(err.response?.data?.detail || '删除文件失败');
    }
  };

  const handleBatchDelete = async () => {
    if (selectedFiles.size === 0) {
      setError('请先选择要删除的文件');
      return;
    }
    setDeleteConfirm({ isOpen: true, fileId: null, isBatch: true });
  };

  // 下载单个文件
  const handleDownloadFile = async (file: DataFile) => {
    try {
      setError('');
      setDownloading(prev => new Set(prev).add(file.id));
      await dataService.downloadDataFile(file.id);
      setSuccess(`文件 ${file.name} 下载成功`);
    } catch (err: any) {
      setError(err.message || '下载失败');
    } finally {
      setDownloading(prev => {
        const newSet = new Set(prev);
        newSet.delete(file.id);
        return newSet;
      });
    }
  };

  // 批量下载文件
  const handleBatchDownload = async () => {
    if (selectedFiles.size === 0) {
      setError('请先选择要下载的文件');
      return;
    }

    try {
      setError('');
      const fileIds = Array.from(selectedFiles);
      await dataService.batchDownloadDataFiles(fileIds);
      setSuccess(`成功下载 ${fileIds.length} 个文件（已打包成 ZIP）`);
    } catch (err: any) {
      setError(err.message || '批量下载失败');
    }
  };

  const toggleSelectFile = (fileId: number) => {
    setSelectedFiles(prev => {
      const newSet = new Set(prev);
      if (newSet.has(fileId)) {
        newSet.delete(fileId);
      } else {
        newSet.add(fileId);
      }
      return newSet;
    });
  };

  const toggleSelectAll = () => {
    if (selectedFiles.size === files.length) {
      setSelectedFiles(new Set());
    } else {
      setSelectedFiles(new Set(files.map(f => f.id)));
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  const formatDateTime = (isoString: string): string => {
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  // 查看文件内容
  const handleViewContent = async (file: DataFile) => {
    try {
      setViewLoading(true);
      setError('');
      const content = await dataService.getDataFileContent(file.id);
      setViewingFile({
        id: file.id,
        filename: content.filename,
        data: content.data,
      });
    } catch (err: any) {
      setError(err.message || '获取文件内容失败');
    } finally {
      setViewLoading(false);
    }
  };

  // 关闭查看弹窗
  const closeViewModal = () => {
    setViewingFile(null);
  };

  return (
    <div className="space-y-6">
      {/* Alerts */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-xl text-green-600 text-sm">
          {success}
        </div>
      )}

      {/* Upload Section */}
      <div className="bg-white rounded-2xl shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">上传数据文件</h3>
        
        {/* 上传进度显示 */}
        {Object.keys(uploadProgress).length > 0 && (
          <div className="mb-4 space-y-2">
            {Object.entries(uploadProgress).map(([fileName, progress]) => (
              <div key={fileName} className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700 truncate">{fileName}</span>
                  <span className={`text-sm ${
                    progress === 100 ? 'text-green-600' :
                    progress > 0 ? 'text-blue-600' :
                    progress === -1 ? 'text-red-600' : 'text-gray-600'
                  }`}>
                    {progress === -1 ? '失败' : `${progress}%`}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      progress === 100 ? 'bg-green-500' :
                      progress > 0 ? 'bg-blue-500' :
                      'bg-red-500'
                    }`}
                    style={{ width: `${Math.max(0, progress)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
        
        <div className="flex items-center gap-4">
          <input
            ref={fileInputRef}
            type="file"
            accept=".jsonl,.csv"
            multiple
            onChange={handleUpload}
            disabled={uploading}
            className="flex-1 px-4 py-3 border border-gray-300 rounded-xl bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
          />
          {uploading && (
            <div className="flex items-center gap-2 text-blue-600">
              <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span className="text-sm">上传中...</span>
            </div>
          )}
        </div>
        <p className="mt-2 text-sm text-gray-500">支持批量上传多个 .jsonl 和 .csv 文件（CSV文件将自动转换为JSONL格式存储）</p>
      </div>

      {/* File Convert Section */}
      <div className="bg-white rounded-2xl shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">文件格式转换</h3>

        {/* 转换进度显示 */}
        {Object.keys(convertingFiles).length > 0 && (
          <div className="mb-4 space-y-2">
            {Object.entries(convertingFiles).map(([fileName, progress]) => (
              <div key={fileName} className="bg-purple-50 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700 truncate">{fileName}</span>
                  <span className={`text-sm ${
                    progress === 100 ? 'text-green-600' :
                    progress > 0 ? 'text-purple-600' : 'text-gray-600'
                  }`}>
                    {progress === 100 ? '完成' : `${progress}%`}
                  </span>
                </div>
                <div className="w-full bg-purple-200 rounded-full h-2 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      progress === 100 ? 'bg-green-500' : 'bg-purple-500'
                    }`}
                    style={{ width: `${Math.max(0, progress)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center gap-4">
          <input
            ref={convertInputRef}
            type="file"
            accept=".jsonl,.csv"
            multiple
            onChange={handleConvert}
            disabled={converting}
            className="flex-1 px-4 py-3 border border-gray-300 rounded-xl bg-gray-50 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100"
          />
          {converting && (
            <div className="flex items-center gap-2 text-purple-600">
              <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span className="text-sm">转换中...</span>
            </div>
          )}
        </div>
        <p className="mt-2 text-sm text-gray-500">支持批量转换 .jsonl 和 .csv 文件（CSV ↔ JSONL 自动转换，转换后自动下载ZIP包）</p>
      </div>

      {/* File List Section */}
      <div className="bg-white rounded-2xl shadow-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">我的数据文件</h3>
          <div className="flex items-center gap-2">
            {selectedFiles.size > 0 && (
              <>
                <button
                  onClick={handleBatchDownload}
                  className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium transition-colors"
                >
                  下载选中 ({selectedFiles.size})
                </button>
                <button
                  onClick={handleBatchDelete}
                  className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg font-medium transition-colors"
                >
                  批量删除 ({selectedFiles.size})
                </button>
              </>
            )}
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-500">加载中...</p>
          </div>
        ) : files.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">📁</div>
            <p className="text-gray-500">暂无数据文件，请上传</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left">
                    <input
                      type="checkbox"
                      checked={selectedFiles.size === files.length && files.length > 0}
                      onChange={toggleSelectAll}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    文件名
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    大小
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    上传时间
                  </th>
                  <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {files.map((file) => (
                  <tr key={file.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <input
                        type="checkbox"
                        checked={selectedFiles.has(file.id)}
                        onChange={() => toggleSelectFile(file.id)}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="text-sm font-medium text-gray-900">{file.name}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{formatFileSize(file.size)}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{formatDateTime(file.upload_time)}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleDownloadFile(file)}
                          disabled={downloading.has(file.id)}
                          className="text-green-600 hover:text-green-900 disabled:text-gray-400"
                          title="下载文件"
                        >
                          {downloading.has(file.id) ? '下载中...' : '下载'}
                        </button>
                        <button
                          onClick={() => navigate(`/data-editor/${file.id}`)}
                          className="text-purple-600 hover:text-purple-900"
                          title="编辑文件"
                        >
                          编辑
                        </button>
                        <button
                          onClick={() => handleViewContent(file)}
                          className="text-blue-600 hover:text-blue-900"
                          disabled={viewLoading}
                          title="查看内容"
                        >
                          查看
                        </button>
                        <button
                          onClick={() => handleDelete(file.id)}
                          className="text-red-600 hover:text-red-900"
                          title="删除文件"
                        >
                          删除
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

      {/* View Content Modal */}
      {viewingFile && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl max-w-4xl w-full mx-4 max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">
                文件内容: {viewingFile.filename}
                <span className="ml-2 text-sm text-gray-500">(共 {viewingFile.data.length} 条数据)</span>
              </h3>
              <button
                onClick={closeViewModal}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-auto p-6">
              <div className="space-y-4">
                {viewingFile.data.map((item, index) => (
                  <div key={index} className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-500">第 {index + 1} 条</span>
                    </div>
                    <pre className="text-sm text-gray-800 whitespace-pre-wrap break-words overflow-auto max-h-60 bg-white p-3 rounded border">
                      {JSON.stringify(item, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
              <button
                onClick={closeViewModal}
                className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-medium transition-colors"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 删除确认弹窗 */}
      <ConfirmDialog
        isOpen={deleteConfirm.isOpen}
        title={deleteConfirm.isBatch ? '批量删除文件' : '删除文件'}
        message={deleteConfirm.isBatch 
          ? `确定要删除选中的 ${selectedFiles.size} 个文件吗？` 
          : '确定要删除这个文件吗？'}
        type="danger"
        confirmText="删除"
        cancelText="取消"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteConfirm({ isOpen: false, fileId: null, isBatch: false })}
      />
    </div>
  );
}
