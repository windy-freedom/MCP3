from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import random
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple, Any

@dataclass
class Event:
    name: str
    description: str
    effect: dict
    duration: int
    type: str

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
        self.active_events: Dict[str, Event] = {}  # 当前生效的事件
        self.event_history: List[Event] = []  # 事件历史
        
        # 随机生成河流地块 (约10%的地块)
        river_count = int(grid_size * grid_size * 0.1)
        river_positions = random.sample([(i, j) for i in range(grid_size) for j in range(grid_size)], river_count)
        for i, j in river_positions:
            self.grid[i][j] = "river"
        
        # 定义所有可能的事件
        self.all_events = {
            # 资源事件
            "resource_boom": Event(
                name="资源繁荣",
                description="资源收集效率提升",
                effect={"resource_multiplier": 1.5},
                duration=2,
                type="resource"
            ),
            "gold_rush": Event(
                name="金矿潮",
                description="金币收集翻倍",
                effect={"gold_multiplier": 2},
                duration=1,
                type="resource"
            ),
            "wood_blessing": Event(
                name="森林祝福",
                description="木材收集翻倍",
                effect={"wood_multiplier": 2},
                duration=1,
                type="resource"
            ),
            # 建筑事件
            "construction_discount": Event(
                name="建筑折扣",
                description="占领费用减少1个资源",
                effect={"build_discount": 1},
                duration=2,
                type="building"
            ),
            "rapid_build": Event(
                name="快速建造",
                description="本回合可以连续占领两格",
                effect={"extra_build": True},
                duration=1,
                type="building"
            ),
            # 地形事件
            "river_shift": Event(
                name="河流改道",
                description="部分河流位置发生改变",
                effect={"river_change": True},
                duration=1,
                type="terrain"
            ),
            # 特殊事件
            "market_trade": Event(
                name="市场交易",
                description="可以1:1交换资源",
                effect={"resource_trade": True},
                duration=1,
                type="special"
            )
        }

    def available_moves(self, player):
        moves = [("collect_wood", None), ("collect_gold", None)]
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                # 只允许在空地块上建造
                if self.grid[i][j] is None:
                    moves.append(("occupy", (i, j)))
        return moves

    def is_valid_position(self, position):
        x, y = position
        # 检查坐标是否在网格范围内
        if not (0 <= x < self.grid_size and 0 <= y < self.grid_size):
            return False
        # 检查是否是空地块（不是河流也不是已占领）
        return self.grid[y][x] is None

    def check_and_trigger_events(self) -> Optional[Event]:
        """检查并触发随机事件，返回触发的事件"""
        current_round = (self.turn // len(self.players)) + 1
        
        # 如果没有活跃事件，100%触发新事件
        # 如果有活跃事件，50%概率触发额外事件
        should_trigger = (len(self.active_events) == 0 or
                        (len(self.active_events) < 2 and random.random() < 0.5))
        
        if should_trigger:
            # 根据事件类型和当前回合设置权重
            available_events = []
            weights = []
            
            for event in self.all_events.values():
                if event.name not in self.active_events:
                    available_events.append(event)
                    base_weight = 1.0
                    
                    # 根据事件类型设置基础权重
                    if event.type == "resource":
                        base_weight = 3.0  # 资源事件更常见
                    elif event.type == "building":
                        base_weight = 2.0  # 建筑事件次之
                    
                    # 根据回合数调整权重
                    if current_round <= 5:
                        # 前5回合倾向于触发资源事件
                        if event.type == "resource":
                            base_weight *= 1.5
                    elif current_round >= 15:
                        # 后期倾向于触发特殊事件
                        if event.type == "special":
                            base_weight *= 1.5
                    
                    weights.append(base_weight)
            
            if available_events:
                new_event = random.choices(available_events, weights=weights, k=1)[0]
                event_instance = Event(
                    name=new_event.name,
                    description=new_event.description,
                    effect=new_event.effect.copy(),
                    duration=current_round + random.randint(2, 3),  # 持续到指定回合
                    type=new_event.type
                )
                self.active_events[new_event.name] = event_instance
                self.event_history.append(event_instance)
                return event_instance
        
        return None

    def apply_event_effects(self, action: str, player: str, resources_delta: Dict[str, int]) -> Dict[str, int]:
        """应用事件效果到资源变化上"""
        modified_delta = resources_delta.copy()
        current_round = (self.turn // len(self.players)) + 1
        
        # 只应用未过期的事件效果
        for event in self.active_events.values():
            if event.duration > current_round:  # 检查事件是否在当前回合仍然有效
                if action == "collect_wood" and "wood_multiplier" in event.effect:
                    modified_delta["wood"] = int(modified_delta["wood"] * event.effect["wood_multiplier"])
                elif action == "collect_gold" and "gold_multiplier" in event.effect:
                    modified_delta["gold"] = int(modified_delta["gold"] * event.effect["gold_multiplier"])
                elif action == "occupy" and "build_discount" in event.effect:
                    for resource in modified_delta:
                        if modified_delta[resource] < 0:  # 只对消耗进行折扣
                            modified_delta[resource] += event.effect["build_discount"]
                            modified_delta[resource] = min(modified_delta[resource], 0)  # 确保不会变成正数
        
        return modified_delta

    def apply_move(self, player, move):
        action, position = move
        
        # 计算当前大回合数
        current_round = (self.turn // len(self.players)) + 1
        
        # 在每个大回合开始时检查事件
        if self.turn % len(self.players) == 0:
            # 移除过期事件（基于大回合数）
            expired_events = [event_id for event_id, event in self.active_events.items()
                            if event.duration <= current_round]
            for event_id in expired_events:
                del self.active_events[event_id]
            
            # 触发新事件
            new_event = self.check_and_trigger_events()
            if new_event:
                # 设置事件结束回合数（当前回合数+持续回合数）
                new_event.duration = current_round + random.randint(2, 3)
                # 通过socket发送事件信息到前端
                emit('event_triggered', {
                    'name': new_event.name,
                    'description': new_event.description,
                    'type': new_event.type,
                    'duration': new_event.duration - current_round  # 发送剩余持续回合数
                }, broadcast=True)
        
        # 处理不同的行动
        if action == "collect_wood":
            resources_delta = {"wood": 3, "gold": 0}
            modified_delta = self.apply_event_effects(action, player, resources_delta)
            self.resources[player]["wood"] += modified_delta["wood"]
            self.turn += 1
            return True
            
        elif action == "collect_gold":
            resources_delta = {"wood": 0, "gold": 2}
            modified_delta = self.apply_event_effects(action, player, resources_delta)
            self.resources[player]["gold"] += modified_delta["gold"]
            self.turn += 1
            return True
            
        elif action == "occupy":
            x, y = position
            resources_delta = {"wood": -2, "gold": -1}
            modified_delta = self.apply_event_effects(action, player, resources_delta)
            
            required_wood = abs(modified_delta["wood"])
            required_gold = abs(modified_delta["gold"])
            
            if (self.is_valid_position((x, y)) and
                self.resources[player]["wood"] >= required_wood and
                self.resources[player]["gold"] >= required_gold):
                
                self.resources[player]["wood"] += modified_delta["wood"]
                self.resources[player]["gold"] += modified_delta["gold"]
                self.grid[y][x] = player
                self.turn += 1
                
                # 处理特殊事件效果
                extra_build = any(event.effect.get("extra_build", False)
                                for event in self.active_events.values())
                if extra_build:
                    emit('extra_build_available', {'player': player}, broadcast=True)
                
                return True
            return False  # 位置无效或资源不足时返回False
            
        return False  # 未知action时返回False

    def calculate_score(self, player):
        # 只计算非河流地块的占领分数
        territory_score = sum(1 for row in self.grid for cell in row if cell == player) * 2  # 领地分数权重加倍
        resource_score = (self.resources[player]["wood"] + self.resources[player]["gold"]) * 0.1  # 资源分数权重降低
        return territory_score + resource_score

    def is_game_over(self):
        current_round = (self.turn // len(self.players)) + 1
        # 只有在达到20回合或所有非河流格子都被占领时才结束
        all_occupied = all(self.grid[i][j] is not None and self.grid[i][j] != "river"
                         for i in range(self.grid_size)
                         for j in range(self.grid_size))
        return current_round > 20 or all_occupied

    def get_winner(self):
        scores = {p: self.calculate_score(p) for p in self.players}
        return max(scores, key=scores.get)

    def copy(self):
        new_state = GameState(self.grid_size, self.players)
        new_state.grid = [row[:] for row in self.grid]
        new_state.resources = {p: r.copy() for p, r in self.resources.items()}
        new_state.turn = self.turn
        new_state.active_events = {k: Event(
            name=v.name,
            description=v.description,
            effect=v.effect.copy(),
            duration=v.duration,
            type=v.type
        ) for k, v in self.active_events.items()}
        new_state.event_history = self.event_history.copy()
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
        
        current_round = (state.turn // len(state.players)) + 1
        while current_round <= 20 and not state.is_game_over():
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
        # 游戏开始时触发第一个事件
        new_event = server.state.check_and_trigger_events()
        
        # 计算当前回合数
        current_round = 1
        
        # 获取当前有效的事件
        active_events = [
            {
                'name': event.name,
                'description': event.description,
                'type': event.type,
                'duration': event.duration - current_round  # 计算剩余回合数
            }
            for event in server.state.active_events.values()
            if event.duration > current_round  # 只显示未过期的事件
        ]
        
        emit('game_started', {
            'grid': server.state.grid,
            'resources': server.state.resources,
            'round': current_round,
            'maxRounds': 20,
            'currentPlayer': all_players[0],
            'active_events': active_events
        }, broadcast=True)
        
        # 如果有事件触发，发送事件通知
        if new_event:
            emit('event_triggered', {
                'name': new_event.name,
                'description': new_event.description,
                'type': new_event.type,
                'duration': new_event.duration
            }, broadcast=True)
    else:
        emit('error', 'Not enough players')

@socketio.on('move')
def handle_move(data):
    player = data['player']
    action = data['action']
    position = tuple(data['position']) if data.get('position') else None
    if server.state and player in server.state.players:
        # 如果行动失败(比如点击河流),不增加回合数
        if server.state.apply_move(player, (action, position)) is False:
            # 发送错误消息和当前状态
            emit('error', '无法在河流上建造!', broadcast=True)
            # 计算当前回合数
            current_round = (server.state.turn // len(server.players)) + 1
            
            # 获取当前有效的事件
            active_events = [
                {
                    'name': event.name,
                    'description': event.description,
                    'type': event.type,
                    'duration': event.duration - current_round  # 计算剩余回合数
                }
                for event in server.state.active_events.values()
                if event.duration > current_round  # 只显示未过期的事件
            ]
            
            emit('update', {
                'grid': server.state.grid,
                'resources': server.state.resources,
                'turn': server.state.turn,
                'currentPlayer': player,  # 保持当前玩家
                'round': current_round,
                'maxRounds': 20,
                'active_events': active_events
            }, broadcast=True)
            return  # 直接返回，不执行后续逻辑
        
        # 行动成功，处理下一个玩家
        next_player_index = (server.state.turn % len(server.state.players))
        next_player = server.state.players[next_player_index]
        
        # 如果当前是AI2行动完，确保下一个是人类玩家
        if player == "AI2":
            next_player = "player"
        
        # 计算当前回合数
        current_round = (server.state.turn // len(server.players)) + 1
        
        # 获取当前有效的事件
        active_events = [
            {
                'name': event.name,
                'description': event.description,
                'type': event.type,
                'duration': event.duration - current_round  # 计算剩余回合数
            }
            for event in server.state.active_events.values()
            if event.duration > current_round  # 只显示未过期的事件
        ]
        
        # 发送更新状态
        emit('update', {
            'grid': server.state.grid,
            'resources': server.state.resources,
            'turn': server.state.turn,
            'currentPlayer': next_player,
            'round': current_round,
            'maxRounds': 20,
            'active_events': active_events
        }, broadcast=True)
        if server.state.is_game_over():
            emit('game_over', {'winner': server.state.get_winner()}, broadcast=True)
        else:
            # AI回合
            for ai in server.ai_players:
                if ai.name in server.state.players and not server.state.is_game_over():
                    # 计算当前回合数（基于玩家数量）
                    current_round = (server.state.turn // len(server.state.players)) + 1
                    current_round = min(current_round, 20)  # 最大回合数限制
                    
                    # 发送AI思考中的状态
                    emit('update', {
                        'grid': server.state.grid,
                        'resources': server.state.resources,
                        'turn': server.state.turn,
                        'currentPlayer': ai.name,
                        'message': 'AI思考中...',
                        'round': current_round,
                        'maxRounds': 20
                    }, broadcast=True)
                    
                    # 等待2秒
                    socketio.sleep(2)
                    
                    # AI行动
                    move = ai.get_action(server.state)
                    server.state.apply_move(ai.name, move)
                    
                    # 发送AI行动后的状态
                    next_player_index = (server.state.turn % len(server.state.players))
                    next_player = server.state.players[next_player_index]
                    
                    # 如果当前AI是AI2，确保下一个是人类玩家
                    if ai.name == "AI2":
                        next_player = "player"
                    
                    # 计算当前回合数（基于玩家数量）
                    current_round = (server.state.turn // len(server.state.players)) + 1
                    current_round = min(current_round, 20)  # 最大回合数限制
                    
                    # 获取当前有效的事件
                    active_events = [
                        {
                            'name': event.name,
                            'description': event.description,
                            'type': event.type,
                            'duration': event.duration - current_round  # 计算剩余回合数
                        }
                        for event in server.state.active_events.values()
                        if event.duration > current_round  # 只显示未过期的事件
                    ]
                    
                    emit('update', {
                        'grid': server.state.grid,
                        'resources': server.state.resources,
                        'turn': server.state.turn,
                        'currentPlayer': next_player,
                        'round': current_round,
                        'maxRounds': 20,
                        'active_events': active_events
                    }, broadcast=True)
                    if server.state.is_game_over():
                        emit('game_over', {'winner': server.state.get_winner()}, broadcast=True)
                        break

server = GameServer()
server.ai_players = [GameAI("AI1"), GameAI("AI2")]

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)