import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { reportService } from '../services/api';
import type { GeneratedDataItem } from '../types';

// 可编辑数据项的类型
interface EditableDataItem {
  id: number;
  data: GeneratedDataItem;
  is_confirmed: boolean;
  created_at: string | null;
  updated_at: string | null;
  isEdited?: boolean;  // 本地编辑状态
}

// Turn 类型
interface Turn {
  role: string;
  text: string;
}

// Turn编辑组件
function TurnEditor({ 
  turn, 
  index, 
  onChange 
}: { 
  turn: Turn; 
  index: number; 
  onChange: (index: number, field: 'role' | 'text', value: string) => void;
}) {
  const roleColor = turn.role === 'Human' ? 'bg-blue-50 border-blue-200' : 'bg-green-50 border-green-200';
  const roleLabelColor = turn.role === 'Human' ? 'text-blue-700' : 'text-green-700';
  
  return (
    <div className={`border rounded-lg p-4 mb-3 ${roleColor}`}>
      <div className="flex items-center gap-3 mb-2">
        <span className={`text-sm font-medium ${roleLabelColor}`}>第 {index + 1} 轮</span>
        <select
          value={turn.role}
          onChange={(e) => onChange(index, 'role', e.target.value)}
          className="px-2 py-1 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500"
        >
          <option value="Human">Human</option>
          <option value="Assistant">Assistant</option>
          <option value="System">System</option>
        </select>
      </div>
      <textarea
        value={turn.text}
        onChange={(e) => onChange(index, 'text', e.target.value)}
        className="w-full p-3 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y"
        rows={4}
        placeholder={`${turn.role} 的内容...`}
      />
    </div>
  );
}

export default function DataEditorPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  
  const [dataItems, setDataItems] = useState<EditableDataItem[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // 当前选中的数据
  const currentItem = dataItems[selectedIndex];
  
  // 加载数据
  const loadData = useCallback(async () => {
    if (!taskId) return;
    
    try {
      setLoading(true);
      setError('');
      const data = await reportService.getReportDataEditable(decodeURIComponent(taskId));
      setDataItems(data.map(item => ({ ...item, isEdited: false })));
    } catch (err: any) {
      setError(err.message || '加载数据失败');
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // 更新 meta_description
  const handleMetaDescriptionChange = (value: string) => {
    if (!currentItem) return;
    
    setDataItems(prev => prev.map((item, idx) => {
      if (idx === selectedIndex) {
        const newData = { ...item.data };
        if (!newData.meta) newData.meta = {};
        newData.meta.meta_description = value;
        return { ...item, data: newData, isEdited: true };
      }
      return item;
    }));
  };

  // 更新 turns
  const handleTurnChange = (turnIndex: number, field: 'role' | 'text', value: string) => {
    if (!currentItem) return;
    
    setDataItems(prev => prev.map((item, idx) => {
      if (idx === selectedIndex) {
        const newData = { ...item.data };
        if (!newData.turns) newData.turns = [];
        newData.turns = [...newData.turns];
        if (newData.turns[turnIndex]) {
          newData.turns[turnIndex] = { ...newData.turns[turnIndex], [field]: value };
        }
        return { ...item, data: newData, isEdited: true };
      }
      return item;
    }));
  };

  // 添加新的 turn
  const handleAddTurn = () => {
    if (!currentItem) return;
    
    setDataItems(prev => prev.map((item, idx) => {
      if (idx === selectedIndex) {
        const newData = { ...item.data };
        if (!newData.turns) newData.turns = [];
        const lastRole = newData.turns.length > 0 ? newData.turns[newData.turns.length - 1].role : 'Human';
        const newRole = lastRole === 'Human' ? 'Assistant' : 'Human';
        newData.turns = [...newData.turns, { role: newRole, text: '' }];
        return { ...item, data: newData, isEdited: true };
      }
      return item;
    }));
  };

  // 删除 turn
  const handleRemoveTurn = (turnIndex: number) => {
    if (!currentItem) return;
    
    setDataItems(prev => prev.map((item, idx) => {
      if (idx === selectedIndex) {
        const newData = { ...item.data };
        if (newData.turns && newData.turns.length > 1) {
          newData.turns = newData.turns.filter((_: Turn, i: number) => i !== turnIndex);
          return { ...item, data: newData, isEdited: true };
        }
        return item;
      }
      return item;
    }));
  };

  // 保存修改
  const handleSave = async () => {
    if (!currentItem) return;
    
    try {
      setSaving(true);
      setError('');
      await reportService.updateGeneratedData(currentItem.id, currentItem.data);
      
      // 更新本地状态
      setDataItems(prev => prev.map((item, idx) => {
        if (idx === selectedIndex) {
          return { ...item, isEdited: false };
        }
        return item;
      }));
      
      setSuccess('保存成功');
      setTimeout(() => setSuccess(''), 2000);
    } catch (err: any) {
      setError(err.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  // 确认可用
  const handleConfirm = async () => {
    if (!currentItem) return;
    
    try {
      setSaving(true);
      setError('');
      
      // 如果有编辑，先保存
      if (currentItem.isEdited) {
        await reportService.updateGeneratedData(currentItem.id, currentItem.data);
      }
      
      // 切换确认状态
      const newConfirmState = !currentItem.is_confirmed;
      await reportService.confirmGeneratedData(currentItem.id, newConfirmState);
      
      // 更新本地状态
      setDataItems(prev => prev.map((item, idx) => {
        if (idx === selectedIndex) {
          return { ...item, is_confirmed: newConfirmState, isEdited: false };
        }
        return item;
      }));
      
      setSuccess(newConfirmState ? '已确认可用' : '已取消确认');
      setTimeout(() => setSuccess(''), 2000);
    } catch (err: any) {
      setError(err.message || '操作失败');
    } finally {
      setSaving(false);
    }
  };

  // 上一条
  const handlePrevious = () => {
    if (selectedIndex > 0) {
      setSelectedIndex(selectedIndex - 1);
    }
  };

  // 下一条
  const handleNext = () => {
    if (selectedIndex < dataItems.length - 1) {
      setSelectedIndex(selectedIndex + 1);
    }
  };

  // 返回
  const handleBack = () => {
    navigate('/');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">加载数据中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">
      {/* 顶部导航栏 */}
      <header className="bg-white shadow-sm">
        <div className="px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={handleBack}
              className="flex items-center gap-2 text-gray-600 hover:text-gray-900"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              返回
            </button>
            <h1 className="text-xl font-semibold text-gray-900">
              数据编辑器
            </h1>
          </div>
          <div className="text-sm text-gray-500">
            任务: {taskId ? decodeURIComponent(taskId) : '-'}
          </div>
        </div>
      </header>

      {/* 错误/成功提示 */}
      {error && (
        <div className="mx-6 mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="mx-6 mt-4 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
          {success}
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        {/* 左侧数据列表 */}
        <aside className="w-64 bg-white border-r border-gray-200 overflow-y-auto">
          <div className="p-4 border-b border-gray-200">
            <h2 className="text-sm font-medium text-gray-700">
              数据列表 ({dataItems.length} 条)
            </h2>
            <p className="text-xs text-gray-500 mt-1">
              已确认: {dataItems.filter(d => d.is_confirmed).length} 条
            </p>
          </div>
          <div className="divide-y divide-gray-100">
            {dataItems.map((item, index) => (
              <button
                key={item.id}
                onClick={() => setSelectedIndex(index)}
                className={`w-full px-4 py-3 text-left transition-colors ${
                  index === selectedIndex
                    ? 'bg-blue-50 border-l-4 border-l-blue-600'
                    : 'hover:bg-gray-50 border-l-4 border-l-transparent'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700">
                    #{index + 1}
                  </span>
                  <div className="flex items-center gap-1">
                    {item.isEdited && (
                      <span className="px-2 py-0.5 text-xs bg-yellow-100 text-yellow-700 rounded">
                        已编辑
                      </span>
                    )}
                    {item.is_confirmed && (
                      <span className="w-3 h-3 bg-green-500 rounded-full" title="已确认" />
                    )}
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-1 truncate">
                  {item.data.turns?.[0]?.text?.slice(0, 30) || '无内容'}...
                </p>
              </button>
            ))}
          </div>
        </aside>

        {/* 中央编辑区 */}
        <main className="flex-1 overflow-y-auto p-6">
          {currentItem ? (
            <div className="max-w-4xl mx-auto">
              {/* Meta Description */}
              <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
                <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center gap-2">
                  <span>📋</span>
                  Meta Description
                </h3>
                <textarea
                  value={currentItem.data.meta?.meta_description || ''}
                  onChange={(e) => handleMetaDescriptionChange(e.target.value)}
                  className="w-full p-4 border border-gray-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y"
                  rows={8}
                  placeholder="输入 meta_description..."
                />
              </div>

              {/* Turns */}
              <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-medium text-gray-900 flex items-center gap-2">
                    <span>💬</span>
                    对话轮次 ({currentItem.data.turns?.length || 0} 轮)
                  </h3>
                  <button
                    onClick={handleAddTurn}
                    className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    + 添加轮次
                  </button>
                </div>
                
                {currentItem.data.turns?.map((turn: Turn, index: number) => (
                  <div key={index} className="relative">
                    <TurnEditor
                      turn={turn}
                      index={index}
                      onChange={handleTurnChange}
                    />
                    {(currentItem.data.turns?.length || 0) > 1 && (
                      <button
                        onClick={() => handleRemoveTurn(index)}
                        className="absolute top-2 right-2 p-1 text-red-500 hover:text-red-700 hover:bg-red-50 rounded"
                        title="删除此轮"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    )}
                  </div>
                ))}
              </div>

              {/* 其他 Meta 信息 */}
              <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
                <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center gap-2">
                  <span>ℹ️</span>
                  其他信息
                </h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">模型评分:</span>
                    <span className="ml-2 text-gray-900">{currentItem.data.meta?.model_score ?? '-'}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">规则评分:</span>
                    <span className="ml-2 text-gray-900">{currentItem.data.meta?.rule_score ?? '-'}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">生成模型:</span>
                    <span className="ml-2 text-gray-900">{currentItem.data.meta?.generation_model || '-'}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">生成时间:</span>
                    <span className="ml-2 text-gray-900">
                      {currentItem.data.meta?.generation_time 
                        ? new Date(currentItem.data.meta.generation_time).toLocaleString('zh-CN')
                        : '-'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              暂无数据
            </div>
          )}
        </main>
      </div>

      {/* 底部操作栏 */}
      {currentItem && (
        <footer className="bg-white border-t border-gray-200 px-6 py-4">
          <div className="max-w-4xl mx-auto flex items-center justify-between">
            {/* 导航按钮 */}
            <div className="flex items-center gap-2">
              <button
                onClick={handlePrevious}
                disabled={selectedIndex === 0}
                className="px-4 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                ← 上一条
              </button>
              <span className="text-sm text-gray-500 px-4">
                {selectedIndex + 1} / {dataItems.length}
              </span>
              <button
                onClick={handleNext}
                disabled={selectedIndex === dataItems.length - 1}
                className="px-4 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                下一条 →
              </button>
            </div>

            {/* 状态指示 */}
            <div className="flex items-center gap-2">
              {currentItem.isEdited && (
                <span className="px-3 py-1 text-sm bg-yellow-100 text-yellow-700 rounded-full">
                  未保存的修改
                </span>
              )}
              {currentItem.is_confirmed && (
                <span className="px-3 py-1 text-sm bg-green-100 text-green-700 rounded-full">
                  ✓ 已确认可用
                </span>
              )}
            </div>

            {/* 操作按钮 */}
            <div className="flex items-center gap-3">
              <button
                onClick={handleSave}
                disabled={saving || !currentItem.isEdited}
                className="px-6 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {saving ? '保存中...' : '保存修改'}
              </button>
              <button
                onClick={handleConfirm}
                disabled={saving}
                className={`px-6 py-2 text-sm rounded-lg transition-colors ${
                  currentItem.is_confirmed
                    ? 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                    : 'bg-green-600 text-white hover:bg-green-700'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {saving ? '处理中...' : (currentItem.is_confirmed ? '取消确认' : '确认可用')}
              </button>
            </div>
          </div>
        </footer>
      )}
    </div>
  );
}
