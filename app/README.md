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
- **漏洞扫描**: 对客户端进行安全漏洞扫描，支持多种扫描模式
  - 扫描任务与结果持久化保存，支持跨会话查询历史记录
  - 支持导出 HTML/TXT 报告，方便归档或分享扫描结果

### 4. 安全特性
- 用户认证和授权
- 会话管理和超时控制
- **加密通信支持**: 
  - AES-256-GCM 对称加密算法
  - ECDH (椭圆曲线迪菲-赫尔曼) 密钥交换
  - 独立的客户端和服务端加密模块
  - 安全的握手协议和密钥协商
- **验证码防护**: 登录页面集成图形验证码，防止暴力破解攻击

### 5. 系统管理面板（新功能）
- **用户管理**: 系统用户账户创建、编辑、删除和权限管理
- **个人信息**: 用户个人资料管理、密码修改、安全设置
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
- **加密通信**: cryptography (AES-256-GCM + ECDH)
- **异步处理**: Eventlet/Gevent
- **图像处理**: Pillow (用于验证码生成)

### 项目结构
```
app/
├── __init__.py              # Flask应用工厂
├── config.py                # 配置文件
├── extensions.py            # 扩展初始化
├── models.py                # 数据模型
├── run.py                   # 应用启动入口（推荐使用）
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
│   │   ├── admin_panel.py   # 管理面板页面路由
│   │   ├── user_management.py # 用户管理路由
│   │   ├── vulnerability_scan.py # 漏洞扫描路由
│   │   └── profile.py       # 个人信息路由
│   └── sockets.py           # WebSocket事件处理
├── services/                # 业务服务层
│   ├── client_manager.py    # 客户端管理
│   ├── encryption.py        # 服务端加密通信模块
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
│   │   ├── admin-panel.js   # 管理面板脚本
│   │   ├── user-management.js # 用户管理脚本
│   │   ├── vulnerability-scan.js # 漏洞扫描脚本
│   │   └── profile.js       # 个人信息脚本
│   └── novnc/               # noVNC客户端
├── templates/               # HTML模板
│   ├── auth/                # 认证页面
│   ├── dashboard/           # 仪表板页面
│   │   ├── toolbox.html     # 工具箱页面
│   │   ├── admin.html       # 系统管理面板页面
│   │   ├── user_management.html # 用户管理页面
│   │   ├── vulnerability_scan.html # 漏洞扫描页面
│   │   └── profile.html     # 个人信息页面
│   └── assets/              # 资源页面
├── utils/                   # 工具模块
    ├── helpers.py           # 辅助函数
    ├── logging.py           # 日志配置
    ├── security.py          # 安全工具
    └── captcha.py           # 验证码生成器
└── 客户端/                  # 独立客户端模块
    ├── client.py            # 主客户端程序
    ├── client_encryption.py # 客户端加密通信模块
    └── client_linux.py     # Linux版本客户端
```

## 加密通信架构

### 设计原则
- **独立性**: 客户端和服务端各自拥有独立的加密模块，避免架构耦合
- **安全性**: 使用业界标准的 AES-256-GCM 加密算法和 ECDH 密钥交换
- **兼容性**: 支持加密和明文两种通信模式，确保向后兼容
- **容错性**: 加密失败时自动降级到明文连接，保证服务可用性

### 技术实现
- **服务端模块**: `services/encryption.py`
  - `EncryptionManager`: 管理密钥生成、加密解密操作
  - `SecureSocket`: 封装加密通信的Socket接口
- **客户端模块**: `客户端/client_encryption.py`
  - `ClientEncryptionManager`: 客户端专用的加密管理器
  - `ClientSecureSocket`: 客户端加密Socket实现

### 通信流程
1. **连接建立**: 客户端连接到服务端TCP端口
2. **密钥交换**: 
   - 客户端发送 `key_exchange` 消息（明文）
   - 服务端响应 `key_exchange_ack` 消息（明文）
   - 双方完成ECDH密钥交换，生成共享密钥
3. **加密通信**: 后续所有消息使用AES-256-GCM加密传输
4. **降级处理**: 如果密钥交换失败，自动切换到明文通信

### 安全特性
- **前向安全性**: 每次连接生成新的临时密钥对
- **完整性保护**: GCM模式提供消息认证和完整性验证
- **重放攻击防护**: 使用随机nonce防止重放攻击
- **密钥隔离**: 客户端和服务端密钥管理完全独立

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
python run.py
```

### 默认配置
- **Web服务端口**: 5000
- **RAT服务端口**: 2383
- **默认用户**: admin/admin123
- **VNC代理端口**: 6080+
- **RDP代理**: 通过Guacamole

### 漏洞扫描配置（fscan）
- 将对应操作系统的 fscan 可执行文件放置在项目根目录的 `fscan/` 目录下，默认约定：
  - Windows: `fscan/fscan.exe`
  - Linux: `fscan/fscan`
- 可通过环境变量覆盖默认路径：
  - `FSCAN_WINDOWS_PATH`
  - `FSCAN_LINUX_PATH`
  - `FSCAN_DEFAULT_PATH`（非 Windows/Linux 平台的备用路径）
  - `FSCAN_OUTPUT_DIR`（扫描日志与报告的输出目录，默认 `downloads/scan_reports`）
- 扫描报告导出接口：`/api/vulnerability-scan/report/<task_id>?format=html|txt`
- 后端会自动检测运行平台并选择匹配的二进制，请确保文件具有执行权限（Linux 环境需要 `chmod +x`）。

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

### 7. 客户端部署和使用
- **独立部署**: 客户端可以完全独立运行，无需依赖服务端模块
- **加密通信**: 自动进行密钥交换，建立安全的加密连接
- **降级处理**: 如果加密初始化失败，会自动降级到明文连接
- **跨平台支持**: 支持Windows和Linux平台
- **连接码认证**: 使用连接码进行客户端身份验证

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

6. **客户端连接和加密通信问题**
   - **客户端立即断开**: 检查客户端是否使用了独立的加密模块
     - 确保客户端使用 `client_encryption.py` 而不是服务端的 `encryption.py`
     - 验证客户端目录下是否存在 `client_encryption.py` 文件
   - **密钥交换失败**: 检查握手阶段的消息传输
     - 确保 `key_exchange` 和 `key_exchange_ack` 消息以明文传输
     - 检查客户端和服务端的 `send_encrypted` 方法是否正确处理握手消息
   - **加密解密错误**: 验证加密算法和密钥生成
     - 确保客户端和服务端都使用 AES-256-GCM 算法
     - 检查 ECDH 密钥交换是否成功完成
     - 验证共享密钥的生成和使用是否一致
   - **连接降级到明文**: 检查加密初始化过程
     - 查看客户端日志中的密钥交换状态
     - 确认服务端是否正确响应密钥交换请求
     - 验证加密管理器的初始化状态

### 日志分析
应用运行时会输出详细的连接日志，包括：
- 客户端连接/断开
- 命令执行结果
- 错误和异常信息

## 更新日志

### v1.3.7 (最新更新 - 2025年1月25日)
- **重大修复**: 解决了客户端连接后立即断开的严重问题
- **架构重构**: 修复了客户端错误导入服务端加密模块的设计缺陷
  - 问题根因：客户端通过 `sys.path` 修改导入服务端的 `encryption.py` 模块，导致架构混乱
  - 解决方案：创建独立的客户端加密模块 `client_encryption.py`，实现完全独立的加密通信
- **加密通信优化**: 
  - 实现了 AES-256-GCM 对称加密和 ECDH 密钥交换
  - 修复了密钥交换阶段的加密时序问题：确保握手消息以明文传输，避免解密失败
  - 优化了服务端和客户端的 `send_encrypted` 方法，对 `key_exchange` 和 `key_exchange_ack` 消息类型进行特殊处理
- **错误处理改进**: 
  - 增强了密钥交换失败时的降级处理，自动回退到明文连接
  - 改进了客户端连接错误的日志记录和调试信息
- **独立部署支持**: 客户端现在可以完全独立运行，无需依赖服务端模块
- **向后兼容**: 保持了与现有服务端的完全兼容性

### v1.3.6 (2025年1月25日)
- **新增**: 创建了漏洞扫描页面，位于工具栏目下，提供客户端漏洞扫描功能
  - 后端路由：`vulnerability_scan.py` - 实现扫描任务管理、状态监控和结果展示API
  - 前端界面：`vulnerability_scan.html` - 现代化的扫描配置和结果展示界面
  - JavaScript功能：`vulnerability-scan.js` - 实时扫描状态更新和交互功能
  - 功能特性：支持基础扫描、深度扫描、自定义扫描，实时状态监控，扫描历史记录
- **新增**: 创建了个人信息页面，位于用户管理上方，提供用户个人信息管理功能
  - 后端路由：`profile.py` - 实现个人信息管理、密码修改、安全设置API
  - 前端界面：`profile.html` - 完整的个人资料管理界面，包含头像、基本信息、安全设置
  - JavaScript功能：`profile.js` - 个人信息更新、密码强度检测、头像上传等交互功能
  - 功能特性：个人资料编辑、密码修改、安全设置、活动记录查看
- **集成**: 在主应用中注册了新的蓝图，更新了导航菜单链接
- **修复**: 解决了导航链接端点名称错误导致的 `BuildError` 问题
- **测试**: 验证了新页面的功能完整性和界面响应性

### v1.3.5 (2025年1月25日)
- **重构**: 完全移除了授权码模块，简化了系统架构
- **删除**: 移除了 `AuthCode`、`AuthCodeDeviceMap`、`AuthCodeApplication` 等数据库模型
- **删除**: 移除了授权码相关的路由文件 `auth_code.py` 和前端文件 `auth-codes.js`
- **删除**: 移除了授权码管理页面模板和导航链接
- **清理**: 清理了相关的数据库迁移文件和蓝图注册
- **优化**: 系统架构更加简洁，减少了不必要的复杂性
- **测试**: 验证了删除后系统的稳定性和功能完整性

### v1.3.4
- **修复**: 修复了用户管理界面样式问题，将Tailwind CSS类替换为Bootstrap框架和项目自定义样式系统
- **优化**: 重写了 `user_management.html` 页面，使用Bootstrap网格系统和项目CSS变量，确保样式一致性
- **优化**: 更新了 `user_modal.html` 模态框，采用Bootstrap 5标准模态框组件，增加了密码显示切换和用户启用状态开关功能
- **改进**: 统一了用户管理界面的视觉风格，提升了用户体验和界面响应性

### v1.3.3
- **重构**: 将用户管理功能从 `admin` 模块中分离出来，创建了独立的 `user_management` 蓝图，提高了代码的模块化和可维护性。
- **修复**: 修正了侧边栏中"授权码管理"和"用户管理"的链接和样式问题，确保了导航的正确性和视觉一致性。
- **修复**: 解决了由于 `url_for` 端点名称不正确导致的 `BuildError`。

### v1.3.2
- **修复**：解决了客户端连接时会创建两条数据库记录（一条临时记录和一条完整记录）的严重问题。
- **优化**：重构了客户端连接处理逻辑，确保只在客户端提供了有效的 `device_fingerprint` 后，才执行数据库的创建或更新操作。
- **清理**：移除了所有使用临时自增 ID `client_id` 与数据库交互的遗留代码，从根本上杜绝了不完整记录的产生。

### v1.3.2 (最新版本)
- ✨ 新增登录验证码功能，增强系统安全性
- 🔒 防暴力破解：登录页面集成图形验证码，有效防止自动化攻击
- 🎨 验证码特性：
  - 使用数字和大写字母组合，避免易混淆字符
  - 支持点击刷新验证码
  - 添加干扰线和噪点，提高识别难度
  - 验证后自动清除session，防止重复使用
- 🛠️ 技术实现：
  - 新增 `utils/captcha.py` 验证码生成器
  - 基于 Pillow 库生成图形验证码
  - 集成到登录路由和前端表单
  - 添加 `/auth/captcha` API 接口
- 📦 依赖更新：添加 Pillow 图像处理库

### v1.3.1
- 修复客户端重复记录问题：仅在收到 device_fingerprint 时才创建或查找数据库记录，避免生成不完整记录
- 移除临时连接 ID（如 7、8 等）入库逻辑；创建新记录不再使用临时 ID
- 优化断开连接的离线标记：优先使用连接期映射的数据库主键（db_client_id），避免误更新
- 优化 Client.find_or_create_by_fingerprint 方法：
  - 无 device_fingerprint 时不创建记录并返回 None
  - 更新现有记录时不修改 device_fingerprint 与 client_id
  - 创建新记录时忽略外部传入的 client_id，统一生成稳定 UUID
- 增强日志与错误处理：连接、更新、离线过程输出明确日志，便于排查

注意：更新后需重启服务使新逻辑生效；建议清空 clients 表后重新验证。

### v1.3.0
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

## 任务总结（连接码模块与前端修复）

本次工作围绕“连接码（Connect Code）”模块的后端完善与前端集成修复展开，并完成端到端联调与验证，具体如下：

- 后端模块
  - 路由蓝图与接口：connect_code 蓝图使用前缀 `/api/connect-codes`，提供以下接口：
    - `POST /api/connect-codes/user/rotate`（需登录）：为当前用户重置连接码并返回明文与时间戳
    - `POST /api/connect-codes/guest/ensure`：为访客会话创建占位连接码并下发 `guest_session_id` Cookie
    - `POST /api/connect-codes/guest/rotate`：为当前访客会话重置连接码并返回明文与时间戳
  - 未登录处理：统一由 LoginManager 的 `unauthorized_handler` 返回 401 JSON 响应，前端可感知并提示登录
  - 模型与数据库：
    - ConnectCode 字段完善：`code_hash`、`code_type`（user/guest）、`user_id`（FK）、`guest_session_id`、`is_active`、`last_rotated_at`、`last_used_at`
    - Client 外键：`connect_code_id` 指向 `connect_codes.id`，用于在 TCP 连接期绑定客户端到连接码
    - 迁移文件：`92bda8901d26_add_connect_code.py` 定义表结构与索引
    - SQLite 兼容：在 `create_app` 中执行 `ensure_client_columns` 与 `ensure_connect_code_table` 以保证列/表存在
  - TCP 服务器集成：
    - 握手阶段校验 `connection_code`，使用 `check_password_hash` 与数据库中的 `ConnectCode` 进行校验
    - 校验通过后持久化 `client.connect_code_id`，并在会话活跃时更新 `ConnectCode.last_used_at`
  - 客户端与访客清理：
    - 在 `app/__init__.py` 启动 `start_guest_cleanup` 守护线程
    - `tasks/cleanup_worker.py` 定期清理过期访客连接码与孤立客户端，依据 `last_used_at` 与 `is_active`

- 前端集成与修复
  - 个人信息-安全设置集成“连接码管理”模块：支持重置、显示与复制明文连接码
  - 修复 API 路径错误：将前端调用从 `/api/connect_code/rotate` 更正为 `/api/connect-codes/user/rotate`，解决 404 问题
  - 在“客户端下载”页面新增提示文案，提升指引性

- 联调与验证
  - 启动 Flask 开发服务器，在 `/profile/` 与 `/client_download` 页面验证连接码管理与提示展示，无报错
  - 终端日志确认 TCP 端口监听与开发环境提示正常输出

- 接口速查
  - `POST /api/connect-codes/user/rotate`
  - `POST /api/connect-codes/guest/ensure`
  - `POST /api/connect-codes/guest/rotate`

- 生产化建议（可选优化）
  - 将访客 Cookie 的 `secure=True` 并启用 HTTPS
  - 用户连接码增加历史审计与可视化
  - 管理员工具：连接码失效策略、批量清理与监控面板
  - 对访客连接码设置更严格的过期与速率限制
