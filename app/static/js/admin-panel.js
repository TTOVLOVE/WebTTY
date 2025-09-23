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

    // 编辑用户表单提交
    const editUserForm = document.getElementById('editUserForm');
    if (editUserForm) {
      editUserForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.updateUser();
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

  // 加载用户列表
  async loadUserList() {
    try {
      const response = await fetch('/api/admin/users');
      if (response.ok) {
        const data = await response.json();
        this.updateUserList(data.users);
      } else {
        console.error('加载用户列表失败:', response.status);
        this.showNotification('加载用户列表失败', 'error');
      }
    } catch (error) {
      console.error('加载用户列表出错:', error);
      this.showNotification('加载用户列表出错', 'error');
    }
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
  async editUser(userId) {
    console.log('编辑用户:', userId);
    
    try {
      // 获取用户详情
      const response = await fetch(`/api/admin/users/${userId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        }
      });

      if (response.ok) {
        const data = await response.json();
        const user = data.user;
        
        // 填充编辑表单
        document.getElementById('editUserId').value = user.id;
        document.getElementById('editUsername').value = user.username;
        document.getElementById('editEmail').value = user.email;
        document.getElementById('editUserRole').value = user.role;
        document.getElementById('editUserStatus').value = user.status;
        
        // 显示编辑模态框（使用自定义样式控制）
        this.showEditUserModal();
      } else {
        const error = await response.json();
        this.showNotification(error.error || '获取用户信息失败', 'error');
      }
    } catch (error) {
      console.error('获取用户信息错误:', error);
      this.showNotification('获取用户信息失败', 'error');
    }
  }
  
  // 更新用户信息
  async updateUser() {
    const userId = document.getElementById('editUserId').value;
    const username = document.getElementById('editUsername').value;
    const email = document.getElementById('editEmail').value;
    const password = document.getElementById('editPassword').value;
    const role = document.getElementById('editUserRole').value;
    const status = document.getElementById('editUserStatus').value;
    
    try {
      const userData = {
        username,
        email,
        role,
        status
      };
      
      // 如果输入了密码，则添加到请求数据中
      if (password.trim() !== '') {
        userData.password = password;
      }
      
      const response = await fetch(`/api/admin/users/${userId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(userData)
      });

      if (response.ok) {
        this.showNotification('用户信息更新成功', 'success');
        // 隐藏编辑模态框
        const editUserModal = bootstrap.Modal.getInstance(document.getElementById('editUserModal'));
        editUserModal.hide();
        // 重新加载用户列表
        this.loadUserList();
        // 清空编辑表单
        document.getElementById('editUserForm').reset();
      } else {
        const error = await response.json();
        this.showNotification(error.error || '更新用户信息失败', 'error');
      }
    } catch (error) {
      console.error('更新用户信息错误:', error);
      this.showNotification('更新用户信息失败', 'error');
    }
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

  // 显示添加用户模态框
  showAddUserModal() {
    const modal = document.getElementById('addUserModal');
    if (modal) {
      modal.style.display = 'flex';
      modal.classList.add('active');
    }
  }

  // 隐藏添加用户模态框
  hideAddUserModal() {
    const modal = document.getElementById('addUserModal');
    if (modal) {
      modal.classList.remove('active');
      modal.style.display = 'none';
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

  // 显示编辑用户模态框
  showEditUserModal() {
    const modal = document.getElementById('editUserModal');
    if (modal) {
      modal.style.display = 'flex';
      modal.classList.add('active');
    }
  }

  // 隐藏编辑用户模态框
  hideEditUserModal() {
    const modal = document.getElementById('editUserModal');
    if (modal) {
      modal.classList.remove('active');
      modal.style.display = 'none';
    }
  }

  // 显示用户角色管理模态框
  showUserRolesModal() {
    const modal = document.getElementById('userRolesModal');
    if (modal) {
      modal.style.display = 'flex';
      modal.classList.add('active');
    }
  }

  // 隐藏用户角色管理模态框
  hideUserRolesModal() {
    const modal = document.getElementById('userRolesModal');
    if (modal) {
      modal.classList.remove('active');
      modal.style.display = 'none';
    }
  }

  // 编辑角色权限
  editRole(roleType) {
    console.log('编辑角色:', roleType);
    // 这里可以加载特定角色的权限设置
    this.showNotification(`正在编辑${roleType}角色权限`, 'info');
  }

  // 保存角色权限
  saveRolePermissions() {
    const permissions = {
      userManage: document.getElementById('perm-user-manage').checked,
      systemConfig: document.getElementById('perm-system-config').checked,
      clientControl: document.getElementById('perm-client-control').checked,
      fileAccess: document.getElementById('perm-file-access').checked
    };
    
    console.log('保存权限设置:', permissions);
    this.showNotification('权限设置已保存', 'success');
    this.hideUserRolesModal();
  }

  // 导出用户数据
  async exportUsers() {
    try {
      const response = await fetch('/api/admin/export/users');
      if (response.ok) {
        const data = await response.json();
        if (data.download_url) {
          // 创建一个临时链接并点击它来下载文件
          const link = document.createElement('a');
          link.href = data.download_url;
          link.download = data.download_url.split('/').pop();
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          
          this.showNotification('用户数据导出成功', 'success');
        } else {
          this.showNotification('导出链接无效', 'error');
        }
      } else {
        console.error('导出用户数据失败:', response.status);
        this.showNotification('导出用户数据失败', 'error');
      }
    } catch (error) {
      console.error('导出用户数据出错:', error);
      this.showNotification('导出用户数据出错', 'error');
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

function hideEditUserModal() {
  if (window.adminPanel) {
    window.adminPanel.hideEditUserModal();
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

function hideUserRolesModal() {
  if (window.adminPanel) {
    window.adminPanel.hideUserRolesModal();
  }
}

function editRole(roleType) {
  if (window.adminPanel) {
    window.adminPanel.editRole(roleType);
  }
}

function saveRolePermissions() {
  if (window.adminPanel) {
    window.adminPanel.saveRolePermissions();
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
  window.adminPanel.init();
});
