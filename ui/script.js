let ws;
let selectedPiece = null; // 当前选中的棋子
const GRID_SIZE = 80;  // 格子大小
const BOARD_PADDING = 40;  // 棋盘边距

// 全局设置
let currentSettings = {
    thinkTime: 4.0  // 默认思考时间4秒
};

// 应用设置函数
function applySettings() {
    const thinkTimeSelect = document.getElementById('thinkTime');
    currentSettings.thinkTime = parseFloat(thinkTimeSelect.value);
    
    // 发送设置到服务器
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'settings',
            thinkTime: currentSettings.thinkTime
        }));
    }
    
    addLogMessage('系统', `AI思考时间已设置为 ${currentSettings.thinkTime} 秒`);
}

// WebSocket连接
function connectWebSocket() {
    ws = new WebSocket('ws://localhost:8000');
    
    ws.onopen = function(event) {
        console.log('WebSocket连接已建立');
        addLogMessage('系统', 'WebSocket连接已建立');
    };
    
    ws.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (error) {
            console.error('解析WebSocket消息失败:', error);
        }
    };
    
    ws.onclose = function(event) {
        console.log('WebSocket连接已关闭');
        addLogMessage('系统', 'WebSocket连接已关闭');
        // 尝试重新连接
        setTimeout(connectWebSocket, 3000);
    };
    
    ws.onerror = function(error) {
        console.error('WebSocket错误:', error);
        addLogMessage('系统', 'WebSocket连接错误');
    };
}

function handleWebSocketMessage(data) {
    switch(data.type) {
        case 'log':
            addLogMessage('AI', data.message);
            // 如果是搜索开始，添加搜索状态
            if (data.message === 'AI开始思考...') {
                addSearchingIndicator();
            }
            // 如果是搜索结束，移除搜索状态
            if (data.message.includes('AI最终移动:')) {
                removeSearchingIndicator();
            }
            break;
        case 'move':
            handleAIMove(data.move);
            break;
        case 'error':
            addLogMessage('错误', data.message);
            break;
        case 'settings':
            addLogMessage('系统', `服务器已确认设置: AI思考时间 ${data.thinkTime} 秒`);
            break;
        default:
            console.log('未知消息类型:', data);
    }
}

function addSearchingIndicator() {
    const logHeader = document.querySelector('.log-header h3');
    if (logHeader) {
        logHeader.innerHTML = 'AI思考日志 <span class="searching-indicator">🔍 思考中...</span>';
    }
}

function removeSearchingIndicator() {
    const logHeader = document.querySelector('.log-header h3');
    if (logHeader) {
        logHeader.innerHTML = 'AI思考日志';
    }
}

function addLogMessage(sender, message) {
    const logContent = document.getElementById('logContent');
    const logEntry = document.createElement('p');
    
    // 添加时间戳
    const now = new Date();
    const timeString = now.toLocaleTimeString();
    
    // 根据发送者设置不同的样式
    let className = '';
    let prefix = '';
    
    switch(sender) {
        case 'AI':
            className = 'ai-log';
            prefix = '🤖';
            break;
        case '系统':
            className = 'system-log';
            prefix = '⚙️';
            break;
        case '错误':
            className = 'error-log';
            prefix = '❌';
            break;
        default:
            className = 'user-log';
            prefix = '👤';
    }
    
    logEntry.className = className;
    logEntry.innerHTML = `<span class="time">[${timeString}]</span> <span class="sender">${prefix} ${sender}:</span> ${message}`;
    
    // 添加淡入动画
    logEntry.style.opacity = '0';
    logEntry.style.transform = 'translateY(-10px)';
    logEntry.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    
    logContent.appendChild(logEntry);
    
    // 触发动画
    setTimeout(() => {
        logEntry.style.opacity = '1';
        logEntry.style.transform = 'translateY(0)';
    }, 10);
    
    // 自动滚动到底部
    logContent.scrollTop = logContent.scrollHeight;
    
    // 如果是AI的搜索信息，添加特殊效果
    if (sender === 'AI' && message.includes('搜索深度:')) {
        logEntry.style.borderLeftColor = '#FF9800';
        logEntry.style.background = 'linear-gradient(90deg, #fff3e0 0%, #ffecb3 100%)';
        
        // 添加脉冲效果
        setTimeout(() => {
            logEntry.style.borderLeftColor = '#4CAF50';
            logEntry.style.background = '#f1f8e9';
        }, 500);
    }
}

function clearLog() {
    const logContent = document.getElementById('logContent');
    logContent.innerHTML = '';
    addLogMessage('系统', '日志已清空');
}

function initializeBoard() {
    const chessboard = document.querySelector('.chessboard');
    const pieces = document.querySelectorAll('.piece');

    // 初始化棋子位置
    pieces.forEach(piece => {
        const position = piece.getAttribute('data-position');
        if (position) {
            const [col, row] = position.split('');
            const x = col.charCodeAt(0) - 'a'.charCodeAt(0);
            const y = parseInt(row);
            
            piece.style.left = `${BOARD_PADDING + x * GRID_SIZE}px`;
            piece.style.top = `${BOARD_PADDING + (9 - y) * GRID_SIZE}px`;
            // 确保棋子在最上层
            piece.style.zIndex = "100";
        }
    });

    // 确保棋盘网格在底层
    const boardGrid = document.querySelector('.board-grid');
    if (boardGrid) {
        boardGrid.style.zIndex = "1";
    }

    // 移除所有现有的点击事件
    document.removeEventListener('click', handleGlobalClick, true);
    
    // 在document级别添加一个捕获阶段的点击事件处理器
    document.addEventListener('click', handleGlobalClick, true);
}

function handleGlobalClick(event) {
    console.log("Global click handler triggered");
    
    // 检查是否点击了棋子
    if (event.target.classList.contains('piece')) {
        console.log("Piece clicked");
        event.stopPropagation();
        handlePieceClick(event);
        return;
    }

    // 检查是否点击了棋盘
    const chessboard = document.querySelector('.chessboard');
    if (event.target === chessboard || event.target.classList.contains('board-grid')) {
        console.log("Board clicked");
        handleBoardClick(event);
    }
}

function handlePieceClick(event) {
    console.log("handlePieceClick processing");
    const piece = event.target;
    
    if (selectedPiece === piece) {
        console.log("Deselecting piece");
        deselectPiece();
    } else if (selectedPiece) {
        console.log("Attempting to capture piece");
        const fromPos = selectedPiece.getAttribute('data-position');
        const toPos = piece.getAttribute('data-position');
        makeMove(fromPos, toPos);
    } else {
        console.log("Selecting new piece");
        selectPiece(piece);
    }
}

function handleBoardClick(event) {
    console.log("handleBoardClick processing");
    if (!selectedPiece) return;

    const chessboard = document.querySelector('.chessboard');
    const rect = chessboard.getBoundingClientRect();
    const x = event.clientX - rect.left - BOARD_PADDING;
    const y = event.clientY - rect.top - BOARD_PADDING;

    const col = Math.round(x / GRID_SIZE);
    const row = 9 - Math.round(y / GRID_SIZE);

    if (col >= 0 && col < 9 && row >= 0 && row < 10) {
        const toPos = `${String.fromCharCode(97 + col)}${row}`;
        const fromPos = selectedPiece.getAttribute('data-position');
        makeMove(fromPos, toPos);
    }
}

function selectPiece(piece) {
    if (selectedPiece) {
        selectedPiece.classList.remove('selected');
    }
    selectedPiece = piece;
    piece.classList.add('selected');
}

function deselectPiece() {
    if (selectedPiece) {
        selectedPiece.classList.remove('selected');
        selectedPiece = null;
    }
}

function makeMove(fromPos, toPos) {
    // 移除之前的AI移动高亮效果
    const previousHighlight = document.querySelector('.ai-moved');
    if (previousHighlight) {
        previousHighlight.classList.remove('ai-moved');
    }

    console.log(`Moving piece from ${fromPos} to ${toPos}`);
    
    // 移动玩家的棋子
    const movingPiece = document.querySelector(`[data-position="${fromPos}"]`);
    const targetPiece = document.querySelector(`[data-position="${toPos}"]`);
    
    if (targetPiece) {
        targetPiece.remove();
    }
    
    movingPiece.setAttribute('data-position', toPos);
    
    const col = toPos.charCodeAt(0) - 97;
    const row = 9 - parseInt(toPos.slice(1));
    
    movingPiece.style.left = `${col * GRID_SIZE + BOARD_PADDING}px`;
    movingPiece.style.top = `${row * GRID_SIZE + BOARD_PADDING}px`;
    
    if (selectedPiece) {
        selectedPiece.classList.remove('selected');
        selectedPiece = null;
    }

    // 通过WebSocket发送移动
    if (ws && ws.readyState === WebSocket.OPEN) {
        const move = `${fromPos}${toPos}`;
        ws.send(JSON.stringify({
            type: 'move',
            move: move
        }));
        addLogMessage('玩家', `移动: ${fromPos} → ${toPos}`);
    } else {
        addLogMessage('错误', 'WebSocket连接未建立，无法发送移动');
    }
}

function handleAIMove(aiMove) {
    if (!aiMove || aiMove === "You lost" || aiMove === "You won" || aiMove === "ErrInvalidMove") {
        addLogMessage('系统', `游戏状态: ${aiMove}`);
        return;
    }
    
    // 解析AI的移动 (例如 "h7h6")
    const aiFromPos = aiMove.substring(0, 2);
    const aiToPos = aiMove.substring(2, 4);
    
    console.log(`AI moves from ${aiFromPos} to ${aiToPos}`);
    
    // 延迟一小段时间后执行AI的移动，让玩家能看清楚
    setTimeout(() => {
        const aiPiece = document.querySelector(`[data-position="${aiFromPos}"]`);
        const aiTargetPiece = document.querySelector(`[data-position="${aiToPos}"]`);
        
        if (aiTargetPiece) {
            aiTargetPiece.remove();
        }
        
        if (aiPiece) {
            aiPiece.setAttribute('data-position', aiToPos);
            
            const aiCol = aiToPos.charCodeAt(0) - 97;
            const aiRow = 9 - parseInt(aiToPos.slice(1));
            
            aiPiece.style.left = `${aiCol * GRID_SIZE + BOARD_PADDING}px`;
            aiPiece.style.top = `${aiRow * GRID_SIZE + BOARD_PADDING}px`;

            // 添加高亮效果
            aiPiece.classList.add('ai-moved');
        }
    }, 500);  // 500ms 延迟
}

function updateStatus(message, color) {
    const status = document.getElementById('status');
    status.textContent = message;
    status.style.color = color;
}

// 页面加载时初始化设置
document.addEventListener('DOMContentLoaded', function() {
    // 初始化棋盘
    initializeBoard();
    
    // 连接WebSocket
    connectWebSocket();
}); 