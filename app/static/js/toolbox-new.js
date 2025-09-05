// 工具箱管理器 - 新版本
class ToolboxManager {
  constructor() {
    this.socket = io();
    this.connections = [];
    this.activeConnection = null;
    this.terminal = null;
    this.fitAddon = null;
    this.currentConnectionType = null;
    
    this.init();
  }

  init() {
    this.setupSocketEvents();
    this.loadConnections();
    this.setupFormHandlers();
    this.setupEventListeners();
  }

  setupSocketEvents() {
    this.socket.on('connect', () => {
      console.log('已连接到服务器');
    });

    this.socket.on('disconnect', () => {
      console.log('与服务器断开连接');
    });

    // SSH 事件
    this.socket.on('ssh_connected', (data) => {
      this.updateConnectionStatus(data.session_id, 'online');
      if (this.terminal) {
        this.terminal.writeln('\x1b[1;32mSSH连接成功建立\x1b[0m');
      }
    });

    this.socket.on('ssh_output', (data) => {
      if (this.terminal) {
        this.terminal.write(data.data);
      }
    });

    this.socket.on('ssh_error', (data) => {
      this.updateConnectionStatus(data.session_id, 'offline');
      if (this.terminal) {
        this.terminal.writeln(`\x1b[1;31m连接错误: ${data.error}\x1b[0m`);
      }
    });

    this.socket.on('ssh_closed', (data) => {
      this.updateConnectionStatus(data.session_id, 'offline');
      if (this.terminal) {
        this.terminal.writeln('\x1b[1;31m\r\nSSH连接已关闭\x1b[0m');
      }
    });

    // SFTP 事件
    this.socket.on('sftp_connected', (data) => {
      this.updateConnectionStatus(data.session_id, 'online');
      this.updateSFTPStatus('已连接');
      this.refreshFileList(data.session_id);
    });

    this.socket.on('sftp_list_result', (data) => {
      this.updateRemoteFileList(data.list || [], data.path);
    });

    this.socket.on('sftp_error', (data) => {
      this.updateConnectionStatus(data.session_id, 'offline');
      this.updateSFTPStatus('连接失败');
      console.error('SFTP错误:', data.error);
      this.showError('SFTP错误', data.error);
    });

    this.socket.on('sftp_upload_success', (data) => {
      this.showSuccess('文件上传成功');
      this.refreshFileList(data.session_id);
    });
  }

  setupEventListeners() {
    // 连接类型选择事件
    document.getElementById('connectionType')?.addEventListener('change', (e) => {
      this.updatePortByType(e.target.value);
    });
  }

  setupFormHandlers() {
    const form = document.getElementById('connectionForm');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        this.createConnection();
      });
    }
  }

  async loadConnections() {
    try {
      const response = await fetch('/api/connections');
      const data = await response.json();
      this.connections = data.connections || [];
      this.renderConnections();
    } catch (error) {
      console.error('加载连接失败:', error);
    }
  }

  renderConnections() {
    const container = document.getElementById('connectionsList');
    if (!container) return;

    if (this.connections.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <i class='bx bx-link-alt'></i>
          <h4>暂无连接</h4>
          <p>点击"新建"按钮创建第一个连接</p>
        </div>
      `;
      return;
    }

    // 按类型分组
    const groups = this.groupConnectionsByType();
    
    container.innerHTML = '';
    
    Object.entries(groups).forEach(([type, connections]) => {
      const groupElement = this.createConnectionGroup(type, connections);
      container.appendChild(groupElement);
    });
  }

  groupConnectionsByType() {
    const groups = {};
    this.connections.forEach(connection => {
      if (!groups[connection.type]) {
        groups[connection.type] = [];
      }
      groups[connection.type].push(connection);
    });
    return groups;
  }

  createConnectionGroup(type, connections) {
    const groupDiv = document.createElement('div');
    groupDiv.className = 'connection-group';
    
    const typeNames = {
      ssh: 'SSH终端',
      sftp: 'SFTP传输',
      vnc: 'VNC桌面',
      rdp: 'RDP桌面'
    };
    
    const typeIcons = {
      ssh: 'bx-terminal',
      sftp: 'bx-transfer',
      vnc: 'bx-desktop',
      rdp: 'bx-laptop'
    };

    groupDiv.innerHTML = `
      <div class="group-header">
        <span>
          <i class='bx ${typeIcons[type]}'></i>
          ${typeNames[type]}
        </span>
        <span class="group-count">${connections.length}</span>
      </div>
    `;

    connections.forEach(connection => {
      const itemElement = this.createConnectionItem(connection);
      groupDiv.appendChild(itemElement);
    });

    return groupDiv;
  }

  createConnectionItem(connection) {
    const itemDiv = document.createElement('div');
    itemDiv.className = 'connection-item';
    itemDiv.dataset.connectionId = connection.id;
    
    const typeIcons = {
      ssh: 'bx-terminal',
      sftp: 'bx-transfer',
      vnc: 'bx-desktop',
      rdp: 'bx-laptop'
    };

    const statusClass = connection.last_connected ? 'status-online' : 'status-offline';
    
    itemDiv.innerHTML = `
      <div class="connection-icon">
        <i class='bx ${typeIcons[connection.type]}'></i>
      </div>
      <div class="connection-info">
        <div class="connection-name">${connection.name}</div>
        <div class="connection-details">${connection.host}:${connection.port}</div>
      </div>
      <div class="connection-status ${statusClass}"></div>
    `;

    itemDiv.addEventListener('click', () => {
      this.selectConnection(connection);
    });

    // 右键菜单
    itemDiv.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      this.showConnectionContextMenu(e, connection);
    });

    return itemDiv;
  }

  selectConnection(connection) {
    // 移除之前的选中状态
    document.querySelectorAll('.connection-item').forEach(item => {
      item.classList.remove('active');
    });

    // 添加选中状态
    const itemElement = document.querySelector(`[data-connection-id="${connection.id}"]`);
    if (itemElement) {
      itemElement.classList.add('active');
    }

    this.activeConnection = connection;
    this.showConnectionDetail(connection);
  }

  showConnectionDetail(connection) {
    const header = document.getElementById('contentHeader');
    const body = document.getElementById('contentBody');
    const welcomeContent = document.getElementById('welcomeContent');
    const connectionDetail = document.getElementById('connectionDetail');
    const terminalWindow = document.getElementById('terminalWindow');

    // 隐藏欢迎页面
    if (welcomeContent) welcomeContent.style.display = 'none';
    if (connectionDetail) connectionDetail.style.display = 'none';
    if (terminalWindow) terminalWindow.style.display = 'none';

    // 更新头部信息
    const typeNames = {
      ssh: 'SSH终端',
      sftp: 'SFTP传输',
      vnc: 'VNC桌面',
      rdp: 'RDP桌面'
    };

    const typeIcons = {
      ssh: 'bx-terminal',
      sftp: 'bx-transfer',
      vnc: 'bx-desktop',
      rdp: 'bx-laptop'
    };

    header.innerHTML = `
      <h2 class="content-title">
        <i class='bx ${typeIcons[connection.type]}'></i>
        ${connection.name}
      </h2>
      <p class="content-subtitle">${connection.host}:${connection.port} - ${typeNames[connection.type]}</p>
    `;

    // 显示连接详情
    connectionDetail.style.display = 'block';
    connectionDetail.innerHTML = this.createConnectionDetailContent(connection);
  }

  createConnectionDetailContent(connection) {
    const lastConnected = connection.last_connected 
      ? new Date(connection.last_connected).toLocaleString() 
      : '从未连接';
    
    const createdDate = new Date(connection.created_at).toLocaleString();

    return `
      <div class="connection-form sftp-manager">
        <div class="form-section">
          <h4 class="section-title">
            <i class='bx bx-info-circle'></i>
            连接信息
          </h4>
          
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">连接名称</label>
              <input type="text" class="form-control" value="${connection.name}" readonly>
            </div>
            <div class="form-group">
              <label class="form-label">连接类型</label>
              <input type="text" class="form-control" value="${connection.type.toUpperCase()}" readonly>
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">主机地址</label>
              <input type="text" class="form-control" value="${connection.host}" readonly>
            </div>
            <div class="form-group">
              <label class="form-label">端口</label>
              <input type="text" class="form-control" value="${connection.port}" readonly>
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">用户名</label>
              <input type="text" class="form-control" value="${connection.username || '未设置'}" readonly>
            </div>
            <div class="form-group">
              <label class="form-label">连接次数</label>
              <input type="text" class="form-control" value="${connection.connection_count || 0} 次" readonly>
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">最后连接</label>
              <input type="text" class="form-control" value="${lastConnected}" readonly>
            </div>
            <div class="form-group">
              <label class="form-label">创建时间</label>
              <input type="text" class="form-control" value="${createdDate}" readonly>
            </div>
          </div>
        </div>
        
        <div class="form-actions">
          <button class="btn btn-primary" onclick="toolboxManager.connectToServer('${connection.id}')">
            <i class='bx bx-link'></i>
            连接
          </button>
          <button class="btn btn-secondary" onclick="toolboxManager.editConnection('${connection.id}')">
            <i class='bx bx-edit'></i>
            编辑
          </button>
          <button class="btn btn-danger" onclick="toolboxManager.deleteConnection('${connection.id}')">
            <i class='bx bx-trash'></i>
            删除
          </button>
        </div>
      </div>
    `;
  }

  async connectToServer(connectionId) {
    const connection = this.connections.find(c => c.id === connectionId);
    if (!connection) return;

    try {
      const response = await fetch(`/api/connections/${connectionId}/connect`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      const data = await response.json();
      
      if (data.success) {
        this.updateConnectionStatus(connectionId, 'connecting');
        
        if (connection.type === 'ssh') {
          this.openSSHTerminal(connection, data.connection);
        } else if (connection.type === 'vnc') {
          window.open(data.redirect_url, '_blank');
        } else if (connection.type === 'rdp') {
          window.open(data.redirect_url, '_blank');
        } else if (connection.type === 'sftp') {
          this.openSFTPManager(connection, data.connection);
        }
      } else {
        this.showError('连接失败', data.error);
      }
    } catch (error) {
      console.error('连接错误:', error);
      this.showError('连接失败', '网络错误');
    }
  }

  openSSHTerminal(connection, connectionData) {
    const welcomeContent = document.getElementById('welcomeContent');
    const connectionDetail = document.getElementById('connectionDetail');
    const terminalWindow = document.getElementById('terminalWindow');
    const terminalTitle = document.getElementById('terminalTitle');

    // 隐藏其他内容
    if (welcomeContent) welcomeContent.style.display = 'none';
    if (connectionDetail) connectionDetail.style.display = 'none';
    terminalWindow.style.display = 'flex';

    // 更新终端标题
    terminalTitle.textContent = `${connection.name} - SSH终端`;

    // 初始化终端
    if (!this.terminal) {
      this.terminal = new Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: 'Consolas, Monaco, monospace',
        theme: {
          background: '#1e1e1e',
          foreground: '#ffffff'
        }
      });

      this.fitAddon = new FitAddon.FitAddon();
      this.terminal.loadAddon(this.fitAddon);
      
      const terminalElement = document.getElementById('terminal');
      this.terminal.open(terminalElement);
      
      setTimeout(() => {
        this.fitAddon.fit();
      }, 100);

      // 处理终端输入
      this.terminal.onData(data => {
        this.socket.emit('ssh_input', {
          session_id: connectionData.session_id,
          data: data
        });
      });
    }

    // 清空终端内容
    this.terminal.clear();
    this.terminal.writeln(`\x1b[1;36m正在连接到 ${connection.host}:${connection.port}...\x1b[0m`);
    
    // 建立SSH连接
    this.socket.emit('ssh_connect', {
      session_id: connectionData.session_id,
      host: connection.host,
      port: connection.port,
      username: connection.username,
      password: connection.password,
      cols: 80,
      rows: 24
    });
  }

  closeTerminal() {
    const terminalWindow = document.getElementById('terminalWindow');
    const welcomeContent = document.getElementById('welcomeContent');
    
    terminalWindow.style.display = 'none';
    welcomeContent.style.display = 'block';
    
    if (this.terminal) {
      this.terminal.dispose();
      this.terminal = null;
      this.fitAddon = null;
    }
  }

  openSFTPManager(connection, connectionData) {
    const welcomeContent = document.getElementById('welcomeContent');
    const connectionDetail = document.getElementById('connectionDetail');
    const terminalWindow = document.getElementById('terminalWindow');
    const header = document.getElementById('contentHeader');

    // 隐藏其他内容
    if (welcomeContent) welcomeContent.style.display = 'none';
    if (connectionDetail) connectionDetail.style.display = 'none';
    if (terminalWindow) terminalWindow.style.display = 'none';

    // 更新头部信息
    header.innerHTML = `
      <h2 class="content-title">
        <i class='bx bx-transfer'></i>
        ${connection.name} - SFTP文件管理
      </h2>
      <p class="content-subtitle">${connection.host}:${connection.port} - SFTP传输</p>
    `;

    // 显示SFTP管理器
    connectionDetail.style.display = 'block';
    connectionDetail.innerHTML = this.createSFTPManagerContent(connection, connectionData);

    // 建立SFTP连接
    this.socket.emit('sftp_connect', {
      session_id: connectionData.session_id,
      host: connection.host,
      port: connection.port,
      username: connection.username,
      password: connection.password
    });
  }

  createSFTPManagerContent(connection, connectionData) {
    return `
      <div class="connection-form">
        <div class="form-section">
          <h4 class="section-title">
            <i class='bx bx-folder-open'></i>
            SFTP文件管理
          </h4>
          
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">当前路径</label>
              <input type="text" class="form-control" id="currentPath" value="/" readonly>
            </div>
            <div class="form-group">
              <label class="form-label">连接状态</label>
              <input type="text" class="form-control" id="sftpStatus" value="连接中..." readonly>
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">远程文件列表</label>
              <div id="remoteFileList" class="form-control sftp-file-list" style="height: 400px; overflow-y: auto; background: var(--light-bg); padding: 1rem;">
                <div class="text-center text-muted">正在加载文件列表...</div>
              </div>
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">本地文件</label>
              <input type="file" class="form-control" id="localFile" multiple>
            </div>
            <div class="form-group">
              <label class="form-label">操作</label>
              <div class="d-flex gap-2">
                <button class="btn btn-primary" onclick="toolboxManager.uploadFile('${connectionData.session_id}')">
                  <i class='bx bx-upload'></i> 上传
                </button>
                <button class="btn btn-secondary" onclick="toolboxManager.refreshFileList('${connectionData.session_id}')">
                  <i class='bx bx-refresh'></i> 刷新
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  updateConnectionStatus(connectionId, status) {
    const itemElement = document.querySelector(`[data-connection-id="${connectionId}"]`);
    if (itemElement) {
      const statusElement = itemElement.querySelector('.connection-status');
      if (statusElement) {
        statusElement.className = `connection-status status-${status}`;
      }
    }
  }

  showConnectionContextMenu(event, connection) {
    // 创建右键菜单
    const menu = document.createElement('div');
    menu.className = 'context-menu';
    menu.style.cssText = `
      position: fixed;
      top: ${event.clientY}px;
      left: ${event.clientX}px;
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      box-shadow: var(--shadow-lg);
      z-index: 1000;
      min-width: 150px;
    `;

    menu.innerHTML = `
      <div class="menu-item" onclick="toolboxManager.connectToServer('${connection.id}')">
        <i class='bx bx-link'></i> 连接
      </div>
      <div class="menu-item" onclick="toolboxManager.editConnection('${connection.id}')">
        <i class='bx bx-edit'></i> 编辑
      </div>
      <div class="menu-item" onclick="toolboxManager.duplicateConnection('${connection.id}')">
        <i class='bx bx-copy'></i> 复制
      </div>
      <div class="menu-item" onclick="toolboxManager.deleteConnection('${connection.id}')">
        <i class='bx bx-trash'></i> 删除
      </div>
    `;

    document.body.appendChild(menu);

    // 点击其他地方关闭菜单
    const closeMenu = () => {
      document.body.removeChild(menu);
      document.removeEventListener('click', closeMenu);
    };

    setTimeout(() => {
      document.addEventListener('click', closeMenu);
    }, 100);
  }

  async createConnection() {
    const formData = {
      name: document.getElementById('connectionName').value,
      type: document.getElementById('connectionType').value,
      host: document.getElementById('connectionHost').value,
      port: parseInt(document.getElementById('connectionPort').value),
      username: document.getElementById('connectionUsername').value,
      password: document.getElementById('connectionPassword').value
    };

    try {
      const response = await fetch('/api/connections', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });

      const data = await response.json();
      
      if (data.success) {
        this.hideConnectionModal();
        this.loadConnections();
        this.showSuccess('连接创建成功');
      } else {
        this.showError('创建失败', data.error);
      }
    } catch (error) {
      console.error('创建连接错误:', error);
      this.showError('创建失败', '网络错误');
    }
  }

  async deleteConnection(connectionId) {
    if (!confirm('确定要删除这个连接吗？')) return;

    try {
      const response = await fetch(`/api/connections/${connectionId}`, {
        method: 'DELETE'
      });

      const data = await response.json();
      
      if (data.success) {
        this.loadConnections();
        this.showSuccess('连接删除成功');
        
        // 如果删除的是当前选中的连接，显示欢迎页面
        if (this.activeConnection && this.activeConnection.id === connectionId) {
          this.showWelcomePage();
        }
      } else {
        this.showError('删除失败', data.error);
      }
    } catch (error) {
      console.error('删除连接错误:', error);
      this.showError('删除失败', '网络错误');
    }
  }

  editConnection(connectionId) {
    const connection = this.connections.find(c => c.id === connectionId);
    if (!connection) return;

    // 填充表单
    document.getElementById('connectionName').value = connection.name;
    document.getElementById('connectionType').value = connection.type;
    document.getElementById('connectionHost').value = connection.host;
    document.getElementById('connectionPort').value = connection.port;
    document.getElementById('connectionUsername').value = connection.username || '';
    document.getElementById('connectionPassword').value = connection.password || '';

    // 显示模态框
    this.showConnectionModal();
  }

  duplicateConnection(connectionId) {
    const connection = this.connections.find(c => c.id === connectionId);
    if (!connection) return;

    // 创建副本
    const duplicate = {
      ...connection,
      name: `${connection.name} (副本)`,
      id: undefined,
      created_at: new Date().toISOString(),
      last_connected: null,
      connection_count: 0
    };

    // 填充表单
    document.getElementById('connectionName').value = duplicate.name;
    document.getElementById('connectionType').value = duplicate.type;
    document.getElementById('connectionHost').value = duplicate.host;
    document.getElementById('connectionPort').value = duplicate.port;
    document.getElementById('connectionUsername').value = duplicate.username || '';
    document.getElementById('connectionPassword').value = duplicate.password || '';

    // 显示模态框
    this.showConnectionModal();
  }

  showWelcomePage() {
    const welcomeContent = document.getElementById('welcomeContent');
    const connectionDetail = document.getElementById('connectionDetail');
    const terminalWindow = document.getElementById('terminalWindow');
    const header = document.getElementById('contentHeader');

    // 显示欢迎页面
    welcomeContent.style.display = 'block';
    connectionDetail.style.display = 'none';
    terminalWindow.style.display = 'none';

    // 重置头部
    header.innerHTML = `
      <h2 class="content-title">
        <i class='bx bx-home'></i>
        欢迎使用工具箱
      </h2>
      <p class="content-subtitle">选择左侧连接或使用下方工具开始工作</p>
    `;

    // 移除选中状态
    document.querySelectorAll('.connection-item').forEach(item => {
      item.classList.remove('active');
    });

    this.activeConnection = null;
  }

  updatePortByType(type) {
    const portInput = document.getElementById('connectionPort');
    const defaultPorts = {
      ssh: 22,
      sftp: 22,
      vnc: 5900,
      rdp: 3389
    };

    if (type && defaultPorts[type]) {
      portInput.value = defaultPorts[type];
    }
  }

  showConnectionModal(type = null) {
    const modal = document.getElementById('connectionModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalSubtitle = document.getElementById('modalSubtitle');
    const typeSelect = document.getElementById('connectionType');

    if (type) {
      typeSelect.value = type;
      this.updatePortByType(type);
      
      // 根据连接类型更新标题和描述
      const typeInfo = {
        'ssh': { 
          title: '创建SSH连接', 
          subtitle: '安全Shell连接，用于远程命令行操作和管理' 
        },
        'sftp': { 
          title: '创建SFTP连接', 
          subtitle: '安全文件传输协议，用于远程文件上传下载' 
        },
        'vnc': { 
          title: '创建VNC连接', 
          subtitle: '虚拟网络计算，用于远程桌面图形界面访问' 
        },
        'rdp': { 
          title: '创建RDP连接', 
          subtitle: 'Windows远程桌面协议，用于Windows系统远程访问' 
        }
      };
      
      if (typeInfo[type]) {
        modalTitle.textContent = typeInfo[type].title;
        modalSubtitle.textContent = typeInfo[type].subtitle;
      }
    } else {
      modalTitle.textContent = '创建新连接';
      modalSubtitle.textContent = '选择连接类型并填写相关信息以创建新的远程连接';
    }

    modal.style.display = 'flex';
    setTimeout(() => modal.classList.add('active'), 10);
  }

  hideConnectionModal() {
    const modal = document.getElementById('connectionModal');
    modal.classList.remove('active');
    setTimeout(() => modal.style.display = 'none', 300);
    
    // 清空表单
    document.getElementById('connectionForm').reset();
  }
  
  toggleAdvancedOptions() {
    const advancedSection = document.querySelector('.advanced-options');
    const toggleBtn = document.querySelector('.btn-outline-secondary');
    
    if (advancedSection.style.display === 'none') {
      advancedSection.style.display = 'block';
      toggleBtn.innerHTML = '<i class="bx bx-chevron-up"></i> 隐藏高级选项';
    } else {
      advancedSection.style.display = 'none';
      toggleBtn.innerHTML = '<i class="bx bx-cog"></i> 高级选项';
    }
  }

  async refreshConnections() {
    await this.loadConnections();
    this.showSuccess('连接列表已刷新');
  }

  showSuccess(message) {
    this.showNotification(message, 'success');
  }

  showError(title, message) {
    this.showNotification(`${title}: ${message}`, 'error');
  }

  showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 1rem 1.5rem;
      border-radius: var(--radius-md);
      color: white;
      font-weight: 500;
      z-index: 10000;
      max-width: 300px;
      box-shadow: var(--shadow-lg);
    `;

    const bgColor = type === 'success' ? 'var(--success-color)' : 
                   type === 'error' ? 'var(--danger-color)' : 
                   'var(--info-color)';
    
    notification.style.background = bgColor;
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
      notification.style.opacity = '0';
      notification.style.transform = 'translateX(100%)';
      setTimeout(() => {
        document.body.removeChild(notification);
      }, 300);
    }, 3000);
  }

  // SFTP相关方法
  updateSFTPStatus(status) {
    const statusInput = document.getElementById('sftpStatus');
    if (statusInput) {
      statusInput.value = status;
    }
  }

  updateRemoteFileList(files, path) {
    const fileListDiv = document.getElementById('remoteFileList');
    const currentPathInput = document.getElementById('currentPath');
    
    if (currentPathInput) {
      currentPathInput.value = path;
    }
    
    if (fileListDiv) {
      if (files.length === 0) {
        fileListDiv.innerHTML = '<div class="text-center text-muted">当前目录为空</div>';
        return;
      }
      
      let html = '<div class="d-flex flex-column gap-2">';
      files.forEach(file => {
        const icon = file.is_dir ? 'bx-folder' : 'bx-file';
        const size = file.is_dir ? '-' : this.formatFileSize(file.size);
        const date = new Date(file.mtime * 1000).toLocaleString();
        
        html += `
          <div class="d-flex align-items-center gap-2 p-2 border rounded">
            <i class='bx ${icon} text-primary'></i>
            <span class="flex-grow-1">${file.name}</span>
            <small class="text-muted">${size}</small>
            <small class="text-muted">${date}</small>
          </div>
        `;
      });
      html += '</div>';
      fileListDiv.innerHTML = html;
    }
  }

  formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  refreshFileList(sessionId) {
    this.socket.emit('sftp_list', {
      session_id: sessionId,
      path: document.getElementById('currentPath')?.value || '.'
    });
  }

  uploadFile(sessionId) {
    const fileInput = document.getElementById('localFile');
    if (!fileInput.files.length) {
      this.showError('请选择要上传的文件');
      return;
    }

    const file = fileInput.files[0];
    const reader = new FileReader();
    reader.onload = (e) => {
      this.socket.emit('sftp_upload', {
        session_id: sessionId,
        path: `/${file.name}`,
        file_data: e.target.result
      });
    };
    reader.readAsArrayBuffer(file);
  }
}

// 全局变量
let toolboxManager;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
  toolboxManager = new ToolboxManager();
});

// 全局函数
function showConnectionModal(type = null) {
  toolboxManager.showConnectionModal(type);
}

function hideConnectionModal() {
  toolboxManager.hideConnectionModal();
}

function toggleAdvancedOptions() {
  toolboxManager.toggleAdvancedOptions();
}

function refreshConnections() {
  toolboxManager.refreshConnections();
}

function closeTerminal() {
  toolboxManager.closeTerminal();
}

// 添加CSS样式
const style = document.createElement('style');
style.textContent = `
.context-menu {
  animation: slideIn 0.2s ease-out;
}

.menu-item {
  padding: 0.75rem 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: var(--transition);
}

.menu-item:hover {
  background: var(--light-bg);
}

.menu-item:first-child {
  border-radius: var(--radius-md) var(--radius-md) 0 0;
}

.menu-item:last-child {
  border-radius: 0 0 var(--radius-md) var(--radius-md);
}

.notification {
  transition: all 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
`;

document.head.appendChild(style);
