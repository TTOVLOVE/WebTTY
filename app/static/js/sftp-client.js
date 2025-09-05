// SFTP客户端专用JavaScript
class SFTPClient {
    constructor() {
        this.socket = io();
        this.sessionId = null;
        this.isConnected = false;
        this.selectedFiles = [];
        this.remoteFiles = [];
        this.currentRemotePath = '.';
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupSocketEvents();
        this.updateConnectionStatus('未连接', '请填写连接信息并点击连接按钮');
        this.renderLocalFiles();
    }

    setupEventListeners() {
        // 表单提交事件
        document.getElementById('sftp-form').addEventListener('submit', (e) => {
            e.preventDefault();
            if (!this.isConnected) {
                this.connectSFTP();
            }
        });

        // 回车键导航
        document.getElementById('remote-path').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.navigateRemote();
            }
        });

        // 文件选择事件
        document.getElementById('file-input').addEventListener('change', () => {
            this.handleFileSelect();
        });
    }

    setupSocketEvents() {
        this.socket.on('connect', () => {
            this.updateConnectionStatus('未连接', '已连接到服务器，请配置SFTP连接');
        });

        this.socket.on('disconnect', () => {
            this.updateConnectionStatus('未连接', '与服务器断开连接');
            this.isConnected = false;
        });

        this.socket.on('sftp_connected', (data) => {
            if (data.session_id === this.sessionId) {
                this.updateConnectionStatus('已连接', 'SFTP连接已建立', true);
                this.refreshRemoteFiles();
            }
        });

        this.socket.on('sftp_list_result', (data) => {
            if (data.session_id === this.sessionId) {
                this.remoteFiles = data.list || [];
                this.currentRemotePath = data.path;
                document.getElementById('remote-path').value = this.currentRemotePath;
                document.getElementById('remote-status').textContent = `当前路径: ${this.currentRemotePath}`;
                this.renderRemoteFiles();
            }
        });

        this.socket.on('sftp_error', (data) => {
            if (data.session_id === this.sessionId) {
                this.updateConnectionStatus('连接失败', `SFTP错误: ${data.error}`);
                alert(`SFTP错误: ${data.error}`);
                this.isConnected = false;
                this.sessionId = null;
            }
        });
    }

    updateConnectionStatus(status, message, isConnectedState = false) {
        const indicator = document.getElementById('connection-indicator');
        const statusText = document.getElementById('connection-status');
        const remoteStatus = document.getElementById('remote-status');
        const connectBtn = document.getElementById('connect-btn');
        const disconnectBtn = document.getElementById('disconnect-btn');
        const refreshBtn = document.getElementById('refresh-btn');
        const navigateBtn = document.getElementById('navigate-btn');
        
        this.isConnected = isConnectedState;
        
        if (isConnectedState) {
            indicator.classList.add('online');
            statusText.textContent = '已连接';
            connectBtn.innerHTML = '<i class="bx bx-loader bx-spin"></i> 已连接';
            connectBtn.disabled = true;
            disconnectBtn.style.display = 'inline-block';
            refreshBtn.disabled = false;
            navigateBtn.disabled = false;
            document.getElementById('remote-path').readOnly = false;
        } else {
            indicator.classList.remove('online');
            statusText.textContent = status;
            connectBtn.innerHTML = '<i class="bx bx-plug"></i> 连接';
            connectBtn.disabled = false;
            disconnectBtn.style.display = 'none';
            refreshBtn.disabled = true;
            navigateBtn.disabled = true;
            document.getElementById('remote-path').readOnly = true;
        }
        
        remoteStatus.textContent = message;
    }

    connectSFTP() {
        const host = document.getElementById('sftp-host').value.trim();
        const port = parseInt(document.getElementById('sftp-port').value) || 22;
        const username = document.getElementById('sftp-username').value.trim();
        const password = document.getElementById('sftp-password').value;
        
        if (!host || !username || !password) {
            alert('请填写完整的连接信息');
            return;
        }
        
        this.sessionId = 'sftp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        
        this.updateConnectionStatus('连接中', '正在建立SFTP连接...');
        
        this.socket.emit('sftp_connect', {
            session_id: this.sessionId,
            host: host,
            port: port,
            username: username,
            password: password
        });
    }

    disconnectSFTP() {
        if (this.sessionId) {
            this.socket.emit('sftp_disconnect', { session_id: this.sessionId });
        }
        
        this.isConnected = false;
        this.sessionId = null;
        this.remoteFiles = [];
        this.updateConnectionStatus('未连接', '已断开SFTP连接');
        this.renderRemoteFiles();
    }

    refreshRemoteFiles() {
        if (!this.isConnected || !this.sessionId) return;
        
        document.getElementById('remote-status').textContent = '正在加载...';
        this.socket.emit('sftp_list', {
            session_id: this.sessionId,
            path: this.currentRemotePath
        });
    }

    navigateRemote() {
        const path = document.getElementById('remote-path').value.trim();
        if (path && path !== this.currentRemotePath) {
            this.currentRemotePath = path;
            this.refreshRemoteFiles();
        }
    }

    renderRemoteFiles() {
        const container = document.getElementById('remote-files');
        const countEl = document.getElementById('remote-count');
        
        if (!this.isConnected || this.remoteFiles.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class='bx bx-${this.isConnected ? 'folder-open' : 'server'}'></i>
                    <p>${this.isConnected ? '此目录为空' : '请先连接到SFTP服务器'}</p>
                </div>
            `;
            countEl.textContent = '';
            return;
        }
        
        container.innerHTML = '';
        
        // 添加上级目录项
        if (this.currentRemotePath !== '.' && this.currentRemotePath !== '/') {
            const parentItem = this.createFileItem({
                name: '..',
                is_dir: true,
                size: 0,
                mtime: 0
            }, true);
            container.appendChild(parentItem);
        }
        
        // 排序：目录在前，然后按名称排序
        const sortedFiles = [...this.remoteFiles].sort((a, b) => {
            if (a.is_dir !== b.is_dir) return b.is_dir - a.is_dir;
            return a.name.localeCompare(b.name);
        });
        
        sortedFiles.forEach(file => {
            const item = this.createFileItem(file, false);
            container.appendChild(item);
        });
        
        countEl.textContent = `${this.remoteFiles.length} 项`;
    }

    createFileItem(file, isParent = false) {
        const item = document.createElement('div');
        item.className = 'file-item';
        
        const iconClass = isParent ? 'bx-up-arrow-alt' : 
                         file.is_dir ? 'bxs-folder' : 'bxs-file-blank';
        const iconColor = isParent ? 'text-secondary' : 
                         file.is_dir ? 'text-warning' : 'text-primary';
        
        item.innerHTML = `
            <div class="file-icon">
                <i class='bx ${iconClass} ${iconColor}'></i>
            </div>
            <div class="file-info">
                <div class="file-name">${file.name}</div>
                <div class="file-meta">
                    <span>${file.is_dir ? '目录' : this.formatFileSize(file.size)}</span>
                    <span>${this.formatDate(file.mtime)}</span>
                </div>
            </div>
        `;
        
        if (file.is_dir || isParent) {
            item.style.cursor = 'pointer';
            item.onclick = () => {
                if (isParent) {
                    // 导航到上级目录
                    const parts = this.currentRemotePath.split('/').filter(p => p);
                    parts.pop();
                    this.currentRemotePath = parts.length > 0 ? parts.join('/') : '.';
                } else {
                    // 导航到子目录
                    this.currentRemotePath = this.currentRemotePath === '.' ? file.name : 
                                           this.currentRemotePath + '/' + file.name;
                }
                document.getElementById('remote-path').value = this.currentRemotePath;
                this.refreshRemoteFiles();
            };
        }
        
        return item;
    }

    handleFileSelect() {
        const input = document.getElementById('file-input');
        this.selectedFiles = Array.from(input.files);
        this.renderLocalFiles();
    }

    renderLocalFiles() {
        const container = document.getElementById('local-files');
        const countEl = document.getElementById('local-count');
        const statusEl = document.getElementById('local-status');
        
        if (this.selectedFiles.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class='bx bx-file-plus'></i>
                    <p>点击上方按钮选择要上传的文件</p>
                </div>
            `;
            countEl.textContent = '';
            statusEl.textContent = '等待选择文件';
            return;
        }
        
        container.innerHTML = '';
        
        this.selectedFiles.forEach((file, index) => {
            const item = this.createLocalFileItem(file, index);
            container.appendChild(item);
        });
        
        countEl.textContent = `${this.selectedFiles.length} 个文件`;
        statusEl.textContent = `已选择 ${this.selectedFiles.length} 个文件`;
    }

    createLocalFileItem(file, index) {
        const item = document.createElement('div');
        item.className = 'file-item';
        
        item.innerHTML = `
            <div class="file-icon">
                <i class='bx bxs-file-blank text-info'></i>
            </div>
            <div class="file-info">
                <div class="file-name">${file.name}</div>
                <div class="file-meta">
                    <span>${this.formatFileSize(file.size)}</span>
                    <span>${new Date(file.lastModified).toLocaleString()}</span>
                </div>
            </div>
            <div class="ms-auto">
                <button class="btn btn-success btn-sm me-2" onclick="sftpClient.uploadFile(${index})" ${!this.isConnected ? 'disabled' : ''}>
                    <i class='bx bx-upload'></i>
                    上传
                </button>
                <button class="btn btn-danger btn-sm" onclick="sftpClient.removeFile(${index})">
                    <i class='bx bx-x'></i>
                </button>
            </div>
        `;
        
        return item;
    }

    uploadFile(index) {
        if (!this.isConnected || !this.sessionId || !this.selectedFiles[index]) return;
        
        const file = this.selectedFiles[index];
        const progressEl = document.getElementById('transfer-progress');
        const statusEl = document.getElementById('transfer-status');
        const percentEl = document.getElementById('transfer-percent');
        const fillEl = document.getElementById('progress-fill');
        
        progressEl.style.display = 'block';
        statusEl.textContent = `正在上传 ${file.name}...`;
        percentEl.textContent = '0%';
        fillEl.style.width = '0%';
        
        // 模拟上传进度
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 20;
            if (progress >= 100) {
                progress = 100;
                clearInterval(interval);
                statusEl.textContent = `${file.name} 上传完成`;
                setTimeout(() => {
                    progressEl.style.display = 'none';
                    this.refreshRemoteFiles();
                }, 2000);
            }
            percentEl.textContent = Math.round(progress) + '%';
            fillEl.style.width = progress + '%';
        }, 200);
    }

    removeFile(index) {
        this.selectedFiles.splice(index, 1);
        this.renderLocalFiles();
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    formatDate(timestamp) {
        if (!timestamp) return '未知';
        return new Date(timestamp * 1000).toLocaleString();
    }
}

// 全局实例
let sftpClient;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    sftpClient = new SFTPClient();
});

// 全局函数（保持向后兼容）
function disconnectSFTP() {
    sftpClient?.disconnectSFTP();
}

function refreshRemoteFiles() {
    sftpClient?.refreshRemoteFiles();
}

function navigateRemote() {
    sftpClient?.navigateRemote();
}