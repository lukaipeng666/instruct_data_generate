#!/usr/bin/env python3
"""
Web前端应用
提供Web界面来配置和运行数据生成任务
"""

import os
import sys
import subprocess
import json
import threading
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import queue
import time
from config.tools import FORMAT_EVALUATORS

app = Flask(__name__)
CORS(app)


@app.route('/api/task_types')
def get_task_types():
    """获取支持的任务类型列表"""
    return jsonify({
        'success': True,
        'types': list(FORMAT_EVALUATORS.keys())
    })


# 存储运行中的任务
running_tasks = {}


def run_main_py(params, task_id):
    """运行 main.py 并捕获输出"""
    # 构建命令
    cmd = [sys.executable, os.path.join(os.path.dirname(__file__), 'main.py')]
    
    # 添加所有参数
    for key, value in params.items():
        if key == 'directions':
            # directions 是空格分隔的字符串，需要拆分成多个参数
            if value and value.strip():
                directions_list = value.strip().split()
                cmd.extend(['--directions'] + directions_list)
        elif key == 'services':
            # services 是列表，需要拆分成多个参数
            if isinstance(value, list) and len(value) > 0:
                cmd.extend(['--services'] + value)
            elif isinstance(value, str) and value.strip():
                # 如果是字符串，按空格或逗号分隔
                services_list = [s.strip() for s in value.replace(',', ' ').split() if s.strip()]
                if services_list:
                    cmd.extend(['--services'] + services_list)
        elif key == 'special_prompt':
            # special_prompt 即使为空字符串也要传递
            arg_name = '--' + key.replace('_', '-')
            cmd.append(arg_name)
            cmd.append(str(value) if value is not None else '')
        elif value is not None and value != '':
            # 将参数名转换为命令行格式
            arg_name = '--' + key.replace('_', '-')
            if isinstance(value, bool):
                if value:
                    cmd.append(arg_name)
            else:
                cmd.append(arg_name)
                cmd.append(str(value))
    
    # 运行进程并实时捕获输出
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,
        cwd=os.path.dirname(__file__)
    )
    
    # 将进程对象存储到任务中
    running_tasks[task_id]['process'] = process
    
    # 实时读取输出
    output_queue = running_tasks[task_id]['output_queue']
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                output_queue.put(line.rstrip())
        output_queue.put(None)  # 结束标记
    except Exception as e:
        output_queue.put(f"ERROR: {str(e)}")
        output_queue.put(None)
    finally:
        process.wait()
        running_tasks[task_id]['return_code'] = process.returncode
        running_tasks[task_id]['finished'] = True


@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')


@app.route('/api/start', methods=['POST'])
def start_task():
    """启动任务"""
    try:
        data = request.json
        
        # 验证必填参数（只有输入输出文件是必填的）
        if not data.get('input_file') or not data.get('input_file').strip():
            return jsonify({
                'success': False,
                'error': '缺少必填参数: input_file'
            }), 400
        
        if not data.get('output') or not data.get('output').strip():
            return jsonify({
                'success': False,
                'error': '缺少必填参数: output'
            }), 400
        
        # 生成任务ID
        task_id = f"task_{int(time.time() * 1000)}"
        
        # 准备参数（使用默认值）
        params = {
            'input_file': data['input_file'],
            'output': data['output'],
            'services': data.get('services', ['http://localhost:6466/v1']),
            'model': data.get('model', '/data/kaipeng/model/Qwen/Qwen3-235B-A22B-Instruct-2507'),
            'batch_size': int(data.get('batch_size', 16)),
            'max_concurrent': int(data.get('max_concurrent', 16)),
            'min_score': int(data.get('min_score', 10)),
            'task_type': data.get('task_type', 'general'),
            'variants_per_sample': int(data.get('variants_per_sample', 3)),
            'data_rounds': int(data.get('data_rounds', 10)),
            'retry_times': int(data.get('retry_times', 3)),
            'special_prompt': data.get('special_prompt', ''),
            'directions': data.get('directions', '信用卡年费 股票爆仓 基金赎回')
        }
        
        # 初始化任务
        running_tasks[task_id] = {
            'output_queue': queue.Queue(),
            'process': None,
            'finished': False,
            'return_code': None,
            'params': params
        }
        
        # 在新线程中运行任务
        thread = threading.Thread(target=run_main_py, args=(params, task_id))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    """获取任务进度（Server-Sent Events）"""
    if task_id not in running_tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    def generate():
        output_queue = running_tasks[task_id]['output_queue']
        while True:
            try:
                line = output_queue.get(timeout=1)
                if line is None:  # 结束标记
                    # 发送最终状态
                    task_info = running_tasks[task_id]
                    yield f"data: {json.dumps({'type': 'finished', 'return_code': task_info['return_code']})}\n\n"
                    break
                else:
                    yield f"data: {json.dumps({'type': 'output', 'line': line})}\n\n"
            except queue.Empty:
                # 检查任务是否已完成
                if running_tasks[task_id]['finished']:
                    task_info = running_tasks[task_id]
                    yield f"data: {json.dumps({'type': 'finished', 'return_code': task_info['return_code']})}\n\n"
                    break
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/api/stop/<task_id>', methods=['POST'])
def stop_task(task_id):
    """停止任务"""
    if task_id not in running_tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    task = running_tasks[task_id]
    if task['process']:
        try:
            task['process'].terminate()
            task['process'].wait(timeout=5)
        except:
            task['process'].kill()
    
    task['finished'] = True
    return jsonify({'success': True})


@app.route('/api/status/<task_id>')
def get_status(task_id):
    """获取任务状态"""
    if task_id not in running_tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    task = running_tasks[task_id]
    return jsonify({
        'finished': task['finished'],
        'return_code': task['return_code']
    })


@app.route('/api/active_task')
def get_active_task():
    """获取当前正在运行的任务ID"""
    for task_id, task in running_tasks.items():
        if not task['finished']:
            return jsonify({
                'success': True,
                'task_id': task_id,
                'params': task['params']
            })
    return jsonify({
        'success': False,
        'message': '没有运行中的任务'
    })


if __name__ == '__main__':
    # 生产环境下建议 debug=False
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

