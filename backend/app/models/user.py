# 导入datetime模块，用于处理日期时间相关操作
from datetime import datetime

# 从sqlalchemy导入必要的字段类型和函数
# Boolean: 布尔类型字段
# DateTime: 日期时间类型字段
# String: 字符串类型字段
# func: 用于调用数据库内置函数（如now()）
from sqlalchemy import Boolean, DateTime, String, func
# 从sqlalchemy.orm导入ORM相关的类型和方法
# Mapped: 用于类型注解，定义模型字段与Python类型的映射
# mapped_column: 定义数据库表的列属性
# relationship: 定义模型之间的关联关系
from sqlalchemy.orm import Mapped, mapped_column, relationship

# 导入自定义的基础模型类（所有模型都继承自此类）
from app.db.base import Base


# 定义用户模型类，继承自Base（SQLAlchemy的声明式基础类）
class User(Base):
    # 指定该模型对应的数据库表名
    __tablename__ = "users"

    # 主键字段：用户ID
    # Mapped[int] 注解表示该字段映射为Python的int类型
    # mapped_column参数说明：
    # primary_key=True: 设为主键
    # index=True: 为该字段创建索引，提升查询效率
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # 用户名字段
    # String(50): 字符串类型，最大长度50
    # unique=True: 用户名唯一，不允许重复
    # index=True: 创建索引
    # nullable=False: 该字段不允许为空
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)

    # 密码哈希字段（存储加密后的密码，而非明文）
    # String(255): 字符串类型，最大长度255（适配常见的哈希算法结果长度）
    # nullable=False: 该字段不允许为空
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # 是否为管理员标识
    # Boolean: 布尔类型
    # default=False: 默认值为False（普通用户）
    # nullable=False: 该字段不允许为空
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 用户创建时间
    # DateTime(timezone=True): 带时区的日期时间类型
    # server_default=func.now(): 数据库层面的默认值为当前时间（调用数据库的now()函数）
    # nullable=False: 该字段不允许为空
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # 定义与ChatSession模型的关联关系
    # relationship: 建立模型间的双向关联
    # "ChatSession": 关联的目标模型类名
    # back_populates="user": 对应ChatSession模型中名为user的关联字段，实现双向关联
    # cascade="all, delete-orphan": 级联操作配置
    # - all: 所有操作（增删改）都级联到关联的ChatSession记录
    # - delete-orphan: 当ChatSession记录不再关联到任何User时，自动删除该ChatSession
    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")