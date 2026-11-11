# 从fastapi导入路由和异常处理相关的模块
# APIRouter: 用于创建可复用的路由组件
# Depends: 用于依赖注入（如获取数据库会话）
# HTTPException: 用于抛出HTTP异常
# status: 包含HTTP状态码常量
from fastapi import APIRouter, Depends, HTTPException, status
# 从sqlalchemy导入查询构造器select
from sqlalchemy import select
# 从sqlalchemy.orm导入数据库会话类型
from sqlalchemy.orm import Session

# 导入自定义的安全相关函数
# create_access_token: 生成JWT访问令牌
# get_password_hash: 对明文密码进行哈希加密
# verify_password: 验证明文密码与哈希密码是否匹配
from app.core.security import create_access_token, get_password_hash, verify_password
# 导入获取数据库会话的依赖函数
from app.db.session import get_db
# 导入用户模型类
from app.models.user import User
# 导入认证相关的Pydantic模式（用于数据校验和序列化）
from app.schemas.auth import TokenResponse, UserLogin, UserRegister

# 创建API路由实例，用于挂载认证相关的接口
router = APIRouter()


# 定义用户注册接口
# @router.post: POST请求方法
# "/register": 接口路径
# response_model=TokenResponse: 响应数据的模型（自动校验和序列化）
# status_code=status.HTTP_201_CREATED: 成功响应的状态码（201表示资源创建成功）
@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> TokenResponse:
    """
    用户注册接口

    参数说明：
    - payload: UserRegister类型的请求体，包含用户名和密码（由Pydantic校验）
    - db: 数据库会话对象，通过Depends(get_db)自动注入

    返回值：
    - TokenResponse: 包含访问令牌、用户名、是否为管理员的响应体
    """
    # 查询数据库，检查用户名是否已存在
    # select(User).where(User.username == payload.username): 构造查询语句
    # db.execute(): 执行查询
    # scalar_one_or_none(): 返回单个结果（存在则返回User对象，不存在则返回None）
    existing_user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    # 如果用户名已存在，抛出400 Bad Request异常
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    # 创建新用户对象
    user = User(
        username=payload.username,  # 从请求体获取用户名
        password_hash=get_password_hash(payload.password),  # 对密码进行哈希加密
        is_admin=False,  # 默认注册为普通用户（非管理员）
    )
    # 将新用户对象添加到数据库会话
    db.add(user)
    # 提交事务，将数据写入数据库
    db.commit()
    # 刷新用户对象，获取数据库自动生成的字段（如id、created_at）
    db.refresh(user)
    # 生成JWT访问令牌（以用户ID为标识）
    token = create_access_token(str(user.id))
    # 返回注册成功的响应数据
    return TokenResponse(access_token=token, username=user.username, is_admin=user.is_admin)


# 定义用户登录接口
# @router.post: POST请求方法
# "/login": 接口路径
# response_model=TokenResponse: 响应数据的模型
@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    """
    用户登录接口

    参数说明：
    - payload: UserLogin类型的请求体，包含用户名和密码（由Pydantic校验）
    - db: 数据库会话对象，通过Depends(get_db)自动注入

    返回值：
    - TokenResponse: 包含访问令牌、用户名、是否为管理员的响应体

    异常：
    - 401 Unauthorized: 用户名不存在或密码错误时抛出
    """
    # 查询数据库，获取指定用户名的用户对象
    user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    # 验证用户是否存在，且密码是否匹配
    # verify_password(payload.password, user.password_hash): 对比明文密码和哈希密码
    if not user or not verify_password(payload.password, user.password_hash):
        # 抛出401 Unauthorized异常，提示用户名或密码错误
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    # 生成JWT访问令牌（以用户ID为标识）
    token = create_access_token(str(user.id))
    # 返回登录成功的响应数据
    return TokenResponse(access_token=token, username=user.username, is_admin=user.is_admin)