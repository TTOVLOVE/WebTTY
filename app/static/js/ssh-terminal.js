// SSH终端专用JavaScript
class SSHTerminal {
    constructor() {
        this.socket = io();
        this.terminal = null;
        this.fitAddon = null;
        this.sessionId = null;
        this.isConnected = false;
        this.init();
    }

    init() {
        this.initTerminal();
        this.setupEventListeners();
        this.setupSocketEvents();
        this.updateConnectionStatus('未连接', '请填写连接信息并点击连接按钮');
    }

    initTerminal() {
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
        
        this.terminal.open(document.getElementById('terminal-wrapper'));
        this.fitAddon.fit();
        
        this.terminal.writeln('\x1b[1;32m欢迎使用 SSH 终端\x1b[0m');
        this.terminal.writeln('请配置连接信息并点击连接按钮开始使用。');
        this.terminal.writeln('');
        
        // 监听终端输入
        this.terminal.onData(data => {
            if (this.isConnected && this.sessionId) {
                this.socket.emit('ssh_input', { session_id: this.sessionId, data: data });
            }
        });
        
        // 监听窗口大小变化
        window.addEventListener('resize', () => {
            if (this.fitAddon) {
                this.fitAddon.fit();
                if (this.isConnected && this.sessionId) {
                    this.socket.emit('ssh_resize', {
                        session_id: this.sessionId,
                        cols: this.terminal.cols,
                        rows: this.terminal.rows
                    });
                }
            }
        });
    }

    setupEventListeners() {
        // 表单提交事件
        document.getElementById('ssh-form').addEventListener('submit', (e) => {
            e.preventDefault();
            if (!this.isConnected) {
                this.connectSSH();
            }
        });
    }

    setupSocketEvents() {
        this.socket.on('connect', () => {
            this.updateConnectionStatus('未连接', '已连接到服务器，请配置SSH连接');
        });

        this.socket.on('disconnect', () => {
            this.updateConnectionStatus('未连接', '与服务器断开连接');
            this.isConnected = false;
        });

        this.socket.on('ssh_connected', (data) => {
            if (data.session_id === this.sessionId) {
                this.isConnected = true;
                this.updateConnectionStatus('已连接', 'SSH连接已建立', true);
                this.terminal.writeln('\x1b[1;32mSSH连接成功建立\x1b[0m');
            }
        });

        this.socket.on('ssh_output', (data) => {
            if (data.session_id === this.sessionId && this.terminal) {
                this.terminal.write(data.data);
            }
        });

        this.socket.on('ssh_error', (data) => {
            if (data.session_id === this.sessionId) {
                this.updateConnectionStatus('连接失败', `连接错误: ${data.error}`);
                this.terminal.writeln(`\x1b[1;31m连接错误: ${data.error}\x1b[0m`);
                this.isConnected = false;
                this.sessionId = null;
            }
        });

        this.socket.on('ssh_closed', (data) => {
            if (data.session_id === this.sessionId) {
                this.updateConnectionStatus('未连接', 'SSH连接已关闭');
                this.terminal.writeln('\x1b[1;31m\r\nSSH连接已关闭\x1b[0m');
                this.isConnected = false;
                this.sessionId = null;
            }
        });
    }

    updateConnectionStatus(status, message, isConnectedState = false) {
        const indicator = document.getElementById('connection-indicator');
        const statusText = document.getElementById('connection-status');
        const terminalDot = document.getElementById('terminal-status-dot');
        const terminalText = document.getElementById('terminal-status-text');
        const statusMessage = document.getElementById('status-message');
        const connectionDetails = document.getElementById('connection-details');
        const currentConnection = document.getElementById('current-connection');
        const connectBtn = document.getElementById('connect-btn');
        const disconnectBtn = document.getElementById('disconnect-btn');
        
        if (isConnectedState) {
            indicator.classList.add('online');
            terminalDot.classList.add('connected');
            statusText.textContent = '已连接';
            terminalText.textContent = '已连接';
            connectBtn.innerHTML = '<i class="bx bx-loader bx-spin"></i> 已连接';
            connectBtn.disabled = true;
            disconnectBtn.style.display = 'inline-block';
            
            const host = document.getElementById('ssh-host').value;
            const port = document.getElementById('ssh-port').value;
            const username = document.getElementById('ssh-username').value;
            currentConnection.textContent = `${username}@${host}:${port}`;
            connectionDetails.style.display = 'block';
        } else {
            indicator.classList.remove('online');
            terminalDot.classList.remove('connected');
            statusText.textContent = status;
            terminalText.textContent = status;
            connectBtn.innerHTML = '<i class="bx bx-plug"></i> 连接';
            connectBtn.disabled = false;
            disconnectBtn.style.display = 'none';
            connectionDetails.style.display = 'none';
        }
        
        statusMessage.textContent = message;
    }

    connectSSH() {
        const host = document.getElementById('ssh-host').value.trim();
        const port = parseInt(document.getElementById('ssh-port').value) || 22;
        const username = document.getElementById('ssh-username').value.trim();
        const password = document.getElementById('ssh-password').value;
        
        if (!host || !username) {
            alert('请填写服务器地址和用户名');
            return;
        }
        
        this.sessionId = 'ssh_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        
        this.updateConnectionStatus('连接中', '正在建立SSH连接...');
        
        this.terminal.clear();
        this.terminal.writeln(`\x1b[1;33m正在连接到 ${username}@${host}:${port}...\x1b[0m`);
        
        this.socket.emit('ssh_connect', {
            session_id: this.sessionId,
            host: host,
            port: port,
            username: username,
            password: password,
            cols: this.terminal.cols,
            rows: this.terminal.rows
        });
    }

    disconnectSSH() {
        if (this.sessionId) {
            this.socket.emit('ssh_disconnect', { session_id: this.sessionId });
        }
        
        this.isConnected = false;
        this.sessionId = null;
        this.updateConnectionStatus('未连接', '已断开SSH连接');
        
        this.terminal.clear();
        this.terminal.writeln('\x1b[1;31mSSH连接已断开\x1b[0m');
        this.terminal.writeln('');
    }
}

// 全局实例
let sshTerminal;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    sshTerminal = new SSHTerminal();
});

// 全局函数（保持向后兼容）
function disconnectSSH() {
    sshTerminal?.disconnectSSH();
}