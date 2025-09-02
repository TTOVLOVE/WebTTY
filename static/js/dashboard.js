// 仪表板专用JavaScript
class Dashboard {
    constructor() {
        this.socket = io();
        this.currentCommandForParam = "";
        this.messageHistory = [];
        this.maxHistory = 1000;
        this.lastTimeoutMessage = 0;
        this.timeoutMessageInterval = 5000;
        this.eventsInitialized = false;
        this.init();
    }

    init() {
        this.initializeSocket();
        this.loadQuickConnections();
        this.loadHistory();
        this.setupEventListeners();
    }

    setupEventListeners() {
        // 命令输入事件
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
    }

    initializeSocket() {
        if (this.socket && this.eventsInitialized) {
            return; // 避免重复初始化
        }
        
        // 只绑定一次事件监听器
        if (!this.eventsInitialized) {
            // 监听服务器发送的完整客户端列表
            this.socket.on("clients_list", (data) => {
                console.log("收到客户端列表:", data.clients);
                if (data && data.clients) {
                    this.updateClientDropdown(data.clients);
                } else {
                    console.error("从服务器收到的客户端列表格式不正确:", data);
                    this.updateClientDropdown({});
                }
            });

            // 监听新客户端连接
            this.socket.on('new_client', (clientData) => {
                console.log("新客户端连接:", clientData);
                this.populateClientsInitial();
            });

            // 监听客户端信息更新
            this.socket.on('client_updated', (clientData) => {
                console.log("客户端信息更新:", clientData);
                this.populateClientsInitial();
            });

            // 监听客户端断开连接
            this.socket.on('client_disconnected', (data) => {
                console.log("客户端断开连接:", data);
                this.populateClientsInitial();
            });

            // 监听命令结果
            this.socket.on("command_result", (data) => {
                this.handleCommandResult(data);
            });

            // 监听截图事件
            this.socket.on('new_screenshot', (data) => {
                this.handleNewScreenshot(data);
            });
            
            this.eventsInitialized = true;
        }
    }

    updateClientDropdown(clientsData) {
        const select = document.getElementById("client-select");
        if (!select) return;
        
        const previouslySelected = select.value;
        select.innerHTML = "";

        const clientIds = Object.keys(clientsData);

        if (clientIds.length === 0) {
            const option = document.createElement("option");
            option.value = "";
            option.text = "无在线客户端";
            option.disabled = true;
            select.appendChild(option);
        } else {
            clientIds.forEach((clientId) => {
                const clientInfo = clientsData[clientId];
                const option = document.createElement("option");
                option.value = clientId;
                option.innerHTML = `客户端 ${clientId} (${clientInfo.user || '未知'}) @ ${clientInfo.addr || '未知IP'}`;
                select.appendChild(option);
            });
            
            if (clientIds.includes(previouslySelected)) {
                select.value = previouslySelected;
            } else if (clientIds.length > 0) {
                select.value = clientIds[0];
            }
        }
    }

    populateClientsInitial() {
        console.log("请求客户端列表...");
        this.socket.emit("get_clients");
    }

    sendCommand() {
        const target = document.getElementById("client-select")?.value;
        const cmdFull = document.getElementById("command-input")?.value.trim();

        if (!target) {
            alert("请先选择一个客户端！");
            return;
        }
        if (!cmdFull) {
            alert("请输入命令！");
            return;
        }

        let action = cmdFull;
        let arg = "";

        const parts = cmdFull.split(/\s+/);
        action = parts[0];
        if (parts.length > 1) {
            arg = parts.slice(1).join(" ");
        }

        this.addFeedbackMessage(`正在发送命令: ${cmdFull}`);

        console.log(`发送命令给 ${target}: action='${action}', arg='${arg}'`);
        this.socket.emit("send_command", { target, command: { action, arg } });
        document.getElementById("command-input").value = "";
        document.getElementById("command-input").focus();
    }

    sendQuickCommand(cmdAction, cmdArg = "") {
        const target = document.getElementById("client-select")?.value;
        if (!target) {
            alert("请先选择一个客户端！");
            return;
        }

        let cmdDisplay = cmdAction;
        if (cmdArg) {
            cmdDisplay += ` ${cmdArg}`;
        }

        this.addFeedbackMessage(`正在发送快捷命令: ${cmdDisplay}`);

        console.log(`发送快捷命令给 ${target}: action='${cmdAction}', arg='${cmdArg}'`);
        this.socket.emit("send_command", { target, command: { action: cmdAction, arg: cmdArg } });
    }

    showInput(cmd) {
        this.currentCommandForParam = cmd;
        const paramInput = document.getElementById("param-input");
        if (paramInput) {
            paramInput.classList.add("active");
            const input = document.getElementById("param-value");
            if (input) {
                input.focus();
            }
        }
    }

    sendParamCommand() {
        const target = document.getElementById("client-select")?.value;
        const param = document.getElementById("param-value")?.value.trim();

        if (!target) {
            alert("请先选择一个客户端！");
            return;
        }
        if (!param && this.currentCommandForParam === "download") {
            alert("请输入要下载的文件路径！");
            return;
        }

        if (this.currentCommandForParam) {
            this.addFeedbackMessage(`正在发送${this.currentCommandForParam === 'download' ? '下载' : '参数'}命令: ${this.currentCommandForParam} ${param}`);

            this.sendQuickCommand(this.currentCommandForParam, param);
            this.hideInput();
        }
    }

    hideInput() {
        const paramInput = document.getElementById("param-input");
        const paramValue = document.getElementById("param-value");
        if (paramInput) paramInput.classList.remove("active");
        if (paramValue) paramValue.value = "";
        this.currentCommandForParam = "";
    }

    useCommand(cmd) {
        const input = document.getElementById("command-input");
        if (input) {
            input.value = cmd;
            input.focus();
        }
    }

    handleCommandResult(data) {
        const out = document.getElementById("output");
        if (!out) return;

        const timestamp = new Date().toLocaleTimeString();

        if (data.output && data.output.includes("客户端响应超时")) {
            const now = Date.now();
            if (now - this.lastTimeoutMessage < this.timeoutMessageInterval) {
                return;
            }
            this.lastTimeoutMessage = now;
        }

        let outputLine = document.createElement('div');
        outputLine.className = 'terminal-line';
        
        if (data.is_error) {
            outputLine.classList.add('terminal-error');
        } else if (data.is_success) {
            outputLine.classList.add('terminal-success');
        } else if (data.is_warning) {
            outputLine.classList.add('terminal-warning');
        }

        let timeSpan = document.createElement('span');
        timeSpan.className = 'terminal-timestamp';
        timeSpan.textContent = `[${timestamp}] `;
        outputLine.appendChild(timeSpan);

        if (data.is_file_link && data.file_url) {
            let link = document.createElement('a');
            link.href = data.file_url;
            link.target = '_blank';
            let cleanOutput = data.output.replace(/\[\d+\]\s*/, '');
            const clientMatch = cleanOutput.match(/^(\[\d+\])\s*/);
            if (clientMatch) {
                let clientSpan = document.createElement('span');
                clientSpan.className = 'terminal-client';
                clientSpan.textContent = clientMatch[1] + ' ';
                outputLine.appendChild(clientSpan);
                
                let linkText = cleanOutput.substring(clientMatch[0].length);
                linkText = linkText.replace(/<[^>]*>/g, '');
                link.textContent = linkText;
                outputLine.appendChild(link);
            } else {
                let linkText = cleanOutput;
                linkText = linkText.replace(/<[^>]*>/g, '');
                link.textContent = linkText;
                outputLine.appendChild(link);
            }
        } else {
            let cleanOutput = data.output
                .replace(/<pre>/g, '')
                .replace(/<\/pre>/g, '')
                .replace(/<[^>]*>/g, '');
            
            const clientMatch = cleanOutput.match(/^(\[\d+\])\s*/);
            if (clientMatch) {
                let clientSpan = document.createElement('span');
                clientSpan.className = 'terminal-client';
                clientSpan.textContent = clientMatch[1] + ' ';
                outputLine.appendChild(clientSpan);
                
                let contentSpan = document.createElement('span');
                contentSpan.textContent = cleanOutput.substring(clientMatch[0].length);
                outputLine.appendChild(contentSpan);
            } else {
                let contentSpan = document.createElement('span');
                contentSpan.textContent = cleanOutput;
                outputLine.appendChild(contentSpan);
            }
        }

        this.saveToHistory({
            htmlContent: outputLine.outerHTML,
            is_error: data.is_error,
            is_success: data.is_success,
            is_warning: data.is_warning,
            timestamp: timestamp
        });

        out.appendChild(outputLine);
        requestAnimationFrame(() => {
            out.scrollTop = out.scrollHeight;
        });
    }

    addFeedbackMessage(message) {
        const out = document.getElementById("output");
        if (!out) return;

        const timestamp = new Date().toLocaleTimeString();
        let feedbackLine = document.createElement('div');
        feedbackLine.className = 'terminal-line';
        
        let timeSpan = document.createElement('span');
        timeSpan.className = 'terminal-timestamp';
        timeSpan.textContent = `[${timestamp}] `;
        feedbackLine.appendChild(timeSpan);

        let systemSpan = document.createElement('span');
        systemSpan.className = 'terminal-system';
        systemSpan.textContent = '[系统] ';
        feedbackLine.appendChild(systemSpan);

        let messageSpan = document.createElement('span');
        messageSpan.textContent = message;
        feedbackLine.appendChild(messageSpan);

        out.appendChild(feedbackLine);
        requestAnimationFrame(() => {
            out.scrollTop = out.scrollHeight;
        });

        this.saveToHistory({
            htmlContent: feedbackLine.outerHTML,
            timestamp: timestamp
        });
    }

    handleNewScreenshot(data) {
        console.log('收到新截图通知:', data);

        const modalTitle = document.querySelector('#screenshotModal .modal-title');
        const modalImage = document.getElementById('screenshotImage');
        const downloadLink = document.getElementById('screenshotDownloadLink');

        if (modalTitle) modalTitle.textContent = `来自客户端 ${data.client_id} 的新截图`;
        if (modalImage) modalImage.src = data.url;
        if (downloadLink) {
            downloadLink.href = data.url;
            downloadLink.download = data.filename;
        }

        const modal = document.getElementById('screenshotModal');
        if (modal) {
            modal.style.display = 'flex';
        }
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
            const out = document.getElementById("output");
            if (out) {
                out.innerHTML = '';
                this.messageHistory.forEach(msg => {
                    out.innerHTML += msg.htmlContent;
                });
                out.scrollTop = out.scrollHeight;
            }
        }
    }

    loadQuickConnections() {
        fetch('/api/connections')
            .then(response => response.json())
            .then(data => {
                this.displayQuickConnections(data.connections);
            })
            .catch(error => {
                console.error('加载快速连接失败:', error);
            });
    }

    displayQuickConnections(connections) {
        const container = document.getElementById('quick-connections');
        const emptyState = document.getElementById('empty-connections');
        
        if (!container) return;
        
        if (connections.length === 0) {
            if (container) container.style.display = 'none';
            if (emptyState) emptyState.style.display = 'block';
            return;
        }
        
        container.style.display = 'grid';
        if (emptyState) emptyState.style.display = 'none';
        
        // 只显示前6个连接
        const recentConnections = connections.slice(0, 6);
        
        container.innerHTML = recentConnections.map(conn => `
            <div class="connection-card" onclick="dashboard.quickConnect('${conn.id}')">
                <div class="connection-header">
                    <h6 class="connection-name">${conn.name}</h6>
                    <span class="connection-type ${conn.type}">${conn.type.toUpperCase()}</span>
                </div>
                <div class="connection-details">
                    <i class='bx bx-server'></i> ${conn.host}:${conn.port}
                    ${conn.username ? `<br><i class='bx bx-user'></i> ${conn.username}` : ''}
                </div>
                <div class="connection-stats">
                    连接次数: ${conn.connection_count}
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
                if (data.type === 'vnc') {
                    window.open(data.redirect_url, '_blank');
                } else if (data.type === 'rdp') {
                    window.open(data.redirect_url, '_blank');
                } else if (data.type === 'ssh') {
                    window.open(data.redirect_url, '_blank');
                }
            } else {
                alert('连接失败: ' + data.error);
            }
        })
        .catch(error => {
            console.error('连接失败:', error);
            alert('连接失败');
        });
    }
}

// 全局实例
let dashboard;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    dashboard = new Dashboard();
    dashboard.populateClientsInitial();
});

// 全局函数（保持向后兼容）
function sendCommand() {
    dashboard?.sendCommand();
}

function sendQuickCommand(action, arg = '') {
    dashboard?.sendQuickCommand(action, arg);
}

function showInput(cmd) {
    dashboard?.showInput(cmd);
}

function sendParamCommand() {
    dashboard?.sendParamCommand();
    const modal = document.getElementById('screenshotModal');
}

function useCommand(cmd) {
    dashboard?.useCommand(cmd);
}

function quickConnect(connectionId) {
    dashboard?.quickConnect(connectionId);
}

function closeModal() {
    if (modal) {
      modal.style.display = 'flex';
    modal.classList.remove('active');
    setTimeout(() => modal.style.display = 'none', 300);
    }
}