from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import random
import math
from collections import defaultdict

app = Flask(__name__)
socketio = SocketIO(app)

# 游戏状态类
class GameState:
    def __init__(self, grid_size, players):
        self.grid = [[None for _ in range(grid_size)] for _ in range(grid_size)]
        self.players = players
        self.resources = {p: {"wood": 10, "gold": 5} for p in players}
        self.turn = 0
        self.grid_size = grid_size

    def available_moves(self, player):
        moves = [("collect_wood", None), ("collect_gold", None)]
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if self.grid[i][j] is None:
                    moves.append(("occupy", (i, j)))
        return moves

    def apply_move(self, player, move):
        action, position = move
        if action == "collect_wood":
            self.resources[player]["wood"] += 3
        elif action == "collect_gold":
            self.resources[player]["gold"] += 2
        elif action == "occupy" and self.resources[player]["wood"] >= 2 and self.resources[player]["gold"] >= 1:
            self.resources[player]["wood"] -= 2
            self.resources[player]["gold"] -= 1
            self.grid[position[0]][position[1]] = player
        self.turn += 1

    def calculate_score(self, player):
        territory_score = sum(row.count(player) for row in self.grid)
        resource_score = (self.resources[player]["wood"] + self.resources[player]["gold"]) * 0.5
        return territory_score + resource_score

    def is_game_over(self):
        return self.turn >= 20 or all(self.grid[i][j] is not None for i in range(self.grid_size) for j in range(self.grid_size))

    def get_winner(self):
        scores = {p: self.calculate_score(p) for p in self.players}
        return max(scores, key=scores.get)

    def copy(self):
        new_state = GameState(self.grid_size, self.players)
        new_state.grid = [row[:] for row in self.grid]
        new_state.resources = {p: r.copy() for p, r in self.resources.items()}
        new_state.turn = self.turn
        return new_state

# MCTS节点
class MCTSNode:
    def __init__(self, state, player, parent=None, move=None):
        self.state = state
        self.player = player
        self.parent = parent
        self.move = move
        self.children = []
        self.wins = 0
        self.visits = 0
        self.untried_moves = state.available_moves(player)

    def select_child(self):
        exploration = 1.4  # 增加探索性
        return max(self.children, key=lambda c: c.wins / c.visits + exploration * math.sqrt(math.log(self.visits) / c.visits) if c.visits > 0 else float('inf'))

    def expand(self):
        move = self.untried_moves.pop(0)
        new_state = self.state.copy()
        new_state.apply_move(self.player, move)
        child = MCTSNode(new_state, self.player, self, move)
        self.children.append(child)
        return child

    def simulate(self):
        state = self.state.copy()
        current_player = self.player
        
        while not state.is_game_over():
            moves = state.available_moves(current_player)
            
            # 平衡策略：根据当前资源状态选择行动
            if moves:
                weights = []
                for move in moves:
                    action, _ = move
                    resources = state.resources[current_player]
                    
                    if action == "collect_wood" and resources["wood"] < 6:
                        weights.append(2.0)  # 木材少时增加收集概率
                    elif action == "collect_gold" and resources["gold"] < 4:
                        weights.append(2.0)  # 金币少时增加收集概率
                    elif action == "occupy" and resources["wood"] >= 2 and resources["gold"] >= 1:
                        weights.append(3.0)  # 有足够资源时倾向于占领
                    else:
                        weights.append(1.0)
                
                move = random.choices(moves, weights=weights)[0]
                state.apply_move(current_player, move)
            
            current_player = state.players[(state.players.index(current_player) + 1) % len(state.players)]
        
        # 根据综合得分评估结果
        final_score = state.calculate_score(self.player)
        max_possible_score = state.grid_size * state.grid_size + 20  # 最大可能分数
        return final_score / max_possible_score  # 归一化的得分

    def backpropagate(self, result):
        self.visits += 1
        self.wins += result
        if self.parent:
            self.parent.backpropagate(result)

# AI类
class GameAI:
    def __init__(self, name):
        self.name = name
        self.q_table = defaultdict(lambda: 0)
        self.learning_rate = 0.2  # 提高学习率
        self.discount = 0.8  # 降低折扣因子，更注重短期收益
        self.epsilon = 0.2  # 探索率

    def get_action(self, state, iterations=150):  # 增加迭代次数
        root = MCTSNode(state, self.name)
        
        for _ in range(iterations):
            node = root
            while node.untried_moves == [] and node.children != []:
                node = node.select_child()
            if node.untried_moves:
                node = node.expand()
            reward = node.simulate()
            node.backpropagate(reward)

        # 平衡探索和利用
        if random.random() < self.epsilon:
            return random.choice(state.available_moves(self.name))
        
        best_child = max(root.children, key=lambda c: c.visits)
        move = best_child.move
        
        # 更新Q值
        state_hash = str(state.grid) + str(state.resources[self.name])
        next_state = state.copy()
        next_state.apply_move(self.name, move)
        next_hash = str(next_state.grid) + str(next_state.resources[self.name])
        
        # 使用综合评分作为奖励
        reward = next_state.calculate_score(self.name) - state.calculate_score(self.name)
        
        self.q_table[(state_hash, move)] += self.learning_rate * (
            reward + self.discount * max(
                [self.q_table[(next_hash, m)] for m in next_state.available_moves(self.name)],
                default=0
            ) - self.q_table[(state_hash, move)]
        )
        
        return move

# 游戏服务器
class GameServer:
    def __init__(self):
        self.state = None
        self.players = []
        self.ai_players = []

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print('Player connected')
    server.players.append("player")
    emit('player_id', "player")

@socketio.on('start_game')
def start_game():
    if len(server.players) + len(server.ai_players) >= 2:
        all_players = server.players + [ai.name for ai in server.ai_players]
        server.state = GameState(grid_size=9, players=all_players)
        emit('game_started', {'grid': server.state.grid, 'resources': server.state.resources}, broadcast=True)
    else:
        emit('error', 'Not enough players')

@socketio.on('move')
def handle_move(data):
    player = data['player']
    action = data['action']
    position = tuple(data['position']) if data.get('position') else None
    if server.state and player in server.state.players:
        server.state.apply_move(player, (action, position))
        emit('update', {'grid': server.state.grid, 'resources': server.state.resources, 'turn': server.state.turn}, broadcast=True)
        if server.state.is_game_over():
            emit('game_over', {'winner': server.state.get_winner()}, broadcast=True)
        else:
            # AI回合
            for ai in server.ai_players:
                if ai.name in server.state.players and not server.state.is_game_over():
                    move = ai.get_action(server.state)
                    server.state.apply_move(ai.name, move)
                    emit('update', {'grid': server.state.grid, 'resources': server.state.resources, 'turn': server.state.turn}, broadcast=True)
                    if server.state.is_game_over():
                        emit('game_over', {'winner': server.state.get_winner()}, broadcast=True)
                        break

server = GameServer()
server.ai_players = [GameAI("AI1"), GameAI("AI2")]

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)