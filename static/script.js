const socket = io();
let playerId;
const canvas = document.getElementById('grid');
const ctx = canvas.getContext('2d');
const cellSize = 100; // 保持单元格大小不变，因为canvas已经扩大到900x900

socket.on('player_id', (id) => {
    playerId = id;
    document.getElementById('status').innerText = `Your ID: ${playerId}`;
});

socket.on('game_started', (data) => {
    // 清空事件面板
    const activeEvents = document.getElementById('active-events');
    activeEvents.innerHTML = '';
    updateGame(data);
});

socket.on('update', (data) => {
    updateGame(data);
});

socket.on('game_over', (data) => {
    document.getElementById('status').innerText = `Game Over! Winner: ${data.winner}`;
});

socket.on('error', (msg) => {
    document.getElementById('status').innerText = msg;
});

// 获取事件图标
function getEventIcon(type) {
    switch (type) {
        case 'resource': return 'fa-gem';
        case 'building': return 'fa-building';
        case 'terrain': return 'fa-mountain';
        case 'special': return 'fa-star';
        default: return 'fa-bolt';
    }
}

// 创建事件元素HTML
function createEventElementHTML(event) {
    const eventIcon = getEventIcon(event.type);
    return `
        <div class="event-icon">
            <i class="fas ${eventIcon}"></i>
        </div>
        <div class="event-details">
            <div class="event-name">${event.name}</div>
            <div class="event-description">${event.description}</div>
        </div>
        <div class="event-duration">
            持续: ${event.duration} 回合
        </div>
    `;
}

// 更新事件面板
function updateEventPanel(events) {
    const eventsPanel = document.getElementById('active-events');
    const currentEvents = Array.from(eventsPanel.children);
    const newEvents = new Set(events.map(e => e.name));
    
    // 移除已经不存在的事件
    currentEvents.forEach(element => {
        const eventName = element.querySelector('.event-name').textContent;
        if (!newEvents.has(eventName)) {
            element.style.opacity = '0';
            element.style.transform = 'translateY(-20px)';
            setTimeout(() => element.remove(), 500);
        }
    });
    
    // 添加或更新事件
    events.forEach(event => {
        const existingElement = Array.from(eventsPanel.children).find(
            el => el.querySelector('.event-name').textContent === event.name
        );
        
        if (existingElement) {
            // 更新持续时间
            const durationElement = existingElement.querySelector('.event-duration');
            durationElement.textContent = `持续: ${event.duration} 回合`;
        } else {
            // 创建新事件元素
            const eventElement = document.createElement('div');
            eventElement.className = `event-item event-type-${event.type}`;
            eventElement.style.opacity = '0';
            eventElement.style.transform = 'translateY(-20px)';
            eventElement.innerHTML = createEventElementHTML(event);
            eventsPanel.appendChild(eventElement);
            
            // 触发动画
            setTimeout(() => {
                eventElement.style.opacity = '1';
                eventElement.style.transform = 'translateY(0)';
            }, 50);
        }
    });
}

// 处理事件触发
socket.on('event_triggered', (event) => {
    const eventsPanel = document.getElementById('active-events');
    const eventElement = document.createElement('div');
    eventElement.className = `event-item event-type-${event.type}`;
    eventElement.innerHTML = createEventElementHTML(event);
    eventsPanel.appendChild(eventElement);
});

// 处理额外建造机会
socket.on('extra_build_available', (data) => {
    if (data.player === playerId) {
        document.getElementById('status').innerHTML = `
            <div class="status-container">
                <div class="status-text">
                    <i class="fas fa-hammer"></i>
                    快速建造已触发！你可以再次建造一个建筑
                </div>
            </div>
        `;
    }
});

function startGame() {
    socket.emit('start_game');
}

function makeMove(action, position = null) {
    socket.emit('move', { player: playerId, action: action, position: position });
}

function updateGame(data) {
    // 更新事件面板
    updateEventPanel(data.active_events || []);

    // 更新状态显示
    let statusText;
    let roundInfo = '';
    
    if (data.message) {
        statusText = data.message;
    } else if (data.currentPlayer) {
        let currentPlayerName;
        if (data.currentPlayer === 'player') {
            currentPlayerName = '自由之邦';
        } else if (data.currentPlayer === 'AI1') {
            currentPlayerName = '钢铁之心';
        } else if (data.currentPlayer === 'AI2') {
            currentPlayerName = '机械神国';
        }
        statusText = `当前行动玩家: ${currentPlayerName}`;
        if (data.round) {
            roundInfo = `<div class="round-info">第 ${data.round} / ${data.maxRounds} 回合</div>`;
        }
    } else {
        statusText = 'Waiting for game to start...';
    }
    
    document.getElementById('status').innerHTML = `
        <div class="status-container">
            <div class="status-text">
                <i class="fas fa-info-circle"></i>
                ${statusText}
            </div>
            ${roundInfo}
        </div>
    `;

    // 设置绘图样式
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#3498db';
    ctx.font = 'bold 24px Roboto';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // 绘制网格
    for (let i = 0; i < 9; i++) {
        for (let j = 0; j < 9; j++) {
            // 绘制单元格
            ctx.strokeRect(i * cellSize, j * cellSize, cellSize, cellSize);
            
            const cell = data.grid[j][i];
            if (cell === 'river') {
                // 绘制河流
                const gradient = ctx.createLinearGradient(
                    i * cellSize, j * cellSize,
                    (i + 1) * cellSize, (j + 1) * cellSize
                );
                gradient.addColorStop(0, '#4A90E2');
                gradient.addColorStop(1, '#357ABD');
                ctx.fillStyle = gradient;
                ctx.fillRect(i * cellSize, j * cellSize, cellSize, cellSize);
                
                // 添加波浪图案
                ctx.font = '32px "Font Awesome 5 Free"';
                ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
                ctx.fillText('\uf773', // fa-water
                           i * cellSize + cellSize/2,
                           j * cellSize + cellSize/2);
            }
            // 如果格子被占领，绘制玩家标记
            else if (cell) {
                // 为不同玩家使用不同颜色和图标
                if (cell === 'player') {
                    ctx.fillStyle = '#3498db';  // 蓝色 - 自由之邦
                    ctx.font = '48px "Font Awesome 5 Free"';
                    ctx.fillText('\uf521', // fa-crown
                               i * cellSize + cellSize/2,
                               j * cellSize + cellSize/2);
                } else if (cell === 'AI1') {
                    ctx.fillStyle = '#e74c3c';  // 红色 - 钢铁之心
                    ctx.font = '48px "Font Awesome 5 Free"';
                    ctx.fillText('\uf3ed', // fa-shield-halved
                               i * cellSize + cellSize/2,
                               j * cellSize + cellSize/2);
                } else if (cell === 'AI2') {
                    ctx.fillStyle = '#8e44ad';  // 紫色 - 机械神国
                    ctx.font = '48px "Font Awesome 5 Free"';
                    ctx.fillText('\uf71b', // fa-sword
                               i * cellSize + cellSize/2,
                               j * cellSize + cellSize/2);
                }
            }
        }
    }

    // 更新事件面板
    const activeEvents = document.getElementById('active-events');
    if (data.active_events) {
        activeEvents.innerHTML = '';
        data.active_events.forEach(event => {
            let eventIcon;
            switch (event.type) {
                case 'resource':
                    eventIcon = 'fa-gem';
                    break;
                case 'building':
                    eventIcon = 'fa-building';
                    break;
                case 'terrain':
                    eventIcon = 'fa-mountain';
                    break;
                case 'special':
                    eventIcon = 'fa-star';
                    break;
                default:
                    eventIcon = 'fa-bolt';
            }
            
            const eventElement = document.createElement('div');
            eventElement.className = `event-item event-type-${event.type}`;
            eventElement.innerHTML = `
                <div class="event-icon">
                    <i class="fas ${eventIcon}"></i>
                </div>
                <div class="event-details">
                    <div class="event-name">${event.name}</div>
                    <div class="event-description">${event.description}</div>
                </div>
                <div class="event-duration">
                    持续: ${event.duration} 回合
                </div>
            `;
            activeEvents.appendChild(eventElement);
        });
    }

    // 更新资源显示
    let resourcesDiv = document.getElementById('resources');
    resourcesDiv.innerHTML = '';
    for (let player in data.resources) {
        const resources = data.resources[player];
        let playerIcon, playerName;
        if (player === 'player') {
            playerIcon = 'fa-crown';
            playerName = '自由之邦';
        } else if (player === 'AI1') {
            playerIcon = 'fa-shield-halved';
            playerName = '钢铁之心';
        } else if (player === 'AI2') {
            playerIcon = 'fa-sword';
            playerName = '机械神国';
        }
        const isCurrentPlayer = player === data.currentPlayer;
        resourcesDiv.innerHTML += `
            <div class="resource-item ${isCurrentPlayer ? 'current-player' : ''}">
                <i class="fas ${playerIcon}"></i>
                <span>${playerName}</span>
                <div class="resource-details">
                    <div class="resource-value">
                        <i class="fas fa-tree"></i>
                        <span>${resources.wood}</span>
                    </div>
                    <div class="resource-value">
                        <i class="fas fa-coins"></i>
                        <span>${resources.gold}</span>
                    </div>
                </div>
            </div>
        `;
    }
}

// 点击占领格子
canvas.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / cellSize);
    const y = Math.floor((e.clientY - rect.top) / cellSize);
    makeMove('occupy', [x, y]);
});

// 规则弹窗控制
function showRules() {
    const modal = document.getElementById('rulesModal');
    modal.style.display = 'block';
}

// 获取关闭按钮和弹窗
const modal = document.getElementById('rulesModal');
const closeBtn = document.getElementsByClassName('close')[0];

// 点击关闭按钮关闭弹窗
closeBtn.onclick = function() {
    modal.style.display = 'none';
}

// 点击弹窗外部关闭弹窗
window.onclick = function(event) {
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}