// 仪表板专用JavaScript
class Dashboard {
    constructor() {
        this.socket = null;
        this.currentCommandForParam = "";
        this.lastCommandsByClient = {}; // 记录最近一次发送给各客户端的命令文本
        this.messageHistory = [];
        this.maxHistory = 1000;
        this.lastTimeoutMessage = 0;
        this.timeoutMessageInterval = 5000;
        this.eventsInitialized = false;
        this.isConnected = false; // 添加连接状态标记
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
        // 如果socket已经存在且已连接，不重复初始化
        if (this.socket && this.socket.connected) {
            return;
        }
        
        this.socket = io();

        this.socket.on('connect', () => {
            // 删除连接消息显示，直接执行连接后的操作
            this.isConnected = true;
            this.populateClientsInitial();
        });

        this.socket.on('disconnect', () => {
            this.addFeedbackMessage('已与服务器断开连接');
            this.isConnected = false;
        });

        this.socket.on('command_result', (data) => {
            this.handleCommandResult(data);
        });

        // 安全策略阻止或错误反馈
        this.socket.on('command_response', (data) => {
            this.handleCommandResponse(data);
        });

        // 安全策略警告反馈（允许执行，但需提示）
        this.socket.on('command_warning', (data) => {
            this.handleCommandWarning(data);
        });

        this.socket.on('clients_list', (data) => {
            this.updateClientList(data);
        });

        this.socket.on('new_client', (data) => {
            this.addClient(data);
            this.addFeedbackMessage(`新客户端已连接: ${data.hostname || data.client_id}`);
        });

        this.socket.on('client_updated', (data) => {
            this.updateClient(data);
            this.addFeedbackMessage(`客户端信息已更新: ${data.hostname || data.client_id}`);
        });

        this.socket.on('client_disconnected', (data) => {
            this.removeClient(data.client_id);
            this.addFeedbackMessage(`客户端已断开连接: ${data.client_id}`);
        });

        this.socket.on('new_screenshot', (data) => {
            this.handleNewScreenshot(data);
        });
    }

    populateClientsInitial() {
        this.socket.emit('get_clients');
    }

    updateClientList(data) {
        const select = document.getElementById('client-select');
        const listContainer = document.getElementById('client-list');

        if (select) {
            const previouslySelected = select.value;
            select.innerHTML = '';

            if (!data || !data.clients || Object.keys(data.clients).length === 0) {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = '无在线客户端';
                option.disabled = true;
                select.appendChild(option);
            } else {
                const clientIds = Object.keys(data.clients);
                clientIds.forEach(clientId => {
                    const info = data.clients[clientId];
                    const option = document.createElement('option');
                    option.value = clientId;
                    const displayName = info.hostname || `客户端 ${clientId}`;
                    option.textContent = `${displayName} (${info.user || '未知'}) @ ${info.addr || '未知IP'}`;
                    select.appendChild(option);
                });

                if (clientIds.includes(previouslySelected)) {
                    select.value = previouslySelected;
                } else {
                    select.value = clientIds[0];
                }
            }
        }

        if (listContainer) {
            listContainer.innerHTML = '';
            if (!data || !data.clients || Object.keys(data.clients).length === 0) {
                listContainer.innerHTML = '<p>暂无连接的客户端</p>';
                return;
            }

            Object.keys(data.clients).forEach(clientId => {
                const info = data.clients[clientId];
                const card = this.createClientCard(clientId, info);
                listContainer.appendChild(card);
            });
        }
    }

    addClient(clientInfo) {
        const select = document.getElementById('client-select');
        const listContainer = document.getElementById('client-list');
        const clientId = clientInfo.client_id;

        if (select) {
            // 移除 "无在线客户端" 选项
            const noClientsOption = select.querySelector('option[value=""]');
            if (noClientsOption) {
                noClientsOption.remove();
            }

            const option = document.createElement('option');
            option.value = clientId;
            const displayName = clientInfo.hostname || `客户端 ${clientId}`;
            option.textContent = `${displayName} (${clientInfo.user || '未知'}) @ ${clientInfo.addr || '未知IP'}`;
            select.appendChild(option);
            if (select.options.length === 1) {
                select.value = clientId;
            }
        }

        if (listContainer) {
            // 移除 "暂无连接的客户端" 提示
            const noClientsMessage = listContainer.querySelector('p');
            if (noClientsMessage) {
                noClientsMessage.remove();
            }
            const card = this.createClientCard(clientId, clientInfo);
            listContainer.appendChild(card);
        }
    }

    updateClient(clientInfo) {
        const select = document.getElementById('client-select');
        const listContainer = document.getElementById('client-list');
        const clientId = clientInfo.client_id;

        if (select) {
            const option = select.querySelector(`option[value="${clientId}"]`);
            if (option) {
                const displayName = clientInfo.hostname || `客户端 ${clientId}`;
                option.textContent = `${displayName} (${clientInfo.user || '未知'}) @ ${clientInfo.addr || '未知IP'}`;
            }
        }

        if (listContainer) {
            const card = listContainer.querySelector(`.client-card[data-client-id="${clientId}"]`);
            if (card) {
                const newCard = this.createClientCard(clientId, clientInfo);
                card.replaceWith(newCard);
            }
        }
    }

    removeClient(clientId) {
        const select = document.getElementById('client-select');
        const listContainer = document.getElementById('client-list');

        if (select) {
            const option = select.querySelector(`option[value="${clientId}"]`);
            if (option) {
                option.remove();
            }
            if (select.options.length === 0) {
                const noClientsOption = document.createElement('option');
                noClientsOption.value = '';
                noClientsOption.textContent = '无在线客户端';
                noClientsOption.disabled = true;
                select.appendChild(noClientsOption);
            }
        }

        if (listContainer) {
            const card = listContainer.querySelector(`.client-card[data-client-id="${clientId}"]`);
            if (card) {
                card.remove();
            }
            if (listContainer.children.length === 0) {
                listContainer.innerHTML = '<p>暂无连接的客户端</p>';
            }
        }
    }

    createClientCard(clientId, info) {
        const card = document.createElement('div');
        card.className = 'client-card';
        card.dataset.clientId = clientId;
        const title = info.hostname || `客户端 ${clientId}`;
        card.innerHTML = `
            <div class="client-card-header">
              <span class="client-card-header"><i class='bx bx-laptop'></i> ${title}</span>
              <span class="client-status online"><span class="status-dot"></span> 在线</span>
            </div>
            <div class="client-card-body">
              <div><strong>用户：</strong>${info.user || '未知'}</div>
              <div><strong>IP：</strong>${info.addr || '未知IP'}</div>
              <div><strong>系统：</strong>${info.os || '未知'}</div>
            </div>
            <div class="client-card-actions">
              <button class="btn btn-primary" onclick="window.location.href='/?client=${clientId}'"><i class='bx bx-terminal'></i> 控制台</button>
              <button class="btn btn-success" onclick="dashboard.sendQuickCommand('screenshot', '', '${clientId}')"><i class='bx bx-camera'></i> 截屏</button>
            </div>
        `;
        return card;
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
        // 记录最近一次尝试发送给该客户端的命令文本（用于阻止/警告时提示）
        this.lastCommandsByClient[target] = cmdFull;
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
        // 记录最近一次尝试发送给该客户端的命令文本（用于阻止/警告时提示）
        this.lastCommandsByClient[target] = cmdDisplay;
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

    handleCommandResponse(data) {
        // 统一处理后端返回的响应，包括安全阻止与一般错误
        const out = document.getElementById('output');
        if (!out) return;

        const timestamp = new Date().toLocaleTimeString();
        const clientId = data.client_id || '未知客户端';

        if (data && data.error) {
            // 安全组阻止
            if (data.security_blocked) {
                const attempted = this.lastCommandsByClient[clientId] || '';
                const msg = data.error || '命令被安全策略阻止';
                this.addSecurityMessage(clientId, msg, 'block', attempted, data.rule_matched);
                return;
            }

            // 非安全阻止的一般错误
            const line = document.createElement('div');
            line.className = 'terminal-line terminal-error';
            const t = document.createElement('span');
            t.className = 'terminal-timestamp';
            t.textContent = `[${timestamp}] `;
            line.appendChild(t);
            const sys = document.createElement('span');
            sys.className = 'terminal-system';
            sys.textContent = '[系统] ';
            line.appendChild(sys);
            const cli = document.createElement('span');
            cli.className = 'terminal-client';
            cli.textContent = `[${clientId}] `;
            line.appendChild(cli);
            const content = document.createElement('span');
            content.textContent = data.error;
            line.appendChild(content);

            out.appendChild(line);
            requestAnimationFrame(() => { out.scrollTop = out.scrollHeight; });

            this.saveToHistory({ htmlContent: line.outerHTML, is_error: true, timestamp });
            return;
        }

        // 可选：命令已发送确认（目前不重复提示）
    }

    handleCommandWarning(data) {
        const out = document.getElementById('output');
        if (!out) return;

        const clientId = data.client_id || '未知客户端';
        const attempted = this.lastCommandsByClient[clientId] || '';
        const msg = data && data.message ? data.message : '命令触发安全警告';
        this.addSecurityMessage(clientId, msg, 'warn', attempted, data.rule_matched);
    }

    addSecurityMessage(clientId, message, level = 'warn', commandText = '', ruleMatched = '') {
        const out = document.getElementById('output');
        if (!out) return;

        const timestamp = new Date().toLocaleTimeString();
        const line = document.createElement('div');
        line.className = 'terminal-line';
        if (level === 'block') {
            line.classList.add('terminal-error');
        } else {
            line.classList.add('terminal-warning');
        }

        const t = document.createElement('span');
        t.className = 'terminal-timestamp';
        t.textContent = `[${timestamp}] `;
        line.appendChild(t);

        const tag = document.createElement('span');
        tag.className = 'terminal-system';
        tag.textContent = '[安全组] ';
        line.appendChild(tag);

        const cli = document.createElement('span');
        cli.className = 'terminal-client';
        cli.textContent = `[${clientId}] `;
        line.appendChild(cli);

        const textSpan = document.createElement('span');
        const prefix = level === 'block' ? '该客户端被禁止执行' : '该客户端触发安全警告';
        if (commandText) {
            textSpan.textContent = `${prefix}: ${commandText} (${message})`;
        } else {
            textSpan.textContent = `${prefix}: ${message}`;
        }
        line.appendChild(textSpan);

        if (ruleMatched) {
            const detail = document.createElement('small');
            detail.className = 'text-muted';
            detail.textContent = ` 规则匹配: ${ruleMatched}`;
            line.appendChild(detail);
        }

        out.appendChild(line);
        requestAnimationFrame(() => { out.scrollTop = out.scrollHeight; });

        const historyItem = { htmlContent: line.outerHTML, timestamp };
        if (level === 'block') historyItem.is_error = true; else historyItem.is_warning = true;
        this.saveToHistory(historyItem);
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
            .then(response => {
                const ct = response.headers.get('content-type') || '';
                if (!response.ok || !ct.includes('application/json')) {
                    throw new Error(`无效的响应: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                const connections = Array.isArray(data.connections) ? data.connections : [];
                this.displayQuickConnections(connections);
            })
            .catch(error => {
                console.error('加载快速连接失败:', error);
                this.displayQuickConnections([]);
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

// 仪表板专用JavaScript
function updateClientList(data) {
  const select = document.getElementById('client-select');
  const listContainer = document.getElementById('client-list');

  if (select) {
    const previouslySelected = select.value;
    select.innerHTML = '';

    if (!data || !data.clients || Object.keys(data.clients).length === 0) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = '无在线客户端';
      option.disabled = true;
      select.appendChild(option);
    } else {
      const clientIds = Object.keys(data.clients);
      clientIds.forEach(clientId => {
        const info = data.clients[clientId];
        const option = document.createElement('option');
        option.value = clientId;
        const displayName = info.hostname || `客户端 ${clientId}`;
        option.textContent = `${displayName} (${info.user || '未知'}) @ ${info.addr || '未知IP'}`;
        select.appendChild(option);
      });

      if (clientIds.includes(previouslySelected)) {
        select.value = previouslySelected;
      } else {
        select.value = clientIds[0];
      }
    }
  }

  if (listContainer) {
    listContainer.innerHTML = '';
    if (!data || !data.clients || Object.keys(data.clients).length === 0) {
      listContainer.innerHTML = '<p>暂无连接的客户端</p>';
      return;
    }

    Object.keys(data.clients).forEach(clientId => {
      const info = data.clients[clientId];
      const card = document.createElement('div');
      card.className = 'client-card';
      const title = info.hostname || `客户端 ${clientId}`;
      card.innerHTML = `
        <div class="client-card-header">
          <span class="client-card-header"><i class='bx bx-laptop'></i> ${title}</span>
          <span class="client-status online"><span class="status-dot"></span> 在线</span>
        </div>
        <div class="client-card-body">
          <div><strong>用户：</strong>${info.user || '未知'}</div>
          <div><strong>IP：</strong>${info.addr || '未知IP'}</div>
          <div><strong>系统：</strong>${info.os || '未知'}</div>
        </div>
        <div class="client-card-actions">
          <button class="btn btn-primary" onclick="window.location.href='/?client=${clientId}'"><i class='bx bx-terminal'></i> 控制台</button>
          <button class="btn btn-success" onclick="sendQuickCommand('screenshot', '', '${clientId}')"><i class='bx bx-camera'></i> 截屏</button>
        </div>
      `;
      listContainer.appendChild(card);
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
    const modal = document.getElementById('screenshotModal');
    if (modal) {
        modal.classList.remove('active');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    }
}