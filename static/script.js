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

function startGame() {
    socket.emit('start_game');
}

function makeMove(action, position = null) {
    socket.emit('move', { player: playerId, action: action, position: position });
}

function updateGame(data) {
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
            
            // 如果格子被占领，绘制玩家标记
            if (data.grid[j][i]) {
                const player = data.grid[j][i];
                // 为不同玩家使用不同颜色
                ctx.fillStyle = player === 'player' ? '#3498db' : '#e74c3c';
                ctx.fillText(player === 'player' ? '👤' : '🤖',
                           i * cellSize + cellSize/2,
                           j * cellSize + cellSize/2);
            }
        }
    }

    // 更新资源显示
    let resourcesDiv = document.getElementById('resources');
    resourcesDiv.innerHTML = '<h2>Resources</h2>';
    for (let player in data.resources) {
        const resources = data.resources[player];
        const playerEmoji = player === 'player' ? '👤' : '🤖';
        resourcesDiv.innerHTML += `
            <div class="player-resources">
                <span>${playerEmoji} ${player}</span>:
                <span>🌳 Wood: ${resources.wood}</span> |
                <span>💰 Gold: ${resources.gold}</span>
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