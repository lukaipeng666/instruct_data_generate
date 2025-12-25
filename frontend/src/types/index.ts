export interface User {
  username: string;
  is_active: boolean;
  is_admin: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  username: string;
  is_admin: boolean;
}

export interface TaskParams {
  input_file: string;
  output: string;
  model_id?: number;  // 新增：模型ID（可选）
  services?: string[];  // 改为可选
  model?: string;  // 改为可选
  task_type: string;
  batch_size: number;
  max_concurrent: number;
  min_score: number;
  variants_per_sample: number;
  data_rounds: number;
  retry_times: number;
  special_prompt: string;
  directions: string;
}

export interface Task {
  task_id: string;
  finished: boolean;
  return_code: number | null;
  params: TaskParams;
  run_time: number;
}

export interface InputFile {
  path: string;
  name: string;
  folder: string;
}

// 管理员相关类型
export interface AdminUser {
  id: number;
  username: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string | null;
  task_count: number;
  report_count: number;
}

export interface ModelConfig {
  id: number;
  name: string;
  api_url: string;
  api_key: string;
  model_path: string;
  max_concurrent: number;
  temperature: number;
  top_p: number;
  max_tokens: number;
  is_vllm: boolean;  // 是否使用vLLM格式
  timeout: number;   // 超时时间（秒）
  description: string | null;
  is_active: boolean;
  created_at: string | null;
}

export interface AdminTask {
  id: number;
  task_id: string;
  username: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  params: string;
  error_message: string | null;
}

// 数据文件相关类型
export interface DataFile {
  id: number;  // 修改为 number 类型以匹配后端返回的整数ID
  name: string;
  size: number;
  upload_time: string;
  path: string;
}

// 报告相关类型
export interface Report {
  id: number;
  task_id: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  data_count: number;
  has_data: boolean;
  params: any;
  error_message: string | null;
  // 审核状态
  confirmed_count?: number;
  is_fully_reviewed?: boolean;
}

export interface GeneratedDataItem {
  [key: string]: any;
}

