// 个人信息页面JavaScript功能
class ProfileManager {
    constructor() {
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadLoginStats();  // 添加加载登录统计
        this.loadSecuritySettings();
        this.loadActivityLog();
    }

    bindEvents() {
        // 标签页切换（仅限于 profile 页面内的 nav-tabs）
        document.querySelectorAll('.nav.nav-tabs .nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault(); // 阻止默认行为
                const tabId = e.currentTarget.dataset.tab;
                if (!tabId) {
                    // 非标签页按钮，忽略
                    return;
                }
                this.switchTab(tabId);
            });
        });

        // 个人信息表单提交
        document.getElementById('profileForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.updateProfile();
        });

        // 密码修改表单提交
        document.getElementById('passwordForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.changePassword();
        });

        // 密码强度检测
        document.getElementById('newPassword').addEventListener('input', (e) => {
            this.checkPasswordStrength(e.target.value);
        });

        // 头像上传
        document.getElementById('avatarInput').addEventListener('change', (e) => {
            this.uploadAvatar(e.target.files[0]);
        });

        // 安全设置保存
        document.getElementById('saveSecurityBtn').addEventListener('click', () => {
            this.saveSecuritySettings();
        });

        // 安全设置开关变化
        document.getElementById('twoFactorSwitch').addEventListener('change', (e) => {
            if (e.target.checked) {
                this.showAlert('双因素认证功能待实现', 'info');
                e.target.checked = false;
            }
        });
    }

    switchTab(tabId) {
        // 检查 tabId 是否有效
        if (!tabId) {
            console.error('switchTab: tabId is undefined or null');
            return;
        }

        // 更新导航标签状态
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        
        const navLink = document.querySelector(`[data-tab="${tabId}"]`);
        if (navLink) {
            navLink.classList.add('active');
        } else {
            console.error(`switchTab: 找不到导航链接 [data-tab="${tabId}"]`);
        }

        // 显示对应内容
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        
        const tabContent = document.getElementById(tabId);
        if (tabContent) {
            tabContent.classList.add('active');
        } else {
            console.error(`switchTab: 找不到标签内容 #${tabId}`);
        }

        // 如果切换到活动记录标签页，刷新数据
        if (tabId === 'activity') {
            this.loadActivityLog();
        }
    }

    async updateProfile() {
        const formData = {
            username: document.getElementById('username').value.trim(),
            email: document.getElementById('email').value.trim(),
            phone: document.getElementById('phone').value.trim()
        };

        // 基本验证
        if (!formData.username) {
            this.showAlert('用户名不能为空', 'warning');
            return;
        }

        if (formData.email && !this.isValidEmail(formData.email)) {
            this.showAlert('请输入有效的邮箱地址', 'warning');
            return;
        }

        try {
            const response = await fetch('/profile/api/update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });

            const data = await response.json();
            
            if (data.success) {
                this.showAlert('个人信息更新成功', 'success');
                this.updateDisplayInfo(formData);
            } else {
                this.showAlert(data.message || '更新失败', 'error');
            }
        } catch (error) {
            console.error('更新个人信息错误:', error);
            this.showAlert('网络错误，请稍后重试', 'error');
        }
    }

    async changePassword() {
        const currentPassword = document.getElementById('currentPassword').value;
        const newPassword = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;

        // 验证输入
        if (!currentPassword || !newPassword || !confirmPassword) {
            this.showAlert('请填写所有密码字段', 'warning');
            return;
        }

        if (newPassword !== confirmPassword) {
            this.showAlert('新密码和确认密码不匹配', 'warning');
            return;
        }

        if (newPassword.length < 6) {
            this.showAlert('新密码长度至少6位', 'warning');
            return;
        }

        try {
            const response = await fetch('/profile/api/change-password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword,
                    confirm_password: confirmPassword
                })
            });

            const data = await response.json();
            
            if (data.success) {
                this.showAlert('密码修改成功', 'success');
                document.getElementById('passwordForm').reset();
                this.resetPasswordStrength();
            } else {
                this.showAlert(data.message || '密码修改失败', 'error');
            }
        } catch (error) {
            console.error('修改密码错误:', error);
            this.showAlert('网络错误，请稍后重试', 'error');
        }
    }

    checkPasswordStrength(password) {
        const strengthFill = document.getElementById('strengthFill');
        const strengthText = document.getElementById('strengthText');
        
        if (!password) {
            strengthFill.style.width = '0%';
            strengthText.textContent = '请输入至少6位密码';
            strengthFill.className = 'strength-fill';
            return;
        }

        let strength = 0;
        let feedback = [];

        // 长度检查
        if (password.length >= 6) strength += 1;
        else feedback.push('至少6位');

        // 包含数字
        if (/\d/.test(password)) strength += 1;
        else feedback.push('包含数字');

        // 包含小写字母
        if (/[a-z]/.test(password)) strength += 1;
        else feedback.push('包含小写字母');

        // 包含大写字母
        if (/[A-Z]/.test(password)) strength += 1;
        else feedback.push('包含大写字母');

        // 包含特殊字符
        if (/[^A-Za-z0-9]/.test(password)) strength += 1;
        else feedback.push('包含特殊字符');

        // 更新强度显示
        const percentage = (strength / 5) * 100;
        strengthFill.style.width = `${percentage}%`;

        if (strength <= 2) {
            strengthFill.className = 'strength-fill strength-weak';
            strengthText.textContent = `弱密码 - 建议${feedback.slice(0, 2).join('、')}`;
        } else if (strength <= 3) {
            strengthFill.className = 'strength-fill strength-medium';
            strengthText.textContent = `中等强度 - 建议${feedback.slice(0, 1).join('、')}`;
        } else {
            strengthFill.className = 'strength-fill strength-strong';
            strengthText.textContent = '强密码';
        }
    }

    resetPasswordStrength() {
        const strengthFill = document.getElementById('strengthFill');
        const strengthText = document.getElementById('strengthText');
        
        strengthFill.style.width = '0%';
        strengthFill.className = 'strength-fill';
        strengthText.textContent = '请输入至少6位密码';
    }

    async uploadAvatar(file) {
        if (!file) return;

        // 验证文件类型
        if (!file.type.startsWith('image/')) {
            this.showAlert('请选择图片文件', 'warning');
            return;
        }

        // 验证文件大小（2MB）
        if (file.size > 2 * 1024 * 1024) {
            this.showAlert('图片大小不能超过2MB', 'warning');
            return;
        }

        try {
            // 这里简化处理，实际项目中需要上传到服务器
            const reader = new FileReader();
            reader.onload = (e) => {
                document.getElementById('avatarImg').src = e.target.result;
                this.showAlert('头像上传成功', 'success');
            };
            reader.readAsDataURL(file);

            // 调用后端API（模拟）
            const response = await fetch('/profile/api/upload-avatar', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    avatar_data: 'base64_data_here'
                })
            });

            const data = await response.json();
            if (!data.success) {
                this.showAlert(data.message || '头像上传失败', 'error');
            }
        } catch (error) {
            console.error('上传头像错误:', error);
            this.showAlert('头像上传失败', 'error');
        }
    }

    async loadSecuritySettings() {
        try {
            const response = await fetch('/profile/api/security-settings');
            const data = await response.json();
            
            if (data.success) {
                const settings = data.security_settings;
                
                // 更新安全设置界面
                document.getElementById('twoFactorSwitch').checked = settings.two_factor_enabled;
                document.getElementById('loginNotificationSwitch').checked = settings.login_notifications;
                document.getElementById('sessionTimeout').value = settings.session_timeout;
                
                // 更新安全信息
                document.getElementById('passwordLastChanged').textContent = settings.password_last_changed || '未设置';
                document.getElementById('failedAttempts').textContent = settings.failed_login_attempts || 0;
                
                // 更新账户状态和最后登录IP
                const accountStatusEl = document.getElementById('accountStatus');
                const lastLoginIpEl = document.getElementById('lastLoginIp');
                if (accountStatusEl) accountStatusEl.textContent = settings.account_status || '正常';
                if (lastLoginIpEl) lastLoginIpEl.textContent = settings.last_login_ip || '未知';
            }
        } catch (error) {
            console.error('加载安全设置错误:', error);
        }
    }

    async loadLoginStats() {
        try {
            const response = await fetch('/profile/api/login-stats');
            const data = await response.json();
            
            if (data.success) {
                const stats = data.stats || {};
                
                // 更新登录统计显示
                const loginCountEl = document.getElementById('loginCount');
                const lastLoginDaysEl = document.getElementById('lastLoginDays');
                
                if (loginCountEl) {
                    loginCountEl.textContent = stats.total_logins ?? 0;
                }
                
                if (lastLoginDaysEl) {
                    if (typeof stats.last_login_days === 'number') {
                        lastLoginDaysEl.textContent = stats.last_login_days;
                    } else if (stats.last_login_iso) {
                        const lastLoginDate = new Date(stats.last_login_iso);
                        if (!isNaN(lastLoginDate)) {
                            const now = new Date();
                            const diffTime = Math.abs(now - lastLoginDate);
                            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
                            lastLoginDaysEl.textContent = diffDays;
                        } else {
                            lastLoginDaysEl.textContent = '-';
                        }
                    } else if (stats.last_login) {
                        const lastLoginDate = new Date(stats.last_login);
                        if (!isNaN(lastLoginDate)) {
                            const now = new Date();
                            const diffTime = Math.abs(now - lastLoginDate);
                            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
                            lastLoginDaysEl.textContent = diffDays;
                        } else {
                            lastLoginDaysEl.textContent = '-';
                        }
                    } else {
                        lastLoginDaysEl.textContent = '-';
                    }
                }
            }
        } catch (error) {
            console.error('加载登录统计错误:', error);
        }
    }

    async saveSecuritySettings() {
        const settings = {
            two_factor_enabled: document.getElementById('twoFactorSwitch').checked,
            login_notifications: document.getElementById('loginNotificationSwitch').checked,
            session_timeout: parseInt(document.getElementById('sessionTimeout').value)
        };

        try {
            const response = await fetch('/profile/api/update-security', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(settings)
            });

            const data = await response.json();
            
            if (data.success) {
                this.showAlert('安全设置保存成功', 'success');
            } else {
                this.showAlert(data.message || '保存失败', 'error');
            }
        } catch (error) {
            console.error('保存安全设置错误:', error);
            this.showAlert('网络错误，请稍后重试', 'error');
        }
    }

    async loadActivityLog() {
        const activityList = document.getElementById('activityList');
        
        try {
            const response = await fetch('/profile/api/activity-log');
            const data = await response.json();
            
            if (data.success && data.activity_log.length > 0) {
                activityList.innerHTML = data.activity_log.map(activity => `
                    <div class="activity-item">
                        <div class="activity-icon">
                            <i class="fas ${this.getActivityIcon(activity.action)}"></i>
                        </div>
                        <div class="activity-content">
                            <div><strong>${activity.action}</strong></div>
                            <div class="activity-time">${activity.timestamp}</div>
                            <small class="text-muted">IP: ${activity.ip_address} | ${activity.user_agent}</small>
                        </div>
                    </div>
                `).join('');
            } else {
                activityList.innerHTML = `
                    <div class="text-center text-muted">
                        <i class="fas fa-history fa-3x mb-3"></i>
                        <p>暂无活动记录</p>
                    </div>
                `;
            }
        } catch (error) {
            console.error('加载活动记录错误:', error);
            activityList.innerHTML = `
                <div class="text-center text-danger">
                    <i class="fas fa-exclamation-triangle fa-3x mb-3"></i>
                    <p>加载活动记录失败</p>
                </div>
            `;
        }
    }

    getActivityIcon(action) {
        const iconMap = {
            '登录系统': 'fa-sign-in-alt',
            '修改个人信息': 'fa-user-edit',
            '查看连接列表': 'fa-list',
            '创建新连接': 'fa-plus',
            '执行漏洞扫描': 'fa-shield-alt',
            '修改密码': 'fa-key',
            '上传头像': 'fa-image'
        };
        return iconMap[action] || 'fa-info-circle';
    }

    updateDisplayInfo(formData) {
        // 更新左侧显示信息
        document.getElementById('displayUsername').textContent = formData.username || '未设置';
    }

    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    showAlert(message, type = 'info') {
        // 创建提示框
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="close" data-dismiss="alert">
                <span>&times;</span>
            </button>
        `;

        // 插入到页面顶部
        const container = document.querySelector('.container-fluid');
        container.insertBefore(alertDiv, container.firstChild);

        // 3秒后自动消失
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 3000);
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    window.profileManager = new ProfileManager();
});

// 连接码管理交互逻辑
(function() {
  const rotateBtn = document.getElementById('rotateConnectCodeBtn');
  const copyBtn = document.getElementById('copyConnectCodeBtn');
  const input = document.getElementById('connectCodeInput');
  if (!rotateBtn || !copyBtn || !input) return;

  let lastShown = null; // 仅前端缓存一次

  async function rotateAndShow() {
    rotateBtn.disabled = true;
    rotateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在重置...';
    input.value = '';
    copyBtn.disabled = true;
    try {
      const resp = await fetch('/api/connect-codes/user/rotate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      if (resp.status === 401) {
        // 未登录
        alert('未登录或会话已过期，请重新登录后再重置连接码');
        window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
        return;
      }
      const data = await resp.json();
      if (!resp.ok || !data.success) {
        throw new Error(data.message || ('重置失败，状态码 ' + resp.status));
      }
      // 后端约定：返回 { success: true, code: '明文连接码', code_id: <id> }
      input.value = data.code || '';
      lastShown = data.code || '';
      copyBtn.disabled = !lastShown;
      rotateBtn.innerHTML = '<i class="fas fa-sync-alt"></i> 重置并显示连接码';
    } catch (err) {
      console.error('rotate connect code error:', err);
      alert('重置连接码失败：' + err.message);
    } finally {
      rotateBtn.disabled = false;
      if (input.value === '') {
        rotateBtn.innerHTML = '<i class="fas fa-sync-alt"></i> 重置并显示连接码';
      }
    }
  }

  function copyCode() {
    if (!lastShown) return;
    navigator.clipboard.writeText(lastShown).then(() => {
      copyBtn.textContent = '已复制';
      setTimeout(() => (copyBtn.textContent = '复制'), 2000);
    }).catch((err) => {
      console.error('copy failed:', err);
      alert('复制失败，请手动选择并复制');
    });
  }

  rotateBtn.addEventListener('click', rotateAndShow);
  copyBtn.addEventListener('click', copyCode);
})();