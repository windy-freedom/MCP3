const socket = io();
let playerId;
const canvas = document.getElementById('grid');
const ctx = canvas.getContext('2d');
const cellSize = 100;

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
    // 绘制网格
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < 3; i++) {
        for (let j = 0; j < 3; j++) {
            ctx.strokeRect(i * cellSize, j * cellSize, cellSize, cellSize);
            if (data.grid[j][i]) {
                ctx.fillText(data.grid[j][i], i * cellSize + 40, j * cellSize + 60);
            }
        }
    }
    // 更新资源
    let resourcesDiv = document.getElementById('resources');
    resourcesDiv.innerHTML = '';
    for (let player in data.resources) {
        resourcesDiv.innerHTML += `${player}: Wood=${data.resources[player].wood}, Gold=${data.resources[player].gold}<br>`;
    }
}

// 点击占领格子
canvas.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / cellSize);
    const y = Math.floor((e.clientY - rect.top) / cellSize);
    makeMove('occupy', [x, y]);
});