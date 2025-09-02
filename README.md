# 基于Flask的远程会话管理平台

## 项目简介

这是一个基于Flask框架开发的远程会话管理平台，提供多种远程连接方式，包括SSH、SFTP、VNC、RDP等协议支持。平台采用Web界面管理，支持多客户端连接和实时监控。

## 主要功能

### 1. 连接管理（新功能）
- **统一连接管理**: 在工具箱中统一管理所有类型的连接
- **快速连接**: 主页面显示最近使用的连接，一键连接
- **连接历史**: 记录所有连接信息，包括连接次数和最后连接时间
- **智能路由**: 根据连接类型自动跳转到对应的连接页面

### 2. 远程连接管理
- **SSH连接**: 支持密码和密钥认证的SSH终端连接
- **SFTP传输**: 安全的文件传输协议支持
- **VNC远程桌面**: 基于Web的VNC客户端，支持实时屏幕共享
- **RDP远程桌面**: Windows远程桌面协议支持

### 3. 客户端管理
- 实时客户端状态监控
- 客户端连接管理
- 命令执行和结果反馈
- 文件上传下载管理

### 4. 安全特性
- 用户认证和授权
- 会话管理和超时控制
- 加密通信支持

### 5. 系统管理面板（新功能）
- **用户管理**: 系统用户账户创建、编辑、删除和权限管理
- **系统监控**: 实时CPU、内存、磁盘使用率监控
- **客户端管理**: 连接客户端状态监控和管理
- **数据库管理**: 数据库连接状态和性能监控
- **端口配置**: 各种服务的端口设置管理
- **域名设置**: 访问域名和SSL证书配置
- **密钥管理**: SSH密钥和访问令牌管理
- **系统日志**: 系统运行日志查看和分析

## 技术架构

### 后端技术栈
- **Web框架**: Flask 2.3.3
- **实时通信**: Flask-SocketIO 5.3.6
- **用户认证**: Flask-Login 0.6.3
- **SSH支持**: Paramiko 3.3.1
- **异步处理**: Eventlet/Gevent

### 项目结构
```
app/
├── __init__.py              # Flask应用工厂
├── config.py                # 配置文件
├── extensions.py            # 扩展初始化
├── models.py                # 数据模型
├── run_app.py               # 应用启动入口（推荐使用）
├── web/                     # Web相关模块
│   ├── routes/              # 路由蓝图
│   │   ├── auth.py          # 认证路由
│   │   ├── dashboard.py     # 仪表板路由
│   │   ├── assets.py        # 资源管理路由
│   │   ├── toolbox.py       # 工具箱路由（连接管理）
│   │   ├── ssh.py           # SSH连接路由
│   │   ├── sftp.py          # SFTP连接路由
│   │   ├── vnc_api.py       # VNC API路由
│   │   ├── rdp_api.py       # RDP API路由
│   │   ├── admin.py         # 管理面板API路由
│   │   └── admin_panel.py   # 管理面板页面路由
│   └── sockets.py           # WebSocket事件处理
├── services/                # 业务服务层
│   ├── client_manager.py    # 客户端管理
│   ├── rat_protocol.py      # RAT协议处理
│   └── transfer_service.py  # 文件传输服务
├── remote_access/           # 远程访问服务
│   ├── ssh_service.py       # SSH服务
│   ├── sftp_service.py      # SFTP服务
│   ├── vnc_service.py       # VNC服务
│   └── rdp_service.py       # RDP服务
├── connect_func/            # 连接功能模块
│   └── tcp_server.py        # TCP服务器
├── static/                  # 静态资源
│   ├── css/                 # 样式文件
│   ├── js/                  # JavaScript文件
│   │   ├── toolbox-new.js   # 工具箱管理脚本
│   │   └── admin-panel.js   # 管理面板脚本
│   └── novnc/               # noVNC客户端
├── templates/               # HTML模板
│   ├── auth/                # 认证页面
│   ├── dashboard/           # 仪表板页面
│   │   ├── toolbox.html     # 工具箱页面
│   │   └── admin.html       # 系统管理面板页面
│   └── assets/              # 资源页面
└── utils/                   # 工具模块
    ├── helpers.py           # 辅助函数
    ├── logging.py           # 日志配置
    └── security.py          # 安全工具
```

## 安装和运行

### 环境要求
- Python 3.8+
- pip包管理器

### 安装步骤

1. **克隆项目**
```bash
git clone <项目地址>
cd app
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**（可选）
```bash
export FLASK_ENV=dev
export SECRET_KEY=your_secret_key
export RAT_PORT=2383
export SOCKETIO_PORT=5000
```

4. **运行应用**
```bash
python run_app.py
```

### 默认配置
- **Web服务端口**: 5000
- **RAT服务端口**: 2383
- **默认用户**: admin/admin123
- **VNC代理端口**: 6080+
- **RDP代理**: 通过Guacamole

## 使用说明

### 1. 用户登录
- 访问 `http://localhost:5000/login`
- 使用默认账户: `admin` / `admin123`

### 2. 连接管理（新界面）
- **左侧连接列表**: 显示所有已保存的连接，按类型分组
- **连接状态**: 绿色圆点表示在线，灰色表示离线，黄色表示连接中
- **快速操作**: 点击连接项查看详情，右键显示更多操作菜单
- **新建连接**: 点击左侧"新建"按钮或右侧欢迎页面的快速操作按钮

### 3. 连接详情页面
- **连接信息**: 显示连接的完整配置信息
- **连接统计**: 显示连接次数、最后连接时间等
- **操作按钮**: 连接、编辑、删除等操作
- **实时状态**: 连接状态实时更新

### 4. SSH终端
- **内置终端**: 在工具箱内直接打开SSH终端
- **实时交互**: 支持命令输入和输出显示
- **终端控制**: 支持关闭、最小化、最大化操作
- **会话管理**: 自动管理SSH会话连接

### 5. 其他连接类型
- **VNC**: 在新窗口中打开VNC远程桌面
- **RDP**: 在新窗口中打开Windows远程桌面
- **SFTP**: 跳转到SFTP文件传输页面

### 6. 文件管理
- 通过SFTP工具进行文件传输
- 支持文件上传、下载、删除等操作
- 文件保存在downloads目录

## 新功能特性

### 界面设计改进
- **FinalShell风格**: 参考FinalShell的设计理念，提供专业的远程连接管理体验
- **左侧连接列表**: 清晰的连接管理界面，支持分组显示
- **右侧详情区域**: 动态显示连接详情、终端窗口或欢迎页面
- **响应式布局**: 自适应不同屏幕尺寸，支持移动端使用

### 连接管理
- **分组显示**: 按SSH、SFTP、VNC、RDP类型自动分组
- **状态指示**: 实时显示连接状态（在线/离线/连接中）
- **右键菜单**: 支持连接、编辑、复制、删除等快捷操作
- **连接详情**: 完整的连接信息展示，包括统计数据和历史记录
- **智能端口**: 根据连接类型自动设置默认端口

### SSH终端集成
- **内置终端**: 无需跳转页面，直接在工具箱内使用SSH
- **实时交互**: 支持命令输入和实时输出显示
- **终端控制**: 支持关闭、最小化、最大化操作
- **会话管理**: 自动管理SSH会话，支持多连接切换

### 用户体验优化
- **欢迎页面**: 新用户友好的引导界面，提供快速操作入口
- **通知系统**: 操作结果实时反馈，支持成功、错误、信息提示
- **键盘快捷键**: 支持常用操作的快捷键操作
- **数据持久化**: 连接信息安全保存，支持导入导出

## API接口

### 认证接口
- `POST /login` - 用户登录
- `POST /register` - 用户注册
- `GET /logout` - 用户登出

### 连接管理接口
- `GET /api/connections` - 获取连接历史
- `POST /api/connections` - 创建新连接
- `POST /api/connections/<id>/connect` - 连接到指定设备
- `DELETE /api/connections/<id>` - 删除连接
- `POST /api/connections/clear` - 清空所有连接

### 远程连接接口
- `GET /ssh/connect` - SSH连接页面
- `POST /api/ssh/connect` - SSH连接API
- `GET /vnc/connect` - VNC连接页面
- `POST /api/vnc/connect` - VNC连接API
- `GET /rdp/connect` - RDP连接页面
- `POST /api/rdp/connect` - RDP连接API

### 系统管理接口
- `GET /admin` - 系统管理面板页面
- `GET /api/admin/system-info` - 获取系统信息
- `GET /api/admin/clients` - 获取客户端信息
- `GET /api/admin/database` - 获取数据库信息
- `GET /api/admin/users` - 获取用户列表
- `POST /api/admin/users` - 创建新用户
- `DELETE /api/admin/users/<id>` - 删除用户
- `PUT /api/admin/ports` - 更新端口设置
- `PUT /api/admin/domains` - 更新域名设置
- `POST /api/admin/ssl/upload` - 上传SSL证书
- `GET /api/admin/keys/<type>` - 获取密钥信息
- `POST /api/admin/keys/<type>/regenerate` - 重新生成密钥
- `GET /api/admin/tokens/<type>` - 获取令牌信息
- `POST /api/admin/tokens/<type>/regenerate` - 重新生成令牌
- `GET /api/admin/export/users` - 导出用户数据
- `GET /api/admin/logs` - 获取系统日志
- `GET /api/admin/stats` - 获取系统统计信息

## 使用说明

### 系统管理面板
系统管理面板提供了完整的系统管理功能，只有管理员用户才能访问。

#### 访问方式
1. 使用管理员账户登录系统
2. 在浏览器中访问 `/admin` 路径
3. 系统会自动检查用户权限

#### 主要功能
1. **用户信息管理**
   - 查看当前登录用户信息
   - 创建、编辑、删除系统用户
   - 管理用户角色和权限

2. **系统监控**
   - 实时CPU、内存、磁盘使用率
   - 系统运行时间统计
   - 客户端连接状态监控

3. **配置管理**
   - 端口设置管理
   - 域名和SSL证书配置
   - SSH密钥和访问令牌管理

4. **数据管理**
   - 数据库连接状态监控
   - 系统日志查看
   - 用户数据导出

## 开发说明

### 添加新功能
1. 在`web/routes/`目录下创建新的蓝图文件
2. 在`__init__.py`中注册新蓝图
3. 创建对应的HTML模板
4. 添加必要的JavaScript功能

### 管理面板开发
1. 在`web/routes/admin.py`中添加新的API接口
2. 在`static/js/admin-panel.js`中添加前端功能
3. 在`templates/dashboard/admin.html`中添加UI组件
4. 使用`@admin_required`装饰器保护管理接口

### 调试模式
```bash
export FLASK_ENV=dev
python run_app.py
```

### 日志查看
应用运行时会输出详细的连接和错误日志，便于调试和监控。

## 安全注意事项

1. **生产环境部署**
   - 修改默认密钥和密码
   - 配置HTTPS
   - 限制访问IP范围
   - 启用防火墙规则

2. **用户权限管理**
   - 实施最小权限原则
   - 定期审查用户权限
   - 启用审计日志

3. **网络安全**
   - 使用VPN或内网部署
   - 定期更新依赖包
   - 监控异常连接

## 故障排除

### 常见问题

1. **端口被占用**
   - 检查端口配置
   - 修改config.py中的端口设置

2. **依赖安装失败**
   - 升级pip: `pip install --upgrade pip`
   - 使用虚拟环境

3. **连接失败**
   - 检查防火墙设置
   - 验证网络配置
   - 查看错误日志

4. **SSH/SFTP功能异常**
   - 确保Paramiko库已正确安装
   - 检查目标服务器SSH服务是否运行
   - 验证用户名和密码是否正确
   - 检查网络连接和端口是否可达

5. **WebSocket连接问题**
   - 确保Flask-SocketIO正确配置
   - 检查浏览器控制台是否有错误信息
   - 验证Socket.IO客户端版本兼容性

### 日志分析
应用运行时会输出详细的连接日志，包括：
- 客户端连接/断开
- 命令执行结果
- 错误和异常信息

## 更新日志

### v1.3.0 (当前版本)
- ✨ 新增系统管理面板，提供完整的系统管理功能
- ✨ 用户管理：创建、编辑、删除系统用户，角色权限管理
- ✨ 系统监控：实时CPU、内存、磁盘使用率，系统运行时间
- ✨ 客户端管理：连接状态监控，在线/离线状态显示
- ✨ 配置管理：端口设置、域名配置、SSL证书、密钥管理
- ✨ 数据库监控：连接状态、性能指标、数据统计
- ✨ 系统日志：运行日志查看、错误分析、审计追踪
- 🔒 权限控制：管理员专用，@admin_required装饰器保护
- 📱 响应式设计：支持移动端和桌面端访问

### v1.2.0
- ✨ 重新设计工具箱界面，参考FinalShell设计风格
- ✨ 左侧连接列表 + 右侧连接详情的布局
- ✨ 连接按类型分组显示，支持树形结构
- ✨ 实时连接状态显示（在线/离线/连接中）
- ✨ 右键菜单支持连接、编辑、复制、删除操作
- ✨ 内置SSH终端，支持实时命令执行
- ✨ 连接详情页面，显示完整的连接信息
- ✨ 欢迎页面，提供快速操作入口
- ✨ 响应式设计，支持移动端和桌面端
- 🔧 优化连接管理逻辑和用户体验
- 📱 改进界面交互和视觉效果

### v1.1.0
- ✨ 新增统一连接管理功能
- ✨ 新增快速连接界面
- ✨ 新增连接历史记录
- ✨ 优化用户界面和导航
- 🔧 修复路由和模板问题
- 📱 改进响应式设计

## 贡献指南

欢迎提交Issue和Pull Request来改进项目。

## 许可证

本项目采用MIT许可证，详见LICENSE文件。
