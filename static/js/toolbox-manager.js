// 工具箱管理器 - 独立文件
class ToolboxManager {
  constructor() {
    this.socket = io();
    this.windows = new Map();
    this.activeWindowId = null;
    this.windowCounter = 0;
    this.currentConnectionType = null;
    
    this.init();
  }

  init() {
    this.setupSocketEvents();
    this.loadConnections();
    this.setupFormHandlers();
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
      const window = this.findWindowBySessionId(data.session_id);
      if (window) {
        window.updateConnectionStatus('已连接', true);
        window.updateTabTitle();
        if (window.terminal) {
          window.terminal.writeln('\x1b[1;32mSSH连接成功建立\x1b[0m');
        }
      }
    });

    this.socket.on('ssh_output', (data) => {
      const window = this.findWindowBySessionId(data.session_id);
      if (window && window.terminal) {
        window.terminal.write(data.data);
      }
    });

    this.socket.on('ssh_error', (data) => {
      const window = this.findWindowBySessionId(data.session_id);
      if (window) {
        window.updateConnectionStatus('连接失败', false);
        if (window.terminal) {
          window.terminal.writeln(`\x1b[1;31m连接错误: ${data.error}\x1b[0m`);
        }
      }
    });

    this.socket.on('ssh_closed', (data) => {
      const window = this.findWindowBySessionId(data.session_id);
      if (window) {
        window.updateConnectionStatus('未连接', false);
        window.updateTabTitle();
        if (window.terminal) {
          window.terminal.writeln('\x1b[1;31m\r\nSSH连接已关闭\x1b[0m');
        }
      }
    });

    // SFTP 事件
    this.socket.on('sftp_connected', (data) => {
      const window = this.findWindowBySessionId(data.session_id);
      if (window) {
        window.sftpConnected = true;
        window.updateConnectionStatus('已连接', true);
        window.refreshRemoteFiles();
      }
    });

    this.socket.on('sftp_list_result', (data) => {
      const window = this.findWindowBySessionId(data.session_id);
      if (window) {
        window.updateRemoteFiles(data.list || [], data.path);
      }
    });

    this.socket.on('sftp_error', (data) => {
      const window = this.findWindowBySessionId(data.session_id);
      if (window) {
        console.error('SFTP错误:', data.error);
        window.updateConnectionStatus('连接失败', false);
      }
    });
  }

  findWindowBySessionId(sessionId) {
    for (const window of this.windows.values()) {
      if (window.sessionId === sessionId) {
        return window;
      }
    }
    return null;
  }

  createWindow(type, connectionData = null) {
    const windowId = `window_${++this.windowCounter}`;
    const window = new ToolboxWindow(windowId, type, this, connectionData);
    this.windows.set(windowId, window);
    
    this.showWindowInterface();
    this.renderTabs();
    this.renderContent();
    this.switchToWindow(windowId);
    
    return window;
  }

  removeWindow(windowId) {
    const window = this.windows.get(windowId);
    if (window) {
      window.cleanup();
      this.windows.delete(windowId);
      
      if (this.activeWindowId === windowId) {
        const remainingWindows = Array.from(this.windows.keys());
        if (remainingWindows.length > 0) {
          this.switchToWindow(remainingWindows[0]);
        } else {
          this.activeWindowId = null;
          this.hideWindowInterface();
        }
      }
      
      this.renderTabs();
      this.renderContent();
    }
  }

  switchToWindow(windowId) {
    this.activeWindowId = windowId;
    this.renderTabs();
    this.renderContent();
    
    const window = this.windows.get(windowId);
    if (window && window.terminal && window.fitAddon) {
      setTimeout(() => {
        window.fitAddon.fit();
      }, 100);
    }
  }

  showWindowInterface() {
    document.getElementById('tabs-header').style.display = 'flex';
    document.getElementById('window-content').style.display = 'flex';
  }

  hideWindowInterface() {
    document.getElementById('tabs-header').style.display = 'none';
    document.getElementById('window-content').style.display = 'none';
  }

  renderTabs() {
    const container = document.getElementById('window-tabs');
    container.innerHTML = '';
    
    for (const [windowId, window] of this.windows) {
      const tab = document.createElement('div');
      tab.className = `window-tab ${windowId === this.activeWindowId ? 'active' : ''}`;
      tab.onclick = () => this.switchToWindow(windowId);
      
      const icon = this.getTypeIcon(window.type);
      tab.innerHTML = `
        <i class='bx ${icon}'></i>
        <span>${window.getDisplayName()}</span>
        <button class="close-btn" onclick="event.stopPropagation(); toolboxManager.removeWindow('${windowId}')">
          ×
        </button>
      `;
      
      container.appendChild(tab);
    }
  }

  renderContent() {
    const container = document.getElementById('window-content');
    container.innerHTML = '';
    
    for (const [windowId, window] of this.windows) {
      const panel = window.render();
      panel.className = `window-panel ${windowId === this.activeWindowId ? 'active' : ''}`;
      container.appendChild(panel);
    }
  }

  getTypeIcon(type) {
    const icons = {
      ssh: 'bx-terminal',
      vnc: 'bx-desktop',
      rdp: 'bx-laptop',
      sftp: 'bx-transfer'
    };
    return icons[type] || 'bx-terminal';
  }

  // 连接历史相关方法
  loadConnections() {
    fetch('/api/connections')
      .then(response => response.json())
      .then(data => {
        this.displayConnections(data.connections);
      })
      .catch(error => {
        console.error('加载连接失败:', error);
      });
  }

  displayConnections(connections) {
    const container = document.getElementById('quick-connections');
    const emptyState = document.getElementById('empty-connections');
    
    if (connections.length === 0) {
      container.style.display = 'none';
      emptyState.style.display = 'block';
      return;
    }
    
    container.style.display = 'grid';
    emptyState.style.display = 'none';
    
    container.innerHTML = connections.map(conn => `
      <div class="connection-card" onclick="toolboxManager.quickConnect('${conn.id}')">
        <div class="connection-header">
          <h5 class="connection-name">${conn.name}</h5>
          <span class="connection-type ${conn.type}">${conn.type.toUpperCase()}</span>
        </div>
        <div class="connection-details">
          <i class='bx bx-server'></i> ${conn.host}:${conn.port}
          ${conn.username ? `<br><i class='bx bx-user'></i> ${conn.username}` : ''}
        </div>
        <div class="connection-stats">
          <span>连接次数: ${conn.connection_count}</span>
          <button class="btn btn-outline-danger btn-sm" onclick="event.stopPropagation(); toolboxManager.deleteConnection('${conn.id}')">
            <i class='bx bx-trash'></i>
          </button>
        </div>
      </div>
    `).join('');
  }

  quickConnect(connectionId) {
    fetch(`/api/connections/${connectionId}/connect`, {
      method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        // 在当前页面创建新窗口
        this.createWindow(data.connection.type, data.connection);
      } else {
        alert('连接失败: ' + data.error);
      }
    })
    .catch(error => {
      console.error('连接失败:', error);
      alert('连接失败');
    });
  }

  deleteConnection(connectionId) {
    if (confirm('确定要删除这个连接吗？')) {
      fetch(`/api/connections/${connectionId}`, {
        method: 'DELETE'
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          this.loadConnections();
        } else {
          alert('删除失败: ' + data.error);
        }
      })
      .catch(error => {
        console.error('删除失败:', error);
        alert('删除失败');
      });
    }
  }

  // 弹窗相关方法
  showConnectionModal(type) {
    this.currentConnectionType = type;
    const modal = document.getElementById('connectionModal');
    const title = document.getElementById('modalTitle');
    const subtitle = document.getElementById('modalSubtitle');
    const portInput = document.getElementById('connectionPort');
    
    const toolInfo = {
      'ssh': { name: 'SSH连接', desc: '安全Shell连接', port: 22 },
      'sftp': { name: 'SFTP传输', desc: '安全文件传输', port: 22 },
      'vnc': { name: 'VNC远程桌面', desc: '虚拟网络计算', port: 5900 },
      'rdp': { name: 'RDP远程桌面', desc: 'Windows远程桌面', port: 3389 }
    };
    
    const info = toolInfo[type];
    title.textContent = info.name;
    subtitle.textContent = info.desc;
    portInput.value = info.port;
    
    const form = document.getElementById('connectionForm');
    form.reset();
    portInput.value = info.port;
    
    modal.classList.add('active');
    document.getElementById('connectionName').focus();
  }

  hideConnectionModal() {
    const modal = document.getElementById('connectionModal');
    modal.classList.remove('active');
    this.currentConnectionType = null;
  }

  showToolSelector() {
    const modal = document.getElementById('toolSelectorModal');
    modal.classList.add('active');
  }

  hideToolSelector() {
    const modal = document.getElementById('toolSelectorModal');
    modal.classList.remove('active');
  }

  setupFormHandlers() {
    const form = document.getElementById('connectionForm');
    
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      this.createConnection();
    });

    // 点击弹窗外部关闭
    document.getElementById('connectionModal').addEventListener('click', (e) => {
      if (e.target === e.currentTarget) {
        this.hideConnectionModal();
      }
    });

    document.getElementById('toolSelectorModal').addEventListener('click', (e) => {
      if (e.target === e.currentTarget) {
        this.hideToolSelector();
      }
    });
  }

  createConnection() {
    const formData = {
      name: document.getElementById('connectionName').value,
      type: this.currentConnectionType,
      host: document.getElementById('connectionHost').value,
      port: parseInt(document.getElementById('connectionPort').value),
      username: document.getElementById('connectionUsername').value,
      password: document.getElementById('connectionPassword').value
    };
    
    fetch('/api/connections', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        this.hideConnectionModal();
        this.loadConnections();
        
        // 创建新窗口并连接
        this.createWindow(this.currentConnectionType, data.connection);
      } else {
        alert('创建失败: ' + data.error);
      }
    })
    .catch(error => {
      console.error('创建连接失败:', error);
      alert('创建连接失败');
    });
  }

  clearAllConnections() {
    if (confirm('确定要清空所有连接吗？此操作不可恢复！')) {
      fetch('/api/connections/clear', {
        method: 'POST'
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          this.loadConnections();
        } else {
          alert('清空失败: ' + data.error);
        }
      })
      .catch(error => {
        console.error('清空失败:', error);
        alert('清空失败');
      });
    }
  }
}

// 工具箱窗口类
class ToolboxWindow {
  constructor(id, type, manager, connectionData = null) {
    this.id = id;
    this.type = type;
    this.manager = manager;
    this.sessionId = null;
    this.isConnected = false;
    this.terminal = null;
    this.fitAddon = null;
    this.remoteFiles = [];
    this.currentRemotePath = '.';
    this.connectionConfig = connectionData || {};
    this.sftpConnected = false;
    this.selectedFiles = [];
  }

  getDisplayName() {
    if (this.isConnected && this.connectionConfig.host) {
      const protocol = this.type.toUpperCase();
      const host = this.connectionConfig.host;
      const port = this.connectionConfig.port;
      return `${protocol} ${host}:${port}`;
    }
    return `新窗口 ${this.id.split('_')[1]}`;
  }

  updateTabTitle() {
    this.manager.renderTabs();
  }

  render() {
    const panel = document.createElement('div');
    panel.id = `panel_${this.id}`;
    
    if (this.type === 'ssh') {
      panel.innerHTML = this.renderSSHContent();
      setTimeout(() => this.initializeSSH(), 100);
    } else if (this.type === 'sftp') {
      panel.innerHTML = this.renderSFTPContent();
      setTimeout(() => this.initializeSFTP(), 100);
    } else if (this.type === 'vnc') {
      panel.innerHTML = this.renderVNCContent();
      setTimeout(() => this.initializeVNC(), 100);
    } else if (this.type === 'rdp') {
      panel.innerHTML = this.renderRDPContent();
      setTimeout(() => this.initializeRDP(), 100);
    }
    
    return panel;
  }

  renderSSHContent() {
    return `
      <div class="ssh-container" style="display: flex; flex-direction: column; height: 100%; gap: 1rem; padding: 1rem;">
        <!-- 连接配置面板 -->
        <div class="ssh-connection-panel" style="background: var(--card-bg); border-radius: var(--radius-lg); padding: 1rem; box-shadow: var(--shadow-sm); border: 1px solid var(--border-color); flex-shrink: 0;">
          <form class="connection-form" id="form_${this.id}" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; align-items: end;">
            <div>
              <label class="form-label">服务器地址</label>
              <input type="text" id="host_${this.id}" class="form-control" placeholder="例如: 192.168.1.100" value="${this.connectionConfig.host || ''}" required>
            </div>
            <div>
              <label class="form-label">端口</label>
              <input type="number" id="port_${this.id}" class="form-control" value="${this.connectionConfig.port || 22}" min="1" max="65535">
            </div>
            <div>
              <label class="form-label">用户名</label>
              <input type="text" id="username_${this.id}" class="form-control" placeholder="用户名" value="${this.connectionConfig.username || ''}" required>
            </div>
            <div>
              <label class="form-label">密码</label>
              <input type="password" id="password_${this.id}" class="form-control" placeholder="密码" value="${this.connectionConfig.password || ''}">
            </div>
            <div>
              <button type="submit" class="btn btn-primary w-100" id="connect_${this.id}">
                <i class='bx bx-plug'></i>
                连接
              </button>
            </div>
          </form>
        </div>

        <!-- 终端容器 -->
        <div class="ssh-terminal-container" style="flex: 1; background: var(--card-bg); border-radius: var(--radius-lg); overflow: hidden; box-shadow: var(--shadow-sm); border: 1px solid var(--border-color); display: flex; flex-direction: column; min-height: 0;">
          <div class="terminal-header" style="background: linear-gradient(135deg, #333, #2a2a2a); color: white; padding: 0.75rem 1rem; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #444;">
            <div class="terminal-dots" style="display: flex; gap: 0.5rem;">
              <div class="terminal-dot red" style="width: 12px; height: 12px; border-radius: 50%; background: #ff5f56;"></div>
              <div class="terminal-dot yellow" style="width: 12px; height: 12px; border-radius: 50%; background: #ffbd2e;"></div>
              <div class="terminal-dot green" style="width: 12px; height: 12px; border-radius: 50%; background: #27ca3f;"></div>
            </div>
            <div class="terminal-title" style="font-size: 0.875rem; font-weight: 500;">SSH 终端</div>
            <div class="terminal-status" style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.75rem;">
              <div class="status-dot" id="status_dot_${this.id}" style="width: 8px; height: 8px; border-radius: 50%; background: var(--danger-color); animation: pulse 2s infinite;"></div>
              <span id="status_text_${this.id}">等待连接</span>
            </div>
          </div>
          <div id="terminal_${this.id}" style="flex: 1; background: #1e1e1e; min-height: 0;">
            <!-- xterm.js 终端将在这里初始化 -->
          </div>
        </div>
      </div>
    `;
  }

  renderSFTPContent() {
    return `
      <div class="sftp-container" style="display: flex; flex-direction: column; height: 100%; gap: 1rem; padding: 1rem;">
        <!-- 连接配置面板 -->
        <div style="background: var(--card-bg); border-radius: var(--radius-lg); padding: 1rem; box-shadow: var(--shadow-sm); border: 1px solid var(--border-color); flex-shrink: 0;">
          <form class="connection-form" id="form_${this.id}" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; align-items: end;">
            <div>
              <label class="form-label">服务器地址</label>
              <input type="text" id="host_${this.id}" class="form-control" placeholder="例如: 192.168.1.100" value="${this.connectionConfig.host || ''}" required>
            </div>
            <div>
              <label class="form-label">端口</label>
              <input type="number" id="port_${this.id}" class="form-control" value="${this.connectionConfig.port || 22}" min="1" max="65535">
            </div>
            <div>
              <label class="form-label">用户名</label>
              <input type="text" id="username_${this.id}" class="form-control" placeholder="用户名" value="${this.connectionConfig.username || ''}" required>
            </div>
            <div>
              <label class="form-label">密码</label>
              <input type="password" id="password_${this.id}" class="form-control" placeholder="密码" value="${this.connectionConfig.password || ''}" required>
            </div>
            <div>
              <button type="submit" class="btn btn-primary w-100" id="connect_${this.id}">
                <i class='bx bx-plug'></i>
                连接
              </button>
            </div>
          </form>
        </div>

        <!-- SFTP 内容区域 -->
        <div style="flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; min-height: 0;">
          <!-- 远程文件面板 -->
          <div style="background: var(--card-bg); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); border: 1px solid var(--border-color); display: flex; flex-direction: column; overflow: hidden;">
            <div style="background: linear-gradient(135deg, var(--primary-color), var(--primary-dark)); color: white; padding: 1rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem;">
              <i class='bx bx-server'></i>
              <span>远程文件</span>
              <div style="margin-left: auto;">
                <button class="btn btn-light btn-sm" onclick="toolboxManager.windows.get('${this.id}').refreshRemoteFiles()" disabled id="refresh_btn_${this.id}">
                  <i class='bx bx-refresh'></i>
                </button>
              </div>
            </div>
            <div style="flex: 1; overflow: auto;">
              <div id="remote_files_${this.id}">
                <div class="empty-state" style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 200px; color: var(--text-muted); text-align: center;">
                  <i class='bx bx-server' style="font-size: 3rem; margin-bottom: 1rem; opacity: 0.5;"></i>
                  <p>请先连接到SFTP服务器</p>
                </div>
              </div>
            </div>
          </div>

          <!-- 本地文件面板 -->
          <div style="background: var(--card-bg); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); border: 1px solid var(--border-color); display: flex; flex-direction: column; overflow: hidden;">
            <div style="background: linear-gradient(135deg, var(--primary-color), var(--primary-dark)); color: white; padding: 1rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem;">
              <i class='bx bx-desktop'></i>
              <span>本地文件</span>
              <div style="margin-left: auto;">
                <input type="file" id="file_input_${this.id}" multiple style="display: none;" onchange="toolboxManager.windows.get('${this.id}').handleFileSelect()">
                <button class="btn btn-light btn-sm" onclick="document.getElementById('file_input_${this.id}').click()">
                  <i class='bx bx-plus'></i>
                  选择文件
                </button>
              </div>
            </div>
            <div style="flex: 1; overflow: auto;">
              <div id="local_files_${this.id}">
                <div class="empty-state" style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 200px; color: var(--text-muted); text-align: center;">
                  <i class='bx bx-file-plus' style="font-size: 3rem; margin-bottom: 1rem; opacity: 0.5;"></i>
                  <p>点击上方按钮选择要上传的文件</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  renderVNCContent() {
    return `
      <div style="display: flex; flex-direction: column; height: 100%; gap: 1rem; padding: 1rem;">
        <form class="connection-form" id="form_${this.id}" style="background: var(--card-bg); border-radius: var(--radius-lg); padding: 1rem; box-shadow: var(--shadow-sm); border: 1px solid var(--border-color); display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; align-items: end; flex-shrink: 0;">
          <div>
            <label class="form-label">服务器地址</label>
            <input type="text" id="host_${this.id}" class="form-control" placeholder="例如: 192.168.1.100" value="${this.connectionConfig.host || ''}" required>
          </div>
          <div>
            <label class="form-label">端口</label>
            <input type="number" id="port_${this.id}" class="form-control" value="${this.connectionConfig.port || 5900}" min="1" max="65535">
          </div>
          <div>
            <button type="submit" class="btn btn-primary w-100" id="connect_${this.id}">
              <i class='bx bx-plug'></i>
              连接
            </button>
          </div>
        </form>

        <div style="flex: 1; display: flex; flex-direction: column; background: var(--card-bg); border-radius: var(--radius-lg); overflow: hidden; box-shadow: var(--shadow-sm); border: 1px solid var(--border-color);">
          <div style="background: linear-gradient(135deg, var(--primary-color), var(--primary-dark)); color: white; padding: 1rem; display: flex; align-items: center; gap: 0.75rem;">
            <i class='bx bx-desktop'></i>
            <span style="font-size: 1.1rem; font-weight: 600;">VNC 远程桌面</span>
          </div>
          <iframe class="viewer-frame" id="viewer_${this.id}" src="about:blank" style="flex: 1; border: none; background: #000; min-height: 400px;"></iframe>
        </div>
      </div>
    `;
  }

  renderRDPContent() {
    return `
      <div style="display: flex; flex-direction: column; height: 100%; gap: 1rem; padding: 1rem;">
        <form class="connection-form" id="form_${this.id}" style="background: var(--card-bg); border-radius: var(--radius-lg); padding: 1rem; box-shadow: var(--shadow-sm); border: 1px solid var(--border-color); display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; align-items: end; flex-shrink: 0;">
          <div>
            <label class="form-label">服务器地址</label>
            <input type="text" id="host_${this.id}" class="form-control" placeholder="例如: 192.168.1.100" value="${this.connectionConfig.host || ''}" required>
          </div>
          <div>
            <label class="form-label">端口</label>
            <input type="number" id="port_${this.id}" class="form-control" value="${this.connectionConfig.port || 3389}" min="1" max="65535">
          </div>
          <div>
            <label class="form-label">用户名</label>
            <input type="text" id="username_${this.id}" class="form-control" placeholder="用户名" value="${this.connectionConfig.username || ''}" required>
          </div>
          <div>
            <label class="form-label">密码</label>
            <input type="password" id="password_${this.id}" class="form-control" placeholder="密码" value="${this.connectionConfig.password || ''}" required>
          </div>
          <div>
            <button type="submit" class="btn btn-primary w-100" id="connect_${this.id}">
              <i class='bx bx-plug'></i>
              连接
            </button>
          </div>
        </form>

        <div style="flex: 1; display: flex; flex-direction: column; background: var(--card-bg); border-radius: var(--radius-lg); overflow: hidden; box-shadow: var(--shadow-sm); border: 1px solid var(--border-color);">
          <div style="background: linear-gradient(135deg, var(--primary-color), var(--primary-dark)); color: white; padding: 1rem; display: flex; align-items: center; gap: 0.75rem;">
            <i class='bx bx-laptop'></i>
            <span style="font-size: 1.1rem; font-weight: 600;">RDP 远程桌面</span>
          </div>
          <iframe class="viewer-frame" id="viewer_${this.id}" src="about:blank" style="flex: 1; border: none; background: #000; min-height: 400px;"></iframe>
        </div>
      </div>
    `;
  }

  initializeSSH() {
    // 初始化终端
    this.terminal = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace',
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#ffffff',
        selection: '#264f78'
      }
    });
    
    this.fitAddon = new FitAddon.FitAddon();
    this.terminal.loadAddon(this.fitAddon);
    
    const terminalElement = document.getElementById(`terminal_${this.id}`);
    this.terminal.open(terminalElement);
    this.fitAddon.fit();
    
    this.terminal.writeln('\x1b[1;32m欢迎使用 SSH 终端\x1b[0m');
    this.terminal.writeln('请配置连接信息并点击连接按钮开始使用。');
    this.terminal.writeln('');
    
    // 监听终端输入
    this.terminal.onData(data => {
      if (this.isConnected && this.sessionId) {
        this.manager.socket.emit('ssh_input', { session_id: this.sessionId, data: data });
      }
    });
    
    // 设置表单提交事件
    const form = document.getElementById(`form_${this.id}`);
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      this.connectSSH();
    });
    
    // 如果有连接配置，自动连接
    if (this.connectionConfig.host) {
      setTimeout(() => this.connectSSH(), 500);
    }
    
    // 监听窗口大小变化
    window.addEventListener('resize', () => {
      if (this.fitAddon && this.id === this.manager.activeWindowId) {
        this.fitAddon.fit();
        if (this.isConnected && this.sessionId) {
          this.manager.socket.emit('ssh_resize', {
            session_id: this.sessionId,
            cols: this.terminal.cols,
            rows: this.terminal.rows
          });
        }
      }
    });
  }

  initializeSFTP() {
    const form = document.getElementById(`form_${this.id}`);
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      this.connectSFTP();
    });
    
    // 如果有连接配置，自动连接
    if (this.connectionConfig.host) {
      setTimeout(() => this.connectSFTP(), 500);
    }
  }

  initializeVNC() {
    const form = document.getElementById(`form_${this.id}`);
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      this.connectVNC();
    });
    
    // 如果有连接配置，自动连接
    if (this.connectionConfig.host) {
      setTimeout(() => this.connectVNC(), 500);
    }
  }

  initializeRDP() {
    const form = document.getElementById(`form_${this.id}`);
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      this.connectRDP();
    });
    
    // 如果有连接配置，自动连接
    if (this.connectionConfig.host) {
      setTimeout(() => this.connectRDP(), 500);
    }
  }

  connectSSH() {
    const host = document.getElementById(`host_${this.id}`).value.trim();
    const port = parseInt(document.getElementById(`port_${this.id}`).value) || 22;
    const username = document.getElementById(`username_${this.id}`).value.trim();
    const password = document.getElementById(`password_${this.id}`).value;
    
    if (!host || !username) {
      alert('请填写服务器地址和用户名');
      return;
    }
    
    this.sessionId = `ssh_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    this.connectionConfig = { host, port, username, password };
    
    this.updateConnectionStatus('连接中', false);
    
    this.terminal.clear();
    this.terminal.writeln(`\x1b[1;33m正在连接到 ${username}@${host}:${port}...\x1b[0m`);
    
    this.manager.socket.emit('ssh_connect', {
      session_id: this.sessionId,
      host: host,
      port: port,
      username: username,
      password: password,
      cols: this.terminal.cols,
      rows: this.terminal.rows
    });
  }

  connectSFTP() {
    const host = document.getElementById(`host_${this.id}`).value.trim();
    const port = parseInt(document.getElementById(`port_${this.id}`).value) || 22;
    const username = document.getElementById(`username_${this.id}`).value.trim();
    const password = document.getElementById(`password_${this.id}`).value;
    
    if (!host || !username || !password) {
      alert('请填写完整的连接信息');
      return;
    }
    
    this.sessionId = `sftp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    this.connectionConfig = { host, port, username, password };
    
    this.manager.socket.emit('sftp_connect', {
      session_id: this.sessionId,
      host: host,
      port: port,
      username: username,
      password: password
    });
  }

  connectVNC() {
    const host = document.getElementById(`host_${this.id}`).value.trim();
    const port = parseInt(document.getElementById(`port_${this.id}`).value) || 5900;
    
    if (!host) {
      alert('请填写服务器地址');
      return;
    }
    
    this.connectionConfig = { host, port };
    const sessionId = `vnc_${Date.now()}`;
    
    // 启动VNC会话
    fetch('/vnc/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        host: host,
        port: port
      })
    })
    .then(response => response.json())
    .then(data => {
      if (data.status === 'success') {
        const viewer = document.getElementById(`viewer_${this.id}`);
        viewer.src = `/vnc?host=${host}&port=${port}`;
        this.isConnected = true;
        this.updateTabTitle();
      } else {
        alert('VNC连接失败: ' + data.message);
      }
    })
    .catch(error => {
      alert('VNC连接失败: ' + error);
    });
  }

  connectRDP() {
    const host = document.getElementById(`host_${this.id}`).value.trim();
    const port = parseInt(document.getElementById(`port_${this.id}`).value) || 3389;
    const username = document.getElementById(`username_${this.id}`).value.trim();
    const password = document.getElementById(`password_${this.id}`).value;
    
    if (!host || !username || !password) {
      alert('请填写完整的连接信息');
      return;
    }
    
    this.connectionConfig = { host, port, username, password };
    
    // 构建RDP连接URL
    const params = new URLSearchParams({
      host: host,
      port: port,
      username: username,
      password: password
    });
    
    const viewer = document.getElementById(`viewer_${this.id}`);
    viewer.src = `/rdp/connect?${params.toString()}`;
    this.isConnected = true;
    this.updateTabTitle();
  }

  updateConnectionStatus(status, isConnectedState) {
    const statusDot = document.getElementById(`status_dot_${this.id}`);
    const statusText = document.getElementById(`status_text_${this.id}`);
    const connectBtn = document.getElementById(`connect_${this.id}`);
    const refreshBtn = document.getElementById(`refresh_btn_${this.id}`);
    
    this.isConnected = isConnectedState;
    
    if (statusDot) {
      if (isConnectedState) {
        statusDot.style.background = 'var(--success-color)';
      } else {
        statusDot.style.background = 'var(--danger-color)';
      }
    }
    
    if (statusText) {
      statusText.textContent = status;
    }
    
    if (connectBtn) {
      if (isConnectedState) {
        connectBtn.innerHTML = '<i class="bx bx-loader bx-spin"></i> 已连接';
        connectBtn.disabled = true;
      } else {
        connectBtn.innerHTML = '<i class="bx bx-plug"></i> 连接';
        connectBtn.disabled = false;
      }
    }

    if (refreshBtn) {
      refreshBtn.disabled = !isConnectedState;
    }
  }

  refreshRemoteFiles() {
    if (!this.sftpConnected || !this.sessionId) return;
    
    this.manager.socket.emit('sftp_list', {
      session_id: this.sessionId,
      path: this.currentRemotePath
    });
  }

  updateRemoteFiles(files, path) {
    this.remoteFiles = files;
    this.currentRemotePath = path;
    
    const container = document.getElementById(`remote_files_${this.id}`);
    if (!container) return;
    
    if (files.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 200px; color: var(--text-muted); text-align: center;">
          <i class='bx bx-folder-open' style="font-size: 3rem; margin-bottom: 1rem; opacity: 0.5;"></i>
          <p>此目录为空</p>
        </div>
      `;
      return;
    }
    
    container.innerHTML = '';
    
    // 添加上级目录
    if (path !== '.' && path !== '/') {
      const parentItem = this.createFileItem({
        name: '..',
        is_dir: true,
        size: 0,
        mtime: 0
      }, true);
      container.appendChild(parentItem);
    }
    
    // 排序并显示文件
    const sortedFiles = [...files].sort((a, b) => {
      if (a.is_dir !== b.is_dir) return b.is_dir - a.is_dir;
      return a.name.localeCompare(b.name);
    });
    
    sortedFiles.forEach(file => {
      const item = this.createFileItem(file, false);
      container.appendChild(item);
    });
  }

  createFileItem(file, isParent = false) {
    const item = document.createElement('div');
    item.style.cssText = 'display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem; border-radius: var(--radius-sm); cursor: pointer; transition: var(--transition); font-size: 0.875rem;';
    
    const iconClass = isParent ? 'bx-up-arrow-alt' : 
                     file.is_dir ? 'bxs-folder' : 'bxs-file-blank';
    const iconColor = isParent ? 'text-secondary' : 
                     file.is_dir ? 'text-warning' : 'text-primary';
    
    item.innerHTML = `
      <i class='bx ${iconClass} ${iconColor}' style="width: 1.25rem; text-align: center;"></i>
      <div style="flex: 1; min-width: 0;">
        <div style="font-weight: 500; color: var(--text-primary); word-break: break-all;">${file.name}</div>
        <div style="font-size: 0.75rem; color: var(--text-secondary);">${file.is_dir ? '目录' : this.formatFileSize(file.size)}</div>
      </div>
    `;
    
    item.addEventListener('mouseenter', () => {
      item.style.background = 'var(--light-bg)';
    });
    
    item.addEventListener('mouseleave', () => {
      item.style.background = '';
    });
    
    if (file.is_dir || isParent) {
      item.onclick = () => {
        if (isParent) {
          const parts = this.currentRemotePath.split('/').filter(p => p);
          parts.pop();
          this.currentRemotePath = parts.length > 0 ? parts.join('/') : '.';
        } else {
          this.currentRemotePath = this.currentRemotePath === '.' ? file.name : 
                                 this.currentRemotePath + '/' + file.name;
        }
        this.refreshRemoteFiles();
      };
    }
    
    return item;
  }

  handleFileSelect() {
    const input = document.getElementById(`file_input_${this.id}`);
    const container = document.getElementById(`local_files_${this.id}`);
    
    if (input.files.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 200px; color: var(--text-muted); text-align: center;">
          <i class='bx bx-file-plus' style="font-size: 3rem; margin-bottom: 1rem; opacity: 0.5;"></i>
          <p>选择要上传的文件</p>
        </div>
      `;
      return;
    }
    
    container.innerHTML = '';
    
    Array.from(input.files).forEach((file, index) => {
      const item = document.createElement('div');
      item.style.cssText = 'display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem; border-radius: var(--radius-sm); font-size: 0.875rem;';
      
      item.innerHTML = `
        <i class='bx bxs-file-blank text-info' style="width: 1.25rem; text-align: center;"></i>
        <div style="flex: 1; min-width: 0;">
          <div style="font-weight: 500; color: var(--text-primary); word-break: break-all;">${file.name}</div>
          <div style="font-size: 0.75rem; color: var(--text-secondary);">${this.formatFileSize(file.size)}</div>
        </div>
        <button class="btn btn-success btn-sm" onclick="toolboxManager.windows.get('${this.id}').uploadFile(${index})" ${!this.sftpConnected ? 'disabled' : ''}>
          <i class='bx bx-upload'></i>
        </button>
      `;
      
      container.appendChild(item);
    });
  }

  uploadFile(index) {
    // 这里可以实现文件上传逻辑
    console.log('上传文件:', index);
  }

  formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  cleanup() {
    if (this.sessionId) {
      if (this.type === 'ssh') {
        this.manager.socket.emit('ssh_disconnect', { session_id: this.sessionId });
      } else if (this.type === 'sftp') {
        this.manager.socket.emit('sftp_disconnect', { session_id: this.sessionId });
      }
    }
    
    this.isConnected = false;
    this.sftpConnected = false;
    this.sessionId = null;
    
    if (this.terminal) {
      this.terminal.dispose();
    }
  }
}