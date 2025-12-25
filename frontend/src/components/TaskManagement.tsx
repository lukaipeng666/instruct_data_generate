import { useState, useEffect, useRef, FormEvent } from 'react';
import { taskService, dataService } from '../services/api';
import type { TaskParams, DataFile, ModelConfig } from '../types';

// 任务进度数据类型
interface TaskProgressData {
  task_id: string;
  status: string;
  current_round: number;
  total_rounds: number;
  generated_count: number;
  progress_percent: number;
  completion_percent?: number;
  source: string;
}

export default function TaskManagement() {
  const [taskTypes, setTaskTypes] = useState<string[]>([]);
  const [dataFiles, setDataFiles] = useState<DataFile[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState<string[]>([]);
  const [taskStatus, setTaskStatus] = useState<'idle' | 'running' | 'finished' | 'error'>('idle');
  const [taskProgress, setTaskProgress] = useState<TaskProgressData | null>(null);
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const [formData, setFormData] = useState<TaskParams>({
    input_file: '',
    output: '', // 保留字段但不显示，后端可能需要
    model_id: undefined,
    task_type: 'general',
    batch_size: 16,
    max_concurrent: 16,
    min_score: 10,
    variants_per_sample: 3,
    data_rounds: 10,
    retry_times: 3,
    special_prompt: '',
    directions: '信用卡年费 股票爆仓 基金赎回',
  });

  useEffect(() => {
    loadData();
    checkActiveTask();
    
    // 清理进度轮询
    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
    };
  }, []);

  const loadData = async () => {
    try {
      const [types, files, modelConfigs] = await Promise.all([
        taskService.getTaskTypes(),
        dataService.getDataFiles(),
        taskService.getActiveModels(), // 使用普通用户接口获取激活的模型
      ]);
      setTaskTypes(types);
      setDataFiles(files);
      setModels(modelConfigs); // 已经过滤了is_active=true的模型
      
      if (types.length > 0 && !formData.task_type) {
        setFormData((prev) => ({ ...prev, task_type: types[0] }));
      }
      
      // 如果有可用模型，默认选择第一个
      if (modelConfigs.length > 0 && !formData.model_id) {
        setFormData((prev) => ({ ...prev, model_id: modelConfigs[0].id }));
      }
    } catch (err) {
      console.error('加载数据失败:', err);
    }
  };

  const checkActiveTask = async () => {
    try {
      const result = await taskService.getActiveTask();
      if (result.success && result.task_id) {
        setCurrentTaskId(result.task_id);
        setTaskStatus('running');
        connectProgress(result.task_id);
        startProgressPolling(result.task_id);
      }
    } catch (err) {
      console.error('检查活动任务失败:', err);
    }
  };
  
  // 开始轮询任务进度
  const startProgressPolling = (taskId: string) => {
    // 清除之前的轮询
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
    }
    
    // 立即获取一次
    fetchTaskProgress(taskId);
    
    // 每2秒轮询一次
    progressIntervalRef.current = setInterval(() => {
      fetchTaskProgress(taskId);
    }, 2000);
  };
  
  // 停止轮询任务进度
  const stopProgressPolling = () => {
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }
  };
  
  // 获取任务进度
  const fetchTaskProgress = async (taskId: string) => {
    try {
      const result = await taskService.getTaskProgress(taskId);
      if (result.success && result.progress) {
        setTaskProgress(result.progress);
        
        // 如果任务完成，停止轮询
        if (result.progress.status === 'completed' || result.progress.status === 'failed') {
          stopProgressPolling();
        }
      }
    } catch (err) {
      // 静默失败，不影响用户体验
      console.error('获取任务进度失败:', err);
    }
  };

  const connectProgress = (taskId: string) => {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    let abortController = new AbortController();
    
    fetch(`/api/progress/${taskId}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      signal: abortController.signal,
    })
      .then((response) => {
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        if (!reader) return;

        const readStream = () => {
          reader.read().then(({ done, value }) => {
            if (done) return;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.substring(6));
                  if (data.type === 'output') {
                    setProgress((prev) => [...prev, data.line]);
                  } else if (data.type === 'finished') {
                    setTaskStatus(data.return_code === 0 ? 'finished' : 'error');
                    abortController.abort();
                  }
                } catch (err) {
                  console.error('解析进度数据失败:', err);
                }
              }
            }

            readStream();
          }).catch(() => {
            // 连接关闭
          });
        };

        readStream();
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          console.error('连接进度流失败:', error);
        }
      });
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      // 验证必填项
      if (!formData.input_file) {
        setError('请选择数据文件');
        setLoading(false);
        return;
      }
      
      if (!formData.model_id) {
        setError('请选择模型');
        setLoading(false);
        return;
      }

      const result = await taskService.startTask(formData);
      setCurrentTaskId(result.task_id);
      setTaskStatus('running');
      setProgress([]);
      setTaskProgress(null);
      setSuccess('任务已启动');
      connectProgress(result.task_id);
      startProgressPolling(result.task_id);
    } catch (err: any) {
      setError(err.response?.data?.error || '启动任务失败');
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    if (!currentTaskId) return;
    if (!confirm('确定要停止当前任务吗？')) return;

    try {
      await taskService.stopTask(currentTaskId);
      setTaskStatus('idle');
      setCurrentTaskId(null);
      setTaskProgress(null);
      stopProgressPolling();
      setSuccess('任务已停止');
    } catch (err: any) {
      setError(err.response?.data?.error || '停止任务失败');
    }
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

      {/* Task Configuration Card */}
      <div className="bg-white rounded-2xl shadow-sm p-8">
        <h2 className="text-xl font-semibold text-gray-900 mb-6">任务配置</h2>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                选择模型 *
              </label>
              <select
                value={formData.model_id || ''}
                onChange={(e) => setFormData((prev) => ({ ...prev, model_id: parseInt(e.target.value) }))}
                className="w-full px-4 py-3 border border-gray-300 rounded-xl bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              >
                <option value="">请选择模型...</option>
                {models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name} {model.description && `- ${model.description}`}
                  </option>
                ))}
              </select>
              {models.length === 0 && (
                <p className="mt-2 text-sm text-red-600">暂无可用模型，请联系管理员配置</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                选择数据文件 *
              </label>
              <select
                value={formData.input_file}
                onChange={(e) => setFormData((prev) => ({ ...prev, input_file: e.target.value }))}
                className="w-full px-4 py-3 border border-gray-300 rounded-xl bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              >
                <option value="">请选择数据文件...</option>
                {dataFiles.map((file) => (
                  <option key={file.id} value={file.path}>
                    {file.name}
                  </option>
                ))}
              </select>
              {dataFiles.length === 0 && (
                <p className="mt-2 text-sm text-red-600">暂无数据文件，请先在"数据管理"中上传</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">任务类型</label>
              <select
                value={formData.task_type}
                onChange={(e) => setFormData((prev) => ({ ...prev, task_type: e.target.value }))}
                className="w-full px-4 py-3 border border-gray-300 rounded-xl bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {taskTypes.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">批处理大小</label>
              <input
                type="number"
                value={formData.batch_size}
                onChange={(e) => setFormData((prev) => ({ ...prev, batch_size: parseInt(e.target.value) }))}
                className="w-full px-4 py-3 border border-gray-300 rounded-xl bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                min="1"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">最大并发数</label>
              <input
                type="number"
                value={formData.max_concurrent}
                onChange={(e) => setFormData((prev) => ({ ...prev, max_concurrent: parseInt(e.target.value) }))}
                className="w-full px-4 py-3 border border-gray-300 rounded-xl bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                min="1"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">最低评分 (0-10)</label>
              <input
                type="number"
                value={formData.min_score}
                onChange={(e) => setFormData((prev) => ({ ...prev, min_score: parseInt(e.target.value) }))}
                className="w-full px-4 py-3 border border-gray-300 rounded-xl bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                min="0"
                max="10"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">每个样本的变体数量</label>
              <input
                type="number"
                value={formData.variants_per_sample}
                onChange={(e) => setFormData((prev) => ({ ...prev, variants_per_sample: parseInt(e.target.value) }))}
                className="w-full px-4 py-3 border border-gray-300 rounded-xl bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                min="1"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">数据使用轮次</label>
              <input
                type="number"
                value={formData.data_rounds}
                onChange={(e) => setFormData((prev) => ({ ...prev, data_rounds: parseInt(e.target.value) }))}
                className="w-full px-4 py-3 border border-gray-300 rounded-xl bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                min="1"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">重试次数</label>
              <input
                type="number"
                value={formData.retry_times}
                onChange={(e) => setFormData((prev) => ({ ...prev, retry_times: parseInt(e.target.value) }))}
                className="w-full px-4 py-3 border border-gray-300 rounded-xl bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                min="0"
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">特殊任务提示词</label>
              <textarea
                value={formData.special_prompt}
                onChange={(e) => setFormData((prev) => ({ ...prev, special_prompt: e.target.value }))}
                className="w-full px-4 py-3 border border-gray-300 rounded-xl bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                rows={3}
                placeholder="用于指导模型生成特定格式或内容的任务提示词"
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">题材方向</label>
              <input
                type="text"
                value={formData.directions}
                onChange={(e) => setFormData((prev) => ({ ...prev, directions: e.target.value }))}
                className="w-full px-4 py-3 border border-gray-300 rounded-xl bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="多个题材用空格分隔"
              />
            </div>
          </div>

          <div className="flex gap-4 pt-4">
            <button
              type="submit"
              disabled={loading || taskStatus === 'running' || models.length === 0 || dataFiles.length === 0}
              className="px-8 py-4 bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
            >
              {loading ? '启动中...' : '启动任务'}
            </button>
            {taskStatus === 'running' && (
              <button
                type="button"
                onClick={handleStop}
                className="px-8 py-4 bg-red-500 hover:bg-red-600 text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all duration-200"
              >
                停止任务
              </button>
            )}
          </div>
        </form>
      </div>

      {/* Progress Card */}
      <div className="bg-white rounded-2xl shadow-sm p-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">任务进度</h2>
          {taskStatus !== 'idle' && (
            <span
              className={`px-4 py-2 rounded-full text-sm font-medium ${
                taskStatus === 'running'
                  ? 'bg-green-100 text-green-700'
                  : taskStatus === 'finished'
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-red-100 text-red-700'
              }`}
            >
              {taskStatus === 'running' ? '运行中' : taskStatus === 'finished' ? '已完成' : '失败'}
            </span>
          )}
        </div>
        
        {/* 进度条 */}
        {taskStatus === 'running' && taskProgress && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">
                {taskProgress.status === 'running' ? (
                  <>轮次 {taskProgress.current_round}/{taskProgress.total_rounds}</>
                ) : taskProgress.status === 'completed' ? (
                  '已完成'
                ) : (
                  '处理中...'
                )}
              </span>
              <span className="text-sm font-medium text-gray-700">
                {taskProgress.progress_percent !== null && taskProgress.progress_percent !== undefined 
                  ? `${taskProgress.progress_percent.toFixed(1)}%` 
                  : '计算中...'}
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500 ease-out bg-gradient-to-r from-blue-500 to-indigo-600"
                style={{ 
                  width: `${taskProgress.progress_percent ?? 0}%`,
                  minWidth: taskProgress.progress_percent > 0 ? '2%' : '0%'
                }}
              />
            </div>
            <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
              <span>已生成 {taskProgress.generated_count} 条数据</span>
              {taskProgress.source === 'redis' && (
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                  实时更新
                </span>
              )}
            </div>
          </div>
        )}
        
        {/* 任务完成后的进度条显示 */}
        {(taskStatus === 'finished' || taskStatus === 'error') && taskProgress && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">
                {taskStatus === 'finished' ? '任务已完成' : '任务失败'}
              </span>
              <span className="text-sm font-medium text-gray-700">
                {taskStatus === 'finished' ? '100%' : `${taskProgress.progress_percent?.toFixed(1) ?? 0}%`}
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ease-out ${
                  taskStatus === 'finished' 
                    ? 'bg-gradient-to-r from-green-500 to-emerald-600' 
                    : 'bg-gradient-to-r from-red-500 to-rose-600'
                }`}
                style={{ width: taskStatus === 'finished' ? '100%' : `${taskProgress.progress_percent ?? 0}%` }}
              />
            </div>
            <div className="mt-2 text-xs text-gray-500">
              共生成 {taskProgress.generated_count} 条数据
            </div>
          </div>
        )}
        <div className="bg-gray-900 rounded-xl p-6 font-mono text-sm text-gray-300 max-h-96 overflow-y-auto">
          {progress.length === 0 ? (
            <div className="text-center text-gray-500 py-12">
              <div className="text-4xl mb-4">📋</div>
              <p>暂无任务运行，请配置参数后启动任务</p>
            </div>
          ) : (
            progress.map((line, index) => (
              <div
                key={index}
                className={`mb-1 ${
                  line.includes('ERROR') || line.includes('错误')
                    ? 'text-red-400'
                    : line.includes('SUCCESS') || line.includes('成功')
                    ? 'text-green-400'
                    : 'text-gray-300'
                }`}
              >
                {line}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
