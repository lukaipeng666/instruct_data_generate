import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { reportService } from '../services/api';
import type { GeneratedDataItem } from '../types';
import ConfirmDialog from '../components/ConfirmDialog';

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

// 验证 Human 和 Assistant 数量是否一致
function validateTurnsBalance(turns: Turn[]): { isValid: boolean; message: string } {
  if (!turns || turns.length === 0) {
    return { isValid: true, message: '' };
  }
  
  const humanCount = turns.filter(t => t.role === 'Human').length;
  const assistantCount = turns.filter(t => t.role === 'Assistant').length;
  
  if (humanCount !== assistantCount) {
    return {
      isValid: false,
      message: `Human 和 Assistant 数量不一致（Human: ${humanCount}, Assistant: ${assistantCount}），请保证对话轮次成对出现`
    };
  }
  
  return { isValid: true, message: '' };
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
  
  // 批量删除相关状态
  const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set());
  const [rangeStart, setRangeStart] = useState('');
  const [rangeEnd, setRangeEnd] = useState('');
  const [deleting, setDeleting] = useState(false);
  
  // 添加数据相关状态
  const [showAddModal, setShowAddModal] = useState(false);
  const [newItemData, setNewItemData] = useState<{ meta: { meta_description: string }; turns: Turn[] }>({
    meta: { meta_description: '' },
    turns: [{ role: 'Human', text: '' }, { role: 'Assistant', text: '' }]
  });
  const [adding, setAdding] = useState(false);
  
  // 确认弹窗状态
  const [deleteConfirm, setDeleteConfirm] = useState<{ isOpen: boolean; indices: number[] | null; message: string }>({
    isOpen: false,
    indices: null,
    message: '',
  });

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
      setSelectedItems(new Set());  // 清空选中
      setSelectedIndex(0);  // 重置选中索引
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
    
    // 验证 Human 和 Assistant 数量是否一致
    const validation = validateTurnsBalance(currentItem.data.turns || []);
    if (!validation.isValid) {
      setError(validation.message);
      return;
    }
    
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

  // 切换选中项
  const toggleSelectItem = (index: number) => {
    setSelectedItems(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  // 全选/取消全选
  const toggleSelectAll = () => {
    if (selectedItems.size === dataItems.length) {
      setSelectedItems(new Set());
    } else {
      setSelectedItems(new Set(dataItems.map((_, i) => i)));
    }
  };

  // 批量删除选中的数据
  const handleBatchDelete = async (indicesToDelete: number[]) => {
    if (indicesToDelete.length === 0) return;
    
    if (indicesToDelete.length >= dataItems.length) {
      setError('不能删除所有数据，至少需要保留一条数据');
      return;
    }
    
    // 获取要删除的数据 ID
    const dataIdsToDelete = indicesToDelete.map(i => dataItems[i].id);
    
    try {
      setDeleting(true);
      setError('');
      const result = await reportService.batchDeleteGeneratedData(dataIdsToDelete);
      setSuccess(`成功删除 ${result.deleted_count} 条数据`);
      setSelectedItems(new Set());
      setRangeStart('');
      setRangeEnd('');
      await loadData();  // 重新加载数据
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '删除失败');
    } finally {
      setDeleting(false);
    }
  };

  // 删除选中的数据
  const handleDeleteSelected = () => {
    if (selectedItems.size === 0) {
      setError('请先选择要删除的数据');
      return;
    }
    setDeleteConfirm({
      isOpen: true,
      indices: Array.from(selectedItems),
      message: `确定要删除选中的 ${selectedItems.size} 条数据吗？`
    });
  };

  // 按范围删除
  const handleDeleteByRange = () => {
    const start = parseInt(rangeStart);
    const end = parseInt(rangeEnd);
    
    if (isNaN(start) || isNaN(end)) {
      setError('请输入有效的起始和结束索引');
      return;
    }
    
    if (start < 1 || end < 1) {
      setError('索引必须大于 0');
      return;
    }
    
    if (start > end) {
      setError('起始索引不能大于结束索引');
      return;
    }
    
    if (end > dataItems.length) {
      setError(`结束索引超出范围，最大为 ${dataItems.length}`);
      return;
    }
    
    // 生成要删除的索引列表（转换为 0-based）
    const indices: number[] = [];
    for (let i = start - 1; i < end; i++) {
      indices.push(i);
    }
    
    setDeleteConfirm({
      isOpen: true,
      indices,
      message: `确定要删除第 ${start} 到第 ${end} 条数据吗？共 ${indices.length} 条`
    });
  };

  // 确认删除
  const confirmDelete = async () => {
    const { indices } = deleteConfirm;
    if (!indices) return;
    
    setDeleteConfirm({ isOpen: false, indices: null, message: '' });
    handleBatchDelete(indices);
  };

  // 添加新数据
  const handleAddNewItem = async () => {
    if (!taskId) return;
    
    // 验证 Human 和 Assistant 数量是否一致
    const validation = validateTurnsBalance(newItemData.turns);
    if (!validation.isValid) {
      setError(validation.message);
      return;
    }
    
    try {
      setAdding(true);
      setError('');
      await reportService.addGeneratedData(decodeURIComponent(taskId), newItemData);
      setSuccess('数据添加成功');
      setShowAddModal(false);
      // 重置表单
      setNewItemData({
        meta: { meta_description: '' },
        turns: [{ role: 'Human', text: '' }, { role: 'Assistant', text: '' }]
      });
      await loadData();
      // 跳转到最后一条
      setSelectedIndex(dataItems.length);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '添加失败');
    } finally {
      setAdding(false);
    }
  };

  // 更新新数据的 meta
  const handleNewItemMetaChange = (value: string) => {
    setNewItemData(prev => ({
      ...prev,
      meta: { ...prev.meta, meta_description: value }
    }));
  };

  // 更新新数据的 turn
  const handleNewItemTurnChange = (turnIndex: number, field: 'role' | 'text', value: string) => {
    setNewItemData(prev => {
      const newTurns = [...prev.turns];
      newTurns[turnIndex] = { ...newTurns[turnIndex], [field]: value };
      return { ...prev, turns: newTurns };
    });
  };

  // 添加新数据的 turn
  const handleNewItemAddTurn = () => {
    setNewItemData(prev => {
      const lastRole = prev.turns.length > 0 ? prev.turns[prev.turns.length - 1].role : 'Human';
      const newRole = lastRole === 'Human' ? 'Assistant' : 'Human';
      return { ...prev, turns: [...prev.turns, { role: newRole, text: '' }] };
    });
  };

  // 删除新数据的 turn
  const handleNewItemRemoveTurn = (turnIndex: number) => {
    if (newItemData.turns.length <= 1) return;
    setNewItemData(prev => ({
      ...prev,
      turns: prev.turns.filter((_, i) => i !== turnIndex)
    }));
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
    <div className="h-screen bg-gray-100 flex flex-col overflow-hidden">
      {/* 顶部导航栏 */}
      <header className="bg-white shadow-sm flex-shrink-0">
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

      {/* 浮动提示框 */}
      {(error || success) && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50 cursor-pointer"
          onClick={() => { setError(''); setSuccess(''); }}
        >
          <div 
            className={`px-8 py-6 rounded-xl shadow-2xl max-w-md text-center ${
              error ? 'bg-red-50 border-2 border-red-200' : 'bg-green-50 border-2 border-green-200'
            }`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={`text-4xl mb-3 ${error ? 'text-red-500' : 'text-green-500'}`}>
              {error ? '❌' : '✅'}
            </div>
            <p className={`text-lg font-medium ${error ? 'text-red-700' : 'text-green-700'}`}>
              {error || success}
            </p>
            <p className="text-sm text-gray-500 mt-3">点击任意位置关闭</p>
          </div>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        {/* 左侧数据列表 */}
        <aside className="w-72 bg-white border-r border-gray-200 flex flex-col overflow-hidden">
          {/* 标题和统计 */}
          <div className="p-4 border-b border-gray-200 flex-shrink-0">
            <h2 className="text-sm font-medium text-gray-700">
              数据列表 ({dataItems.length} 条)
            </h2>
            <p className="text-xs text-gray-500 mt-1">
              已确认: {dataItems.filter(d => d.is_confirmed).length} 条
              {selectedItems.size > 0 && <span className="text-blue-600 ml-2">已选中 {selectedItems.size} 条</span>}
            </p>
          </div>
          
          {/* 批量删除控件 */}
          <div className="p-3 border-b border-gray-200 space-y-2 flex-shrink-0">
            {/* 添加数据按钮 */}
            <button
              onClick={() => setShowAddModal(true)}
              className="w-full px-2 py-1.5 text-xs bg-green-500 hover:bg-green-600 text-white rounded transition-colors flex items-center justify-center gap-1"
            >
              <span>+</span> 添加新数据
            </button>
            
            {/* 全选和删除选中 */}
            <div className="flex items-center gap-2">
              <button
                onClick={toggleSelectAll}
                className="flex-1 px-2 py-1.5 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors"
              >
                {selectedItems.size === dataItems.length ? '取消全选' : '全选'}
              </button>
              <button
                onClick={handleDeleteSelected}
                disabled={selectedItems.size === 0 || deleting}
                className="flex-1 px-2 py-1.5 text-xs bg-red-500 hover:bg-red-600 disabled:bg-gray-300 text-white rounded transition-colors"
              >
                删除选中 ({selectedItems.size})
              </button>
            </div>
            
            {/* 范围删除 */}
            <div className="flex items-center gap-1">
              <input
                type="number"
                min="1"
                max={dataItems.length}
                value={rangeStart}
                onChange={(e) => setRangeStart(e.target.value)}
                placeholder="起始"
                className="w-16 px-2 py-1.5 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 focus:border-blue-500 text-center"
              />
              <span className="text-gray-400 text-xs">-</span>
              <input
                type="number"
                min="1"
                max={dataItems.length}
                value={rangeEnd}
                onChange={(e) => setRangeEnd(e.target.value)}
                placeholder="结束"
                className="w-16 px-2 py-1.5 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 focus:border-blue-500 text-center"
              />
              <button
                onClick={handleDeleteByRange}
                disabled={!rangeStart || !rangeEnd || deleting}
                className="flex-1 px-2 py-1.5 text-xs bg-red-500 hover:bg-red-600 disabled:bg-gray-300 text-white rounded transition-colors whitespace-nowrap"
              >
                删除范围
              </button>
            </div>
          </div>
          
          {/* 数据列表 - 可滚动 */}
          <div className="flex-1 overflow-y-auto divide-y divide-gray-100">
            {dataItems.map((item, index) => (
              <div
                key={item.id}
                className={`flex items-center transition-colors ${
                  index === selectedIndex
                    ? 'bg-blue-50 border-l-4 border-l-blue-600'
                    : 'hover:bg-gray-50 border-l-4 border-l-transparent'
                }`}
              >
                {/* 复选框 */}
                <div className="pl-2">
                  <input
                    type="checkbox"
                    checked={selectedItems.has(index)}
                    onChange={() => toggleSelectItem(index)}
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                  />
                </div>
                {/* 数据项 */}
                <button
                  onClick={() => setSelectedIndex(index)}
                  className="flex-1 px-3 py-3 text-left"
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
                    {item.data.turns?.[0]?.text?.slice(0, 25) || '无内容'}...
                  </p>
                </button>
              </div>
            ))}
          </div>
        </aside>

        {/* 添加数据弹窗 */}
        {showAddModal && (
          <div 
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
            onClick={() => setShowAddModal(false)}
          >
            <div 
              className="bg-white rounded-xl shadow-2xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              {/* 弹窗标题 */}
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                <h2 className="text-xl font-semibold text-gray-900">添加新数据</h2>
                <button
                  onClick={() => setShowAddModal(false)}
                  className="p-1 text-gray-500 hover:text-gray-700 rounded"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              
              {/* 弹窗内容 */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* Meta Description */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">📋 Meta Description</h3>
                  <textarea
                    value={newItemData.meta.meta_description}
                    onChange={(e) => handleNewItemMetaChange(e.target.value)}
                    className="w-full p-3 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y"
                    rows={4}
                    placeholder="输入 meta_description..."
                  />
                </div>
                
                {/* Turns */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-medium text-gray-700">💬 对话轮次</h3>
                    <button
                      onClick={handleNewItemAddTurn}
                      className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                    >
                      + 添加轮次
                    </button>
                  </div>
                  
                  {newItemData.turns.map((turn, index) => (
                    <div key={index} className={`border rounded-lg p-3 mb-2 ${turn.role === 'Human' ? 'bg-blue-50 border-blue-200' : 'bg-green-50 border-green-200'}`}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className={`text-xs font-medium ${turn.role === 'Human' ? 'text-blue-700' : 'text-green-700'}`}>第 {index + 1} 轮</span>
                          <select
                            value={turn.role}
                            onChange={(e) => handleNewItemTurnChange(index, 'role', e.target.value)}
                            className="px-2 py-0.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-blue-500"
                          >
                            <option value="Human">Human</option>
                            <option value="Assistant">Assistant</option>
                            <option value="System">System</option>
                          </select>
                        </div>
                        {newItemData.turns.length > 1 && (
                          <button
                            onClick={() => handleNewItemRemoveTurn(index)}
                            className="p-0.5 text-red-500 hover:text-red-700 rounded"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        )}
                      </div>
                      <textarea
                        value={turn.text}
                        onChange={(e) => handleNewItemTurnChange(index, 'text', e.target.value)}
                        className="w-full p-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y"
                        rows={3}
                        placeholder={`${turn.role} 的内容...`}
                      />
                    </div>
                  ))}
                </div>
              </div>
              
              {/* 弹窗操作栏 */}
              <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
                <button
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handleAddNewItem}
                  disabled={adding}
                  className="px-4 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {adding ? '添加中...' : '确认添加'}
                </button>
              </div>
            </div>
          </div>
        )}

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

      {/* 删除确认弹窗 */}
      <ConfirmDialog
        isOpen={deleteConfirm.isOpen}
        title="删除数据"
        message={deleteConfirm.message}
        type="danger"
        confirmText="删除"
        cancelText="取消"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteConfirm({ isOpen: false, indices: null, message: '' })}
      />
    </div>
  );
}
