"""
数据库模型定义
"""
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()


class User(Base):
    """用户表"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)  # 是否为管理员
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联任务
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    # 关联数据文件
    data_files = relationship("DataFile", back_populates="user", cascade="all, delete-orphan")


class ModelConfig(Base):
    """模型配置表"""
    __tablename__ = 'model_configs'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)  # 模型名称
    api_url = Column(String(255), nullable=False)  # API地址
    api_key = Column(String(255), default='sk-xxxxx')  # API密钥
    model_path = Column(String(500), nullable=False)  # 模型路径
    max_concurrent = Column(Integer, default=16)  # 最大并发数
    temperature = Column(Float, default=1.0)  # 温度
    top_p = Column(Float, default=1.0)  # top_p采样
    max_tokens = Column(Integer, default=2048)  # 最大token数
    is_vllm = Column(Boolean, default=True)  # 是否使用vLLM格式
    timeout = Column(Integer, default=600)  # 超时时间（秒）
    description = Column(Text)  # 描述
    is_active = Column(Boolean, default=True)  # 是否可用
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Task(Base):
    """任务记录表"""
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(100), unique=True, index=True, nullable=False)  # 任务ID
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # 所属用户
    status = Column(String(20), default='running')  # 状态: running, finished, error, stopped
    params = Column(Text)  # 任务参数(JSON格式)
    result = Column(Text)  # 任务结果
    error_message = Column(Text)  # 错误信息
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)
    
    # 关联用户
    user = relationship("User", back_populates="tasks")


class DataFile(Base):
    """数据文件表 - 存储用户上传的文件"""
    __tablename__ = 'data_files'
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)  # 原始文件名
    file_content = Column(LargeBinary, nullable=False)  # 文件内容（二进制存储）
    file_size = Column(Integer, nullable=False)  # 文件大小（字节）
    content_type = Column(String(100), default='application/x-jsonlines')  # 文件类型
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # 所属用户
    created_at = Column(DateTime, default=datetime.utcnow)  # 上传时间
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联用户
    user = relationship("User", back_populates="data_files")


class GeneratedData(Base):
    """生成数据表 - 存储模型生成的对话数据"""
    __tablename__ = 'generated_data'
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(100), ForeignKey('tasks.task_id'), nullable=False, index=True)  # 关联任务
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)  # 所属用户
    data_content = Column(Text, nullable=False)  # 数据内容（JSON格式）
    model_score = Column(Float)  # 模型评分
    rule_score = Column(Integer)  # 规则评分
    retry_count = Column(Integer, default=0)  # 重试次数
    generation_model = Column(String(255))  # 生成模型名称
    task_type = Column(String(50))  # 任务类型
    is_confirmed = Column(Boolean, default=False)  # 是否已确认可用
    created_at = Column(DateTime, default=datetime.utcnow)  # 生成时间
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 更新时间
    
    # 关联用户和任务
    user = relationship("User", backref="generated_data")
    task = relationship("Task", backref="generated_data")


# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), 'app.db')
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# 创建数据库引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite需要这个参数
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """初始化数据库，创建表"""
    Base.metadata.create_all(bind=engine)


def verify_and_create_columns():
    """
    核查数据库所有必需的字段，如果不存在则创建
    用于数据库升级和字段迁移
    """
    from sqlalchemy import inspect, text
    
    inspector = inspect(engine)
    
    # 定义所有表的必需字段
    required_columns = {
        'users': [
            {'name': 'id', 'type': 'INTEGER', 'nullable': False},
            {'name': 'username', 'type': 'VARCHAR(50)', 'nullable': False},
            {'name': 'password_hash', 'type': 'VARCHAR(255)', 'nullable': False},
            {'name': 'is_active', 'type': 'BOOLEAN', 'default': True},
            {'name': 'is_admin', 'type': 'BOOLEAN', 'default': False},
            {'name': 'created_at', 'type': 'DATETIME'},
            {'name': 'updated_at', 'type': 'DATETIME'},
        ],
        'model_configs': [
            {'name': 'id', 'type': 'INTEGER', 'nullable': False},
            {'name': 'name', 'type': 'VARCHAR(100)', 'nullable': False},
            {'name': 'api_url', 'type': 'VARCHAR(255)', 'nullable': False},
            {'name': 'api_key', 'type': 'VARCHAR(255)', 'default': 'sk-xxxxx'},
            {'name': 'model_path', 'type': 'VARCHAR(500)', 'nullable': False},
            {'name': 'max_concurrent', 'type': 'INTEGER', 'default': 16},
            {'name': 'temperature', 'type': 'FLOAT', 'default': 1.0},
            {'name': 'top_p', 'type': 'FLOAT', 'default': 1.0},
            {'name': 'max_tokens', 'type': 'INTEGER', 'default': 2048},
            {'name': 'is_vllm', 'type': 'BOOLEAN', 'default': True},
            {'name': 'timeout', 'type': 'INTEGER', 'default': 600},
            {'name': 'description', 'type': 'TEXT'},
            {'name': 'is_active', 'type': 'BOOLEAN', 'default': True},
            {'name': 'created_at', 'type': 'DATETIME'},
            {'name': 'updated_at', 'type': 'DATETIME'},
        ],
        'tasks': [
            {'name': 'id', 'type': 'INTEGER', 'nullable': False},
            {'name': 'task_id', 'type': 'VARCHAR(100)', 'nullable': False},
            {'name': 'user_id', 'type': 'INTEGER', 'nullable': False},
            {'name': 'status', 'type': 'VARCHAR(20)', 'default': 'running'},
            {'name': 'params', 'type': 'TEXT'},
            {'name': 'result', 'type': 'TEXT'},
            {'name': 'error_message', 'type': 'TEXT'},
            {'name': 'started_at', 'type': 'DATETIME'},
            {'name': 'finished_at', 'type': 'DATETIME'},
        ],
        'data_files': [
            {'name': 'id', 'type': 'INTEGER', 'nullable': False},
            {'name': 'filename', 'type': 'VARCHAR(255)', 'nullable': False},
            {'name': 'file_content', 'type': 'BLOB', 'nullable': False},
            {'name': 'file_size', 'type': 'INTEGER', 'nullable': False},
            {'name': 'content_type', 'type': 'VARCHAR(100)', 'default': 'application/x-jsonlines'},
            {'name': 'user_id', 'type': 'INTEGER', 'nullable': False},
            {'name': 'created_at', 'type': 'DATETIME'},
            {'name': 'updated_at', 'type': 'DATETIME'},
        ],
        'generated_data': [
            {'name': 'id', 'type': 'INTEGER', 'nullable': False},
            {'name': 'task_id', 'type': 'VARCHAR(100)', 'nullable': False},
            {'name': 'user_id', 'type': 'INTEGER', 'nullable': False},
            {'name': 'data_content', 'type': 'TEXT', 'nullable': False},
            {'name': 'model_score', 'type': 'FLOAT'},
            {'name': 'rule_score', 'type': 'INTEGER'},
            {'name': 'retry_count', 'type': 'INTEGER', 'default': 0},
            {'name': 'generation_model', 'type': 'VARCHAR(255)'},
            {'name': 'task_type', 'type': 'VARCHAR(50)'},
            {'name': 'is_confirmed', 'type': 'BOOLEAN', 'default': False},
            {'name': 'created_at', 'type': 'DATETIME'},
            {'name': 'updated_at', 'type': 'DATETIME'},
        ],
    }
    
    db = SessionLocal()
    try:
        # 检查每个表的字段
        for table_name, columns in required_columns.items():
            # 检查表是否存在
            if not inspector.has_table(table_name):
                print(f"⚠️  表 {table_name} 不存在，将通过 create_all 创建")
                continue
            
            # 获取现有字段
            existing_columns = {col['name']: col for col in inspector.get_columns(table_name)}
            
            # 检查每个必需字段
            for col_spec in columns:
                col_name = col_spec['name']
                if col_name not in existing_columns:
                    # 字段不存在，需要添加
                    print(f"⚠️  表 {table_name} 缺少字段 {col_name}，正在添加...")
                    
                    # 构建 ALTER TABLE 语句（SQLite 语法）
                    nullable = col_spec.get('nullable', True)
                    default = col_spec.get('default')
                    
                    # 构建字段定义
                    col_def = f"{col_name} {col_spec['type']}"
                    
                    # 添加默认值
                    if default is not None:
                        if isinstance(default, bool):
                            col_def += f" DEFAULT {1 if default else 0}"
                        elif isinstance(default, str):
                            col_def += f" DEFAULT '{default}'"
                        else:
                            col_def += f" DEFAULT {default}"
                    
                    # SQLite 的 ALTER TABLE ADD COLUMN 不支持 NOT NULL（除非有 DEFAULT）
                    # 如果需要 NOT NULL，必须提供默认值
                    if not nullable and default is None:
                        print(f"  ⚠️  警告: 字段 {col_name} 要求 NOT NULL 但没有默认值，跳过添加")
                        continue
                    
                    try:
                        # 执行 ALTER TABLE
                        alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_def}"
                        db.execute(text(alter_sql))
                        db.commit()
                        print(f"  ✅ 成功添加字段: {table_name}.{col_name}")
                    except Exception as e:
                        db.rollback()
                        print(f"  ❌ 添加字段失败: {table_name}.{col_name} - {e}")
                else:
                    # 字段已存在
                    pass
        
        print("\n✅ 数据库字段核查完成")
        
    except Exception as e:
        print(f"❌ 数据库字段核查失败: {e}")
        db.rollback()
    finally:
        db.close()


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

