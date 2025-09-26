// 系统管理面板 JavaScript
console.log('系统管理面板已加载');

class AdminPanel {
  constructor() {
    this.init();
  }

  init() {
    console.log('初始化管理面板...');
    this.loadSystemInfo();
    this.loadClientInfo();
    this.loadDatabaseInfo();
    this.setupEventListeners();
    this.startAutoRefresh();
  }

  setupEventListeners() {
    // 编辑端口表单提交
    const editPortForm = document.getElementById('editPortForm');
    if (editPortForm) {
      editPortForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.savePortSetting();
      });
    }
  }

  // 加载系统信息
  async loadSystemInfo() {
    try {
      const response = await fetch('/api/admin/system-info');
      if (response.ok) {
        const data = await response.json();
        this.updateSystemInfo(data);
      } else {
        console.error('加载系统信息失败:', response.status);
        this.showNotification('加载系统信息失败', 'error');
      }
    } catch (error) {
      console.error('加载系统信息出错:', error);
      this.showNotification('加载系统信息出错', 'error');
    }
  }

  // 更新系统信息显示
  updateSystemInfo(data) {
    const cpuUsage = document.getElementById('cpuUsage');
    const memoryUsage = document.getElementById('memoryUsage');
    const diskUsage = document.getElementById('diskUsage');
    const uptime = document.getElementById('uptime');

    if (cpuUsage) cpuUsage.textContent = `${data.cpu_usage}%`;
    if (memoryUsage) memoryUsage.textContent = `${data.memory_usage}%`;
    if (diskUsage) diskUsage.textContent = `${data.disk_usage}%`;
    if (uptime) uptime.textContent = `${data.uptime}天`;
  }

  // 加载客户端信息
  async loadClientInfo() {
    try {
      const response = await fetch('/api/admin/clients');
      if (response.ok) {
        const data = await response.json();
        this.updateClientInfo(data);
      } else {
        console.error('加载客户端信息失败:', response.status);
        this.showNotification('加载客户端信息失败', 'error');
      }
    } catch (error) {
      console.error('加载客户端信息出错:', error);
      this.showNotification('加载客户端信息出错', 'error');
    }
  }

  // 更新客户端信息显示
  updateClientInfo(data) {
    const totalClients = document.getElementById('totalClients');
    const onlineClients = document.getElementById('onlineClients');
    const maxClients = document.getElementById('maxClients');
    const clientList = document.getElementById('clientList');

    if (totalClients) totalClients.textContent = data.total;
    if (onlineClients) onlineClients.textContent = data.online;
    if (maxClients) maxClients.textContent = data.max;

    if (clientList && data.clients) {
      this.renderClientList(data.clients, clientList);
    }
  }

  // 渲染客户端列表
  renderClientList(clients, container) {
    if (clients.length === 0) {
      container.innerHTML = '<div class="text-center text-muted">暂无客户端连接</div>';
      return;
    }

    let html = '';
    clients.forEach(client => {
      const statusClass = client.status === 'online' ? 'online' : 
                         client.status === 'connecting' ? 'connecting' : 'offline';
      
      html += `
        <div class="client-item">
          <div class="client-status ${statusClass}"></div>
          <div class="flex-grow-1">
            <div class="font-weight-500">${client.name}</div>
            <small class="text-muted">${client.ip}</small>
          </div>
          <small class="text-muted">${client.last_seen}</small>
        </div>
      `;
    });

    container.innerHTML = html;
  }

  // 加载数据库信息
  async loadDatabaseInfo() {
    try {
      const response = await fetch('/api/admin/database');
      if (response.ok) {
        const data = await response.json();
        this.updateDatabaseInfo(data);
      } else {
        console.error('加载数据库信息失败:', response.status);
        this.showNotification('加载数据库信息失败', 'error');
      }
    } catch (error) {
      console.error('加载数据库信息出错:', error);
      this.showNotification('加载数据库信息出错', 'error');
    }
  }

  // 更新数据库信息显示
  updateDatabaseInfo(data) {
    const dbStatusIndicator = document.getElementById('dbStatusIndicator');
    const dbStatusText = document.getElementById('dbStatusText');
    const dbType = document.getElementById('dbType');
    const dbPoolSize = document.getElementById('dbPoolSize');
    const dbResponseTime = document.getElementById('dbResponseTime');
    const dbActiveConnections = document.getElementById('dbActiveConnections');

    if (dbStatusIndicator) {
      dbStatusIndicator.style.background = data.status === 'connected' ? '#10b981' : '#ef4444';
    }
    if (dbStatusText) dbStatusText.textContent = data.status === 'connected' ? '连接正常' : '连接异常';
    if (dbType) dbType.textContent = data.type;
    if (dbPoolSize) dbPoolSize.textContent = data.pool_size;
    if (dbResponseTime) dbResponseTime.textContent = `${data.response_time}ms`;
    if (dbActiveConnections) dbActiveConnections.textContent = data.active_connections;
  }



  // 编辑端口设置
  editPort(service, currentPort) {
    const modal = document.getElementById('editPortModal');
    const serviceInput = document.getElementById('editPortService');
    const portInput = document.getElementById('editPortNumber');

    if (serviceInput) serviceInput.value = service;
    if (portInput) portInput.value = currentPort;

    if (modal) {
      modal.style.display = 'flex';
      modal.classList.add('active');
    }
  }

  // 保存端口设置
  async savePortSetting() {
    const service = document.getElementById('editPortService').value;
    const port = document.getElementById('editPortNumber').value;

    try {
      const response = await fetch('/api/admin/ports', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          service,
          port: parseInt(port)
        })
      });

      if (response.ok) {
        this.showNotification('端口设置保存成功', 'success');
        this.hideEditPortModal();
        // 这里可以更新页面上的端口显示
      } else {
        const error = await response.json();
        this.showNotification(error.message || '保存端口设置失败', 'error');
      }
    } catch (error) {
      console.error('保存端口设置错误:', error);
      this.showNotification('保存端口设置失败', 'error');
    }
  }

  // 编辑域名设置
  editDomain(type) {
    console.log('编辑域名:', type);
    this.showNotification('域名编辑功能开发中', 'info');
  }

  // 上传SSL证书
  uploadSSL() {
    console.log('上传SSL证书');
    this.showNotification('SSL证书上传功能开发中', 'info');
  }

  // 续期SSL证书
  renewSSL() {
    console.log('续期SSL证书');
    this.showNotification('SSL证书续期功能开发中', 'info');
  }

  // 查看密钥
  viewKey(type) {
    console.log('查看密钥:', type);
    this.showNotification('密钥查看功能开发中', 'info');
  }

  // 重新生成密钥
  regenerateKey(type) {
    if (!confirm(`确定要重新生成${type}密钥吗？这将使现有的连接失效。`)) {
      return;
    }
    console.log('重新生成密钥:', type);
    this.showNotification('密钥重新生成功能开发中', 'info');
  }

  // 查看令牌
  async viewToken(type) {
    try {
      const response = await fetch(`/api/admin/tokens/${type}`);
      if (response.ok) {
        const data = await response.json();
        
        // 显示令牌信息
        let message = `<div class="token-info">\n`;
        message += `<p><strong>类型:</strong> ${data.type.toUpperCase()}</p>\n`;
        message += `<p><strong>令牌:</strong> ${data.token || '未生成'}</p>\n`;
        message += `<p><strong>创建时间:</strong> ${data.created || '未知'}</p>\n`;
        message += `<p><strong>过期时间:</strong> ${data.expires || '未知'}</p>\n`;
        message += `<p><strong>状态:</strong> ${data.status === 'active' ? '有效' : data.status === 'expired' ? '已过期' : '未生成'}</p>\n`;
        message += `</div>`;
        
        this.showNotification(message, 'info', 10000);
      } else {
        console.error('获取令牌信息失败:', response.status);
        this.showNotification('获取令牌信息失败', 'error');
      }
    } catch (error) {
      console.error('获取令牌信息出错:', error);
      this.showNotification('获取令牌信息出错', 'error');
    }
  }

  // 重新生成令牌
  async regenerateToken(type) {
    if (!confirm(`确定要重新生成${type}令牌吗？这将使现有的连接失效。`)) {
      return;
    }
    
    try {
      const response = await fetch(`/api/admin/tokens/${type}/regenerate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        
        // 显示新令牌信息
        let message = `<div class="token-info">\n`;
        message += `<p>${data.message}</p>\n`;
        message += `<p><strong>新令牌:</strong> ${data.token || '生成失败'}</p>\n`;
        message += `<p><strong>创建时间:</strong> ${data.created || '未知'}</p>\n`;
        message += `<p><strong>过期时间:</strong> ${data.expires || '未知'}</p>\n`;
        message += `</div>`;
        
        this.showNotification(message, 'success', 10000);
      } else {
        console.error('重新生成令牌失败:', response.status);
        this.showNotification('重新生成令牌失败', 'error');
      }
    } catch (error) {
      console.error('重新生成令牌出错:', error);
      this.showNotification('重新生成令牌出错', 'error');
    }
  }



  // 隐藏编辑端口模态框
  hideEditPortModal() {
    const modal = document.getElementById('editPortModal');
    if (modal) {
      modal.classList.remove('active');
      modal.style.display = 'none';
    }
  }



  // 刷新系统信息
  refreshSystemInfo() {
    this.loadSystemInfo();
    this.showNotification('系统信息已刷新', 'success');
  }

  // 开始自动刷新
  startAutoRefresh() {
    // 每30秒自动刷新系统信息
    setInterval(() => {
      this.loadSystemInfo();
    }, 30000);
  }

  // 显示通知
  showNotification(message, type = 'info', duration = 3000) {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
      <div class="notification-content">
        <i class='bx bx-${type === 'success' ? 'check-circle' : type === 'error' ? 'x-circle' : 'info-circle'} notification-icon'></i>
        <div>${message}</div>
      </div>
      <button class="notification-close" onclick="this.parentElement.remove()">&times;</button>
    `;

    // 添加到页面
    document.body.appendChild(notification);

    // 指定时间后自动移除
    setTimeout(() => {
      if (notification.parentElement) {
        notification.remove();
      }
    }, duration);
  }
}

// 全局函数，供HTML调用
function hideEditPortModal() {
  if (window.adminPanel) {
    window.adminPanel.hideEditPortModal();
  }
}

function editPort(service, currentPort) {
  if (window.adminPanel) {
    window.adminPanel.editPort(service, currentPort);
  }
}

function editDomain(type) {
  if (window.adminPanel) {
    window.adminPanel.editDomain(type);
  }
}

function uploadSSL() {
  if (window.adminPanel) {
    window.adminPanel.uploadSSL();
  }
}

function renewSSL() {
  if (window.adminPanel) {
    window.adminPanel.renewSSL();
  }
}

function viewKey(type) {
  if (window.adminPanel) {
    window.adminPanel.viewKey(type);
  }
}

function regenerateKey(type) {
  if (window.adminPanel) {
    window.adminPanel.regenerateKey(type);
  }
}

function viewToken(type) {
  if (window.adminPanel) {
    window.adminPanel.viewToken(type);
  }
}

function regenerateToken(type) {
  if (window.adminPanel) {
    window.adminPanel.regenerateToken(type);
  }
}

function refreshSystemInfo() {
  if (window.adminPanel) {
    window.adminPanel.refreshSystemInfo();
  }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
  window.adminPanel = new AdminPanel();
  window.adminPanel.init();
});
