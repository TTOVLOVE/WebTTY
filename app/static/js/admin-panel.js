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
    this.loadUserList();
    this.setupEventListeners();
    this.startAutoRefresh();
  }

  setupEventListeners() {
    // 添加用户表单提交
    const addUserForm = document.getElementById('addUserForm');
    if (addUserForm) {
      addUserForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.createUser();
      });
    }

    // 编辑端口表单提交
    const editPortForm = document.getElementById('editPortForm');
    if (editPortForm) {
      editPortForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.savePortSetting();
      });
    }

    // 密码确认验证
    const confirmPassword = document.getElementById('confirmPassword');
    if (confirmPassword) {
      confirmPassword.addEventListener('input', () => {
        this.validatePassword();
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
        // 如果API不存在，使用模拟数据
        this.updateSystemInfo(this.getMockSystemInfo());
      }
    } catch (error) {
      console.log('使用模拟系统信息');
      this.updateSystemInfo(this.getMockSystemInfo());
    }
  }

  // 获取模拟系统信息
  getMockSystemInfo() {
    return {
      cpu_usage: Math.floor(Math.random() * 100),
      memory_usage: Math.floor(Math.random() * 100),
      disk_usage: Math.floor(Math.random() * 100),
      uptime: Math.floor(Math.random() * 30) + 1
    };
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
        // 使用模拟数据
        this.updateClientInfo(this.getMockClientInfo());
      }
    } catch (error) {
      console.log('使用模拟客户端信息');
      this.updateClientInfo(this.getMockClientInfo());
    }
  }

  // 获取模拟客户端信息
  getMockClientInfo() {
    return {
      total: Math.floor(Math.random() * 50) + 10,
      online: Math.floor(Math.random() * 20) + 5,
      max: 100,
      clients: [
        { id: 1, name: 'Client-001', status: 'online', ip: '192.168.1.100', last_seen: '2分钟前' },
        { id: 2, name: 'Client-002', status: 'offline', ip: '192.168.1.101', last_seen: '1小时前' },
        { id: 3, name: 'Client-003', status: 'connecting', ip: '192.168.1.102', last_seen: '正在连接' }
      ]
    };
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
        // 使用模拟数据
        this.updateDatabaseInfo(this.getMockDatabaseInfo());
      }
    } catch (error) {
      console.log('使用模拟数据库信息');
      this.updateDatabaseInfo(this.getMockDatabaseInfo());
    }
  }

  // 获取模拟数据库信息
  getMockDatabaseInfo() {
    return {
      status: 'connected',
      type: 'SQLite',
      pool_size: 10,
      response_time: Math.floor(Math.random() * 20) + 1,
      active_connections: Math.floor(Math.random() * 10) + 1
    };
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

  // 加载用户列表
  async loadUserList() {
    try {
      const response = await fetch('/api/admin/users');
      if (response.ok) {
        const data = await response.json();
        this.updateUserList(data.users);
      } else {
        // 使用模拟数据
        this.updateUserList(this.getMockUsers());
      }
    } catch (error) {
      console.log('使用模拟用户数据');
      this.updateUserList(this.getMockUsers());
    }
  }

  // 获取模拟用户数据
  getMockUsers() {
    return [
      { id: 1, username: 'admin', role: 'admin', status: 'active', last_login: '2024-01-15 10:30:00' },
      { id: 2, username: 'user1', role: 'user', status: 'active', last_login: '2024-01-15 09:15:00' },
      { id: 3, username: 'guest1', role: 'guest', status: 'inactive', last_login: '2024-01-14 16:45:00' }
    ];
  }

  // 更新用户列表显示
  updateUserList(users) {
    const userTableBody = document.getElementById('userTableBody');
    if (!userTableBody) return;

    if (users.length === 0) {
      userTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">暂无用户数据</td></tr>';
      return;
    }

    let html = '';
    users.forEach(user => {
      const roleClass = user.role === 'admin' ? 'admin' : 
                       user.role === 'user' ? 'user' : 'guest';
      const statusClass = user.status === 'active' ? 'text-success' : 'text-muted';
      
      html += `
        <tr>
          <td>${user.username}</td>
          <td><span class="user-role ${roleClass}">${user.role}</span></td>
          <td class="${statusClass}">${user.status === 'active' ? '活跃' : '非活跃'}</td>
          <td>${user.last_login}</td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="adminPanel.editUser(${user.id})">
              <i class='bx bx-edit'></i>
            </button>
            <button class="btn btn-danger btn-sm" onclick="adminPanel.deleteUser(${user.id})">
              <i class='bx bx-trash'></i>
            </button>
          </td>
        </tr>
      `;
    });

    userTableBody.innerHTML = html;
  }

  // 创建新用户
  async createUser() {
    const username = document.getElementById('newUsername').value;
    const email = document.getElementById('newEmail').value;
    const password = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const role = document.getElementById('newUserRole').value;

    if (!this.validatePassword()) {
      this.showNotification('密码确认不匹配', 'error');
      return;
    }

    try {
      const response = await fetch('/api/admin/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username,
          email,
          password,
          role
        })
      });

      if (response.ok) {
        this.showNotification('用户创建成功', 'success');
        this.hideAddUserModal();
        this.loadUserList();
        this.clearAddUserForm();
      } else {
        const error = await response.json();
        this.showNotification(error.message || '创建用户失败', 'error');
      }
    } catch (error) {
      console.error('创建用户错误:', error);
      this.showNotification('创建用户失败', 'error');
    }
  }

  // 验证密码
  validatePassword() {
    const password = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    
    if (password !== confirmPassword) {
      document.getElementById('confirmPassword').style.borderColor = '#ef4444';
      return false;
    } else {
      document.getElementById('confirmPassword').style.borderColor = '';
      return true;
    }
  }

  // 清空添加用户表单
  clearAddUserForm() {
    document.getElementById('addUserForm').reset();
  }

  // 编辑用户
  editUser(userId) {
    console.log('编辑用户:', userId);
    // 这里可以实现编辑用户的逻辑
    this.showNotification('编辑用户功能开发中', 'info');
  }

  // 删除用户
  async deleteUser(userId) {
    if (!confirm('确定要删除这个用户吗？此操作不可撤销。')) {
      return;
    }

    try {
      const response = await fetch(`/api/admin/users/${userId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        this.showNotification('用户删除成功', 'success');
        this.loadUserList();
      } else {
        const error = await response.json();
        this.showNotification(error.message || '删除用户失败', 'error');
      }
    } catch (error) {
      console.error('删除用户错误:', error);
      this.showNotification('删除用户失败', 'error');
    }
  }

  // 编辑端口设置
  editPort(service, currentPort) {
    const modal = document.getElementById('editPortModal');
    const serviceInput = document.getElementById('editPortService');
    const portInput = document.getElementById('editPortNumber');

    if (serviceInput) serviceInput.value = service;
    if (portInput) portInput.value = currentPort;

    if (modal) modal.style.display = 'flex';
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
  viewToken(type) {
    console.log('查看令牌:', type);
    this.showNotification('令牌查看功能开发中', 'info');
  }

  // 重新生成令牌
  regenerateToken(type) {
    if (!confirm(`确定要重新生成${type}令牌吗？这将使现有的连接失效。`)) {
      return;
    }
    console.log('重新生成令牌:', type);
    this.showNotification('令牌重新生成功能开发中', 'info');
  }

  // 显示添加用户模态框
  showAddUserModal() {
    const modal = document.getElementById('addUserModal');
    if (modal) modal.style.display = 'flex';
  }

  // 隐藏添加用户模态框
  hideAddUserModal() {
    const modal = document.getElementById('addUserModal');
    if (modal) modal.style.display = 'none';
  }

  // 隐藏编辑端口模态框
  hideEditPortModal() {
    const modal = document.getElementById('editPortModal');
    if (modal) modal.style.display = 'none';
  }

  // 显示用户角色管理模态框
  showUserRolesModal() {
    console.log('显示用户角色管理');
    this.showNotification('用户角色管理功能开发中', 'info');
  }

  // 导出用户数据
  exportUsers() {
    console.log('导出用户数据');
    this.showNotification('用户数据导出功能开发中', 'info');
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
  showNotification(message, type = 'info') {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
      <div class="notification-content">
        <i class='bx bx-${type === 'success' ? 'check-circle' : type === 'error' ? 'x-circle' : 'info-circle'} notification-icon'></i>
        <span>${message}</span>
      </div>
      <button class="notification-close" onclick="this.parentElement.remove()">&times;</button>
    `;

    // 添加到页面
    document.body.appendChild(notification);

    // 3秒后自动移除
    setTimeout(() => {
      if (notification.parentElement) {
        notification.remove();
      }
    }, 3000);
  }
}

// 全局函数，供HTML调用
function showAddUserModal() {
  if (window.adminPanel) {
    window.adminPanel.showAddUserModal();
  }
}

function hideAddUserModal() {
  if (window.adminPanel) {
    window.adminPanel.hideAddUserModal();
  }
}

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

function showUserRolesModal() {
  if (window.adminPanel) {
    window.adminPanel.showUserRolesModal();
  }
}

function exportUsers() {
  if (window.adminPanel) {
    window.adminPanel.exportUsers();
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
});
