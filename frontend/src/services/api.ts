import axios from 'axios';
import type { LoginResponse, User, TaskParams, Task, AdminUser, ModelConfig, AdminTask, DataFile, Report, GeneratedDataItem } from '../types';

interface UserReportsResponse {
  success: boolean;
  user: { id: number; username: string };
  reports: Report[];
}

const api = axios.create({
  baseURL: '/api',
});

// 请求拦截器：添加token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器：处理401错误
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('username');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authService = {
  login: async (username: string, password: string): Promise<LoginResponse> => {
    const response = await api.post<{ code: number; message: string; data: { access_token: string; token_type: string; user: { username: string; is_admin: boolean } } }>('/login', { username, password });
    const { access_token, token_type, user } = response.data.data;
    return {
      access_token,
      token_type,
      username: user.username,
      is_admin: user.is_admin
    };
  },

  register: async (username: string, password: string): Promise<LoginResponse> => {
    const response = await api.post<{ code: number; message: string; data: { access_token: string; token_type: string; user: { username: string; is_admin: boolean } } }>('/register', { username, password });
    const { access_token, token_type, user } = response.data.data;
    return {
      access_token,
      token_type,
      username: user.username,
      is_admin: user.is_admin
    };
  },
  
  getMe: async (): Promise<User> => {
    const response = await api.get<{ code: number; message: string; data: User }>('/me');
    return response.data.data;
  },
  
  logout: async (): Promise<void> => {
    await api.post('/logout');
  },
};

export const taskService = {
  getTaskTypes: async (): Promise<string[]> => {
    const response = await api.get<{ code: number; message: string; data: { success: boolean; types: string[] } }>('/task_types');
    return response.data.data.types;
  },

  // 获取激活的模型列表（普通用户）
  getActiveModels: async (): Promise<ModelConfig[]> => {
    const response = await api.get<{ code: number; message: string; data: { success: boolean; models: ModelConfig[]; total: number } }>('/models');
    return response.data.data.models;
  },

  startTask: async (params: TaskParams): Promise<{ success: boolean; task_id: string }> => {
    const response = await api.post<{ code: number; message: string; data: { success: boolean; task_id: string } }>('/start', params);
    return response.data.data;
  },

  stopTask: async (taskId: string): Promise<void> => {
    await api.post(`/stop/${taskId}`);
  },

  getActiveTask: async (): Promise<{ success: boolean; task_id?: string; params?: TaskParams }> => {
    const response = await api.get<{ code: number; message: string; data: { success: boolean; task_id?: string; params?: TaskParams } }>('/active_task');
    return response.data.data;
  },

  getAllTasks: async (): Promise<Task[]> => {
    const response = await api.get<{ code: number; message: string; data: Task[] }>('/tasks');
    return response.data.data;
  },

  // 获取任务进度（从Redis）
  getTaskProgress: async (taskId: string): Promise<{
    success: boolean;
    progress?: {
      task_id: string;
      status: string;
      current_round: number;
      total_rounds: number;
      generated_count: number;
      progress_percent: number;
      completion_percent?: number;
      source: string;
    };
    error?: string;
  }> => {
    const encodedTaskId = encodeURIComponent(taskId);
    const response = await api.get<{ code: number; message: string; data: { success: boolean; progress?: any } }>(`/progress_unified/${encodedTaskId}`);
    return response.data.data;
  },
};

// 数据管理服务
export const dataService = {
  // 获取数据文件列表
  getDataFiles: async (): Promise<DataFile[]> => {
    const response = await api.get<{ code: number; message: string; data: DataFile[] }>('/data_files');
    return response.data.data;
  },

  // 上传数据文件
  uploadDataFile: async (file: File): Promise<DataFile> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<{ code: number; message: string; data: DataFile }>('/data_files/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data.data;
  },

  // 删除数据文件
  deleteDataFile: async (fileId: number): Promise<void> => {
    await api.delete(`/data_files/${fileId}`);
  },

  // 批量删除数据文件
  batchDeleteDataFiles: async (fileIds: number[]): Promise<{ deleted_count: number; errors: string[] }> => {
    const response = await api.post<{ code: number; message: string; data: { deleted_count: number; errors: string[] } }>('/data_files/batch_delete', { file_ids: fileIds });
    return response.data.data;
  },

  // 获取文件内容
  getDataFileContent: async (fileId: number): Promise<{ filename: string; total_lines: number; data: any[] }> => {
    const response = await api.get<{ code: number; message: string; data: { file_id: number; filename: string; total_lines: number; data: any[] } }>(`/data_files/${fileId}/content`);
    const data = response.data.data;
    return {
      filename: data.filename,
      total_lines: data.total_lines,
      data: data.data,
    };
  },

  // 获取文件内容（带索引，用于编辑）
  getDataFileContentEditable: async (fileId: number): Promise<{ filename: string; total_lines: number; items: { index: number; data: any }[] }> => {
    const response = await api.get<{ code: number; message: string; data: { file_id: number; filename: string; total_lines: number; items: { index: number; data: any }[] } }>(`/data_files/${fileId}/content/editable`);
    const data = response.data.data;
    return {
      filename: data.filename,
      total_lines: data.total_lines,
      items: data.items,
    };
  },

  // 下载文件
  downloadDataFile: async (fileId: number): Promise<void> => {
    const encodedFileId = encodeURIComponent(fileId.toString());
    try {
      const response = await api.get(`/data_files/${encodedFileId}/download`, {
        responseType: 'blob',
      });
      
      // 检查响应是否是错误的 JSON
      const contentType = response.headers['content-type'];
      if (contentType && contentType.includes('application/json')) {
        const text = await response.data.text();
        const errorData = JSON.parse(text);
        throw new Error(errorData.detail || '下载失败');
      }
      
      // 从 Content-Disposition 头中提取文件名
      let filename = `data_file_${fileId}.jsonl`; // 默认文件名
      const contentDisposition = response.headers['content-disposition'];
      if (contentDisposition) {
        // 尝试解析 filename*=UTF-8''xxx 格式
        const filenameStarMatch = contentDisposition.match(/filename\*=UTF-8''(.+)/i);
        if (filenameStarMatch && filenameStarMatch[1]) {
          filename = decodeURIComponent(filenameStarMatch[1]);
        } else {
          // 尝试解析 filename="xxx" 格式
          const filenameMatch = contentDisposition.match(/filename="?([^";\n]+)"?/i);
          if (filenameMatch && filenameMatch[1]) {
            filename = filenameMatch[1];
          }
        }
      }
      
      // 创建下载链接
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error: any) {
      if (error.response) {
        let errorMessage = `下载失败: HTTP ${error.response.status}`;
        
        if (error.response.data instanceof Blob) {
          try {
            const text = await error.response.data.text();
            const errorData = JSON.parse(text);
            if (errorData.detail) {
              errorMessage = errorData.detail;
            }
          } catch {
            // 无法解析 blob
          }
        } else if (error.response.data?.detail) {
          errorMessage = error.response.data.detail;
        }
        
        throw new Error(errorMessage);
      }
      
      throw new Error(error.message || '下载失败: 未知错误');
    }
  },

  // 批量下载文件（打包成zip）
  batchDownloadDataFiles: async (fileIds: number[]): Promise<void> => {
    if (fileIds.length === 0) return;
    
    try {
      const response = await api.post('/data_files/batch_download', { file_ids: fileIds }, {
        responseType: 'blob',
      });
      
      // 检查响应类型
      const contentType = response.headers['content-type'];
      if (contentType && contentType.includes('application/json')) {
        const text = await response.data.text();
        const errorData = JSON.parse(text);
        throw new Error(errorData.detail || '批量下载失败');
      }
      
      // 创建下载链接（zip文件）
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `data_files_${fileIds.length}.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error: any) {
      if (error.response) {
        let errorMessage = `批量下载失败: HTTP ${error.response.status}`;
        
        if (error.response.data instanceof Blob) {
          try {
            const text = await error.response.data.text();
            const errorData = JSON.parse(text);
            if (errorData.detail) {
              errorMessage = errorData.detail;
            }
          } catch {
            // 无法解析 blob
          }
        } else if (error.response.data?.detail) {
          errorMessage = error.response.data.detail;
        }
        
        throw new Error(errorMessage);
      }
      
      throw new Error(error.message || '批量下载失败: 未知错误');
    }
  },

  // 批量转换文件格式（CSV<->JSONL）并下载
  batchConvertDataFiles: async (fileIds: number[]): Promise<void> => {
    if (fileIds.length === 0) return;

    try {
      const response = await api.post('/data_files/batch_convert', { file_ids: fileIds }, {
        responseType: 'blob',
      });

      // 检查响应类型
      const contentType = response.headers['content-type'];
      if (contentType && contentType.includes('application/json')) {
        const text = await response.data.text();
        const errorData = JSON.parse(text);
        throw new Error(errorData.detail || '批量转换失败');
      }

      // 创建下载链接（zip文件）
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `converted_files_${fileIds.length}.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error: any) {
      if (error.response) {
        let errorMessage = `批量转换失败: HTTP ${error.response.status}`;

        if (error.response.data instanceof Blob) {
          try {
            const text = await error.response.data.text();
            const errorData = JSON.parse(text);
            if (errorData.detail) {
              errorMessage = errorData.detail;
            }
          } catch {
            // 无法解析 blob
          }
        } else if (error.response.data?.detail) {
          errorMessage = error.response.data.detail;
        }

        throw new Error(errorMessage);
      }

      throw new Error(error.message || '批量转换失败: 未知错误');
    }
  },

  // 直接上传文件并转换格式（不保存到数据库）
  convertFilesDirect: async (files: File[]): Promise<void> => {
    if (files.length === 0) return;

    try {
      const formData = new FormData();
      files.forEach(file => {
        formData.append('files', file);
      });

      const response = await api.post('/convert_files', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        responseType: 'blob',
      });

      // 检查响应类型
      const contentType = response.headers['content-type'];
      if (contentType && contentType.includes('application/json')) {
        const text = await response.data.text();
        const errorData = JSON.parse(text);
        throw new Error(errorData.detail || '文件转换失败');
      }

      // 从 Content-Disposition 头中提取文件名
      let filename = '';
      const contentDisposition = response.headers['content-disposition'];
      if (contentDisposition) {
        // 尝试解析 filename*=UTF-8''xxx 格式
        const filenameStarMatch = contentDisposition.match(/filename\*=UTF-8''(.+)/i);
        if (filenameStarMatch && filenameStarMatch[1]) {
          filename = decodeURIComponent(filenameStarMatch[1]);
        } else {
          // 尝试解析 filename="xxx" 格式
          const filenameMatch = contentDisposition.match(/filename="?([^";\n]+)"?/i);
          if (filenameMatch && filenameMatch[1]) {
            filename = filenameMatch[1];
          }
        }
      }

      // 如果没有提取到文件名，使用默认名称
      if (!filename) {
        if (files.length === 1) {
          // 单个文件：根据原文件名生成
          const originalName = files[0].name;
          if (originalName.endsWith('.csv')) {
            filename = originalName.slice(0, -4) + '.jsonl';
          } else if (originalName.endsWith('.jsonl')) {
            filename = originalName.slice(0, -6) + '.csv';
          } else {
            filename = 'converted_file';
          }
        } else {
          // 多个文件：使用默认ZIP名称
          filename = 'converted_files.zip';
        }
      }

      // 创建下载链接
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error: any) {
      if (error.response) {
        let errorMessage = `文件转换失败: HTTP ${error.response.status}`;

        if (error.response.data instanceof Blob) {
          try {
            const text = await error.response.data.text();
            const errorData = JSON.parse(text);
            if (errorData.detail) {
              errorMessage = errorData.detail;
            }
          } catch {
            // 无法解析 blob
          }
        } else if (error.response.data?.detail) {
          errorMessage = error.response.data.detail;
        }

        throw new Error(errorMessage);
      }

      throw new Error(error.message || '文件转换失败: 未知错误');
    }
  },
  
  // 更新文件中的单条数据
  updateDataFileItem: async (fileId: number, itemIndex: number, content: any): Promise<void> => {
    await api.put(`/data_files/${fileId}/content/${itemIndex}`, { content });
  },
  
  // 批量删除文件中的数据
  batchDeleteDataFileItems: async (fileId: number, indices: number[]): Promise<{ deleted_count: number; remaining_count: number }> => {
    const response = await api.delete<{ success: boolean; deleted_count: number; remaining_count: number; message: string }>(`/data_files/${fileId}/content/batch`, {
      data: { indices }
    });
    return {
      deleted_count: response.data.deleted_count,
      remaining_count: response.data.remaining_count
    };
  },
  
  // 添加新数据到文件
  addDataFileItem: async (fileId: number, content: any): Promise<{ new_index: number; total_count: number }> => {
    const response = await api.post<{ success: boolean; new_index: number; total_count: number; message: string }>(`/data_files/${fileId}/content`, { content });
    return {
      new_index: response.data.new_index,
      total_count: response.data.total_count
    };
  },
};

// 管理员服务
export const adminService = {
  // 用户管理
  getAllUsers: async (): Promise<AdminUser[]> => {
    const response = await api.get<{ code: number; message: string; data: AdminUser[] }>('/admin/users');
    return response.data.data;
  },

  deleteUser: async (userId: number): Promise<void> => {
    await api.delete(`/admin/users/${userId}`);
  },

  // 模型管理
  getAllModels: async (): Promise<ModelConfig[]> => {
    const response = await api.get<{ code: number; message: string; data: ModelConfig[] }>('/admin/models');
    return response.data.data;
  },

  createModel: async (model: Partial<ModelConfig>): Promise<ModelConfig> => {
    const response = await api.post<{ code: number; message: string; data: ModelConfig }>('/admin/models', model);
    return response.data.data;
  },

  updateModel: async (modelId: number, model: Partial<ModelConfig>): Promise<ModelConfig> => {
    const response = await api.put<{ code: number; message: string; data: ModelConfig }>(`/admin/models/${modelId}`, model);
    return response.data.data;
  },

  deleteModel: async (modelId: number): Promise<void> => {
    await api.delete(`/admin/models/${modelId}`);
  },

  // 任务管理
  getAllAdminTasks: async (): Promise<AdminTask[]> => {
    const response = await api.get<{ code: number; message: string; data: AdminTask[] }>('/admin/tasks');
    return response.data.data;
  },

  deleteAdminTask: async (taskId: number): Promise<void> => {
    await api.delete(`/admin/tasks/${taskId}`);
  },

  // 获取指定用户的报告列表
  getUserReports: async (userId: number): Promise<UserReportsResponse> => {
    const response = await api.get<{ code: number; message: string; data: UserReportsResponse }>(`/admin/users/${userId}/reports`);
    return response.data.data;
  },
  
  // 下载指定用户的报告数据
  downloadUserReport: async (userId: number, taskId: string): Promise<void> => {
    const encodedTaskId = encodeURIComponent(taskId);
    
    try {
      const response = await api.get(`/admin/users/${userId}/reports/${encodedTaskId}/download`, {
        responseType: 'blob',
      });
      
      // 检查响应是否是错误的 JSON
      const contentType = response.headers['content-type'];
      if (contentType && contentType.includes('application/json')) {
        const text = await response.data.text();
        const errorData = JSON.parse(text);
        throw new Error(errorData.detail || '下载失败');
      }
      
      if (response.data.size === 0) {
        throw new Error('下载的文件为空，该任务可能没有生成数据');
      }
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `generated_data_${taskId}.jsonl`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error: any) {
      if (error.response) {
        let errorMessage = `下载失败: HTTP ${error.response.status}`;
        
        if (error.response.data instanceof Blob) {
          try {
            const text = await error.response.data.text();
            const errorData = JSON.parse(text);
            if (errorData.detail) {
              errorMessage = errorData.detail;
            }
          } catch {
            // 无法解析 blob
          }
        } else if (error.response.data?.detail) {
          errorMessage = error.response.data.detail;
        }
        
        throw new Error(errorMessage);
      }
      
      throw new Error(error.message || '下载失败: 未知错误');
    }
  },
};

// 报告服务
export const reportService = {
  // 获取用户的所有报告列表
  getAllReports: async (): Promise<Report[]> => {
    const response = await api.get<{ code: number; message: string; data: { success: boolean; reports: Report[]; total: number } }>('/reports');
    return response.data.data.reports;
  },

  // 获取指定任务的生成数据（预览）
  getReportData: async (taskId: string): Promise<GeneratedDataItem[]> => {
    const encodedTaskId = encodeURIComponent(taskId);
    const response = await api.get<{ code: number; message: string; data: GeneratedDataItem[]; count: number }>(`/reports/${encodedTaskId}/data`);
    return response.data.data;
  },

  // 获取指定任务的生成数据（带ID，用于编辑）
  getReportDataEditable: async (taskId: string): Promise<{ id: number; data: GeneratedDataItem; is_confirmed: boolean; created_at: string | null; updated_at: string | null }[]> => {
    const encodedTaskId = encodeURIComponent(taskId);
    const response = await api.get<{ code: number; message: string; data: { data: { id: number; data: GeneratedDataItem; is_confirmed: boolean; created_at: string | null; updated_at: string | null }[]; count: number; success: boolean } }>(`/reports/${encodedTaskId}/data/editable`);
    return response.data.data.data;
  },
  
  // 更新单条生成数据
  updateGeneratedData: async (dataId: number, content: GeneratedDataItem): Promise<void> => {
    await api.put(`/generated_data/${dataId}`, { content });
  },
  
  // 确认单条生成数据可用
  confirmGeneratedData: async (dataId: number, isConfirmed: boolean = true): Promise<void> => {
    await api.post(`/generated_data/${dataId}/confirm`, { is_confirmed: isConfirmed });
  },
  
  // 批量删除生成数据
  batchDeleteGeneratedData: async (dataIds: number[]): Promise<{ deleted_count: number }> => {
    const response = await api.delete<{ success: boolean; deleted_count: number; message: string }>('/generated_data/batch', {
      data: { data_ids: dataIds }
    });
    return { deleted_count: response.data.deleted_count };
  },
  
  // 添加新的生成数据
  addGeneratedData: async (taskId: string, content: any): Promise<{ data_id: number }> => {
    const encodedTaskId = encodeURIComponent(taskId);
    const response = await api.post<{ success: boolean; data_id: number; message: string }>(`/generated_data/${encodedTaskId}`, { content });
    return { data_id: response.data.data_id };
  },
  
  // 下载生成数据（JSONL格式）
  downloadReportData: async (taskId: string): Promise<void> => {
    // 对 taskId 进行 URL 编码，支持中文等特殊字符
    const encodedTaskId = encodeURIComponent(taskId);
    
    try {
      const response = await api.get(`/generated_data/${encodedTaskId}/download`, {
        responseType: 'blob',
      });
      
      // 检查响应是否是错误的 JSON（当 responseType 是 blob 时，错误响应也会被当作 blob）
      const contentType = response.headers['content-type'];
      if (contentType && contentType.includes('application/json')) {
        // 后端返回了 JSON 错误响应，需要解析 blob 获取错误信息
        const text = await response.data.text();
        const errorData = JSON.parse(text);
        throw new Error(errorData.detail || '下载失败');
      }
      
      // 检查 blob 是否为空或太小（可能是错误响应）
      if (response.data.size === 0) {
        throw new Error('下载的文件为空，该任务可能没有生成数据');
      }
      
      // 创建下载链接
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `generated_data_${taskId}.jsonl`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error: any) {
      // 处理 axios 错误（如 404, 500 等）
      if (error.response) {
        let errorMessage = `下载失败: HTTP ${error.response.status}`;
        
        // 尝试从 blob 响应中解析错误信息
        if (error.response.data instanceof Blob) {
          try {
            const text = await error.response.data.text();
            const errorData = JSON.parse(text);
            if (errorData.detail) {
              errorMessage = errorData.detail;
            }
          } catch {
            // 无法解析 blob，使用默认错误信息
          }
        } else if (error.response.data?.detail) {
          errorMessage = error.response.data.detail;
        }
        
        throw new Error(errorMessage);
      }
      
      // 其他错误（网络错误等）
      throw new Error(error.message || '下载失败: 未知错误');
    }
  },
  
  // 下载生成数据（CSV格式）
  downloadReportDataAsCsv: async (taskId: string): Promise<void> => {
    const encodedTaskId = encodeURIComponent(taskId);
    
    try {
      const response = await api.get(`/generated_data/${encodedTaskId}/download_csv`, {
        responseType: 'blob',
      });
      
      const contentType = response.headers['content-type'];
      if (contentType && contentType.includes('application/json')) {
        const text = await response.data.text();
        const errorData = JSON.parse(text);
        throw new Error(errorData.detail || '下载CSV失败');
      }
      
      if (response.data.size === 0) {
        throw new Error('下载的文件为空，该任务可能没有生成数据');
      }
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `generated_data_${taskId}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error: any) {
      if (error.response) {
        let errorMessage = `下载CSV失败: HTTP ${error.response.status}`;
        
        if (error.response.data instanceof Blob) {
          try {
            const text = await error.response.data.text();
            const errorData = JSON.parse(text);
            if (errorData.detail) {
              errorMessage = errorData.detail;
            }
          } catch {
            // 无法解析 blob
          }
        } else if (error.response.data?.detail) {
          errorMessage = error.response.data.detail;
        }
        
        throw new Error(errorMessage);
      }
      
      throw new Error(error.message || '下载CSV失败: 未知错误');
    }
  },
  
  // 删除单个报告
  deleteReport: async (taskId: string): Promise<void> => {
    const encodedTaskId = encodeURIComponent(taskId);
    await api.delete(`/reports/${encodedTaskId}`);
  },
  
  // 批量删除报告
  batchDeleteReports: async (taskIds: string[]): Promise<{ deleted_count: number; errors: any[] }> => {
    await api.post<{ code: number; message: string; data: { success: boolean } }>('/reports/batch_delete', { task_ids: taskIds });
    // 后端只返回 success，不返回 deleted_count 和 errors
    return { deleted_count: taskIds.length, errors: [] };
  },
};

export default api;

