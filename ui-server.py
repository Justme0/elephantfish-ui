#!/usr/bin/env python3

import json, time, re, sys, io
import asyncio
import websockets
import threading
import queue
import contextlib

import elephantfish

# 关闭缓冲
print(io.DEFAULT_BUFFER_SIZE, flush=True)
sys.stdout = open('out.log', mode='w', buffering=1)
sys.stdout.reconfigure(line_buffering=True)

# 存储连接的客户端
connected_clients = set()

def broadcast_message(message):
    """向所有连接的客户端发送消息"""
    if connected_clients:
        asyncio.create_task(asyncio.gather(*[client.send(json.dumps(message)) for client in connected_clients]))

async def websocket_handler(websocket, path="/"):
    """处理WebSocket连接"""
    connected_clients.add(websocket)
    
    # 重置AI状态 - 为新的游戏会话初始化
    global hist, searcher
    hist = [elephantfish.Position(elephantfish.initial, 0)]
    searcher = elephantfish.Searcher()
    
    # 当前连接的think time设置
    current_think_time = elephantfish.THINK_TIME
    
    # 发送连接确认消息
    await websocket.send(json.dumps({
        'type': 'log',
        'message': "WebSocket连接已建立，AI状态已重置"
    }))
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get('type') == 'move':
                    # 处理移动请求
                    await process_move_async(websocket, data.get('move'), current_think_time)
                elif data.get('type') == 'settings':
                    # 处理设置请求
                    if 'thinkTime' in data:
                        current_think_time = float(data['thinkTime'])
                        await websocket.send(json.dumps({
                            'type': 'settings',
                            'thinkTime': current_think_time
                        }))
                        await websocket.send(json.dumps({
                            'type': 'log',
                            'message': f"AI思考时间已更新为 {current_think_time} 秒"
                        }))
            except json.JSONDecodeError:
                await websocket.send(json.dumps({'type': 'error', 'message': 'Invalid JSON'}))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)

async def process_move_async(websocket, input_move, think_time=None):
    """异步处理移动请求"""
    global hist, searcher
    
    if not input_move:
        await websocket.send(json.dumps({'type': 'error', 'message': 'Missing move parameter'}))
        return
    
    # 如果没有提供think_time，使用默认值
    if think_time is None:
        think_time = elephantfish.THINK_TIME

    try:
        # 发送开始处理的消息
        await websocket.send(json.dumps({
            'type': 'log',
            'message': f"玩家输入移动: {input_move}"
        }))

        if hist[-1].score <= -elephantfish.MATE_LOWER:
            await websocket.send(json.dumps({
                'type': 'log',
                'message': "游戏结束: 你输了"
            }))
            await websocket.send(json.dumps({'type': 'move', 'move': "You lost"}))
            return

        match = re.match('([a-i][0-9])'*2, input_move)
        if not match:
            await websocket.send(json.dumps({
                'type': 'log',
                'message': "错误: 请输入正确的移动格式，如 h2e2"
            }))
            await websocket.send(json.dumps({'type': 'move', 'move': "Please enter a move like h2e2"}))
            return

        move = elephantfish.parse(match.group(1)), elephantfish.parse(match.group(2))
        if move not in hist[-1].gen_moves():
            await websocket.send(json.dumps({
                'type': 'log',
                'message': "错误: 无效的移动"
            }))
            await websocket.send(json.dumps({'type': 'move', 'move': "ErrInvalidMove"}))
            return

        hist.append(hist[-1].move(move))
        await websocket.send(json.dumps({
            'type': 'log',
            'message': "玩家移动已执行"
        }))

        # 捕获并发送棋盘状态
        board_output = io.StringIO()
        with contextlib.redirect_stdout(board_output):
            elephantfish.print_pos(hist[-1].rotate())
        
        board_lines = board_output.getvalue().strip().split('\n')
        await websocket.send(json.dumps({
            'type': 'log',
            'message': "当前棋盘状态:"
        }))
        for line in board_lines:
            if line.strip():
                await websocket.send(json.dumps({
                    'type': 'log',
                    'message': line
                }))
                await asyncio.sleep(0.01)  # 小延迟让输出更流畅

        if hist[-1].score <= -elephantfish.MATE_LOWER:
            await websocket.send(json.dumps({
                'type': 'log',
                'message': "游戏结束: 你赢了"
            }))
            await websocket.send(json.dumps({'type': 'move', 'move': "You won"}))
            return

        # AI开始思考
        await websocket.send(json.dumps({
            'type': 'log',
            'message': "AI开始思考..."
        }))

        start = time.time()
        last_send_time = start
        
        for _depth, move, score in searcher.search(start, hist[-1], hist):
            current_time = time.time()
            cost = current_time - start
            
            # 立即发送搜索信息
            await websocket.send(json.dumps({
                'type': 'log',
                'message': f"搜索深度: {_depth}, 评分: {score}, 用时: {cost:.2f}秒"
            }))
            
            # 添加小延迟让输出更流畅
            await asyncio.sleep(0.05)
            
            if cost > think_time:
                break

        if score == elephantfish.MATE_UPPER:
            await websocket.send(json.dumps({
                'type': 'log',
                'message': "将军!"
            }))

        # AI最终移动
        ai_move = elephantfish.render(255-move[0] - 1) + elephantfish.render(255-move[1]-1)
        await websocket.send(json.dumps({
            'type': 'log',
            'message': f"AI最终移动: {ai_move}"
        }))
        await websocket.send(json.dumps({
            'type': 'log',
            'message': f"AI思考深度: {_depth}"
        }))
        await websocket.send(json.dumps({
            'type': 'log',
            'message': f"AI思考时间: {time.time() - start:.2f}秒"
        }))

        hist.append(hist[-1].move(move))

        # 发送最终棋盘状态
        await websocket.send(json.dumps({
            'type': 'log',
            'message': "移动后棋盘状态:"
        }))
        
        final_board_output = io.StringIO()
        with contextlib.redirect_stdout(final_board_output):
            elephantfish.print_pos(hist[-1])
        
        final_board_lines = final_board_output.getvalue().strip().split('\n')
        for line in final_board_lines:
            if line.strip():
                await websocket.send(json.dumps({
                    'type': 'log',
                    'message': line
                }))
                await asyncio.sleep(0.01)  # 小延迟让输出更流畅

        # 发送最终移动结果
        await websocket.send(json.dumps({'type': 'move', 'move': ai_move}))

    except Exception as e:
        await websocket.send(json.dumps({
            'type': 'error',
            'message': str(e)
        }))

def run_websocket_server(port=8000):
    """启动WebSocket服务器"""
    async def main():
        async with websockets.serve(websocket_handler, "localhost", port):
            print(f"Starting WebSocket server on port {port}...")
            await asyncio.Future()  # 保持服务器运行
    
    asyncio.run(main())

# 保留原有的HTTP服务器代码作为备用
from http.server import HTTPServer, SimpleHTTPRequestHandler

class ChessRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With, Content-type")
        SimpleHTTPRequestHandler.end_headers(self)

    def do_OPTIONS(self):
        print(f"===== get option req, path={self.path}")
        self.send_response(200, "ok")
        self.end_headers()

    def do_POST(self):
        print(f"===== get post req, path={self.path}")
        if self.path == '/move':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            move_data = json.loads(post_data.decode('utf-8'))

            move = move_data.get('move')
            if not move:
                self.send_error(400, "Missing move parameter")
                return

            try:
                ai_move, logs = process_move(move)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'move': ai_move, 'logs': logs}).encode('utf-8'))
            except Exception as e:
                self.send_error(500, str(e))

def run_http_server(port=8001):
    """启动HTTP服务器（备用）"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, ChessRequestHandler)
    print(f"Starting HTTP server on port {port}...")
    httpd.serve_forever()

hist = [elephantfish.Position(elephantfish.initial, 0)]
searcher = elephantfish.Searcher()

def process_move(input_move, think_time=None):
    """处理玩家的移动并返回 AI 的响应（HTTP版本）"""
    global hist, searcher
    
    # 如果没有提供think_time，使用默认值
    if think_time is None:
        think_time = elephantfish.THINK_TIME
    
    logs = []
    logs.append(f"玩家输入移动: {input_move}")

    if hist[-1].score <= -elephantfish.MATE_LOWER:
        logs.append("游戏结束: 你输了")
        return ("You lost"), logs

    match = re.match('([a-i][0-9])'*2, input_move)
    if not match:
        logs.append("错误: 请输入正确的移动格式，如 h2e2")
        return ("Please enter a move like h2e2"), logs

    move = elephantfish.parse(match.group(1)), elephantfish.parse(match.group(2))
    if move not in hist[-1].gen_moves():
        logs.append("错误: 无效的移动")
        return "ErrInvalidMove", logs

    hist.append(hist[-1].move(move))
    logs.append("玩家移动已执行")

    board_output = io.StringIO()
    with contextlib.redirect_stdout(board_output):
        elephantfish.print_pos(hist[-1].rotate())
    logs.append("当前棋盘状态:")
    logs.extend(board_output.getvalue().strip().split('\n'))

    if hist[-1].score <= -elephantfish.MATE_LOWER:
        logs.append("游戏结束: 你赢了")
        return ("You won"), logs

    start = time.time()
    logs.append("AI开始思考...")
    
    search_logs = []
    for _depth, move, score in searcher.search(start, hist[-1], hist):
        cost = time.time() - start
        search_logs.append(f"搜索深度: {_depth}, 评分: {score}, 用时: {cost:.2f}秒")
        if cost > think_time:
            break

    logs.extend(search_logs)

    if score == elephantfish.MATE_UPPER:
        logs.append("将军!")

    ai_move = elephantfish.render(255-move[0] - 1) + elephantfish.render(255-move[1]-1)
    logs.append(f"AI最终移动: {ai_move}")
    logs.append(f"AI思考深度: {_depth}")
    logs.append(f"AI思考时间: {time.time() - start:.2f}秒")
    
    hist.append(hist[-1].move(move))
    
    final_board_output = io.StringIO()
    with contextlib.redirect_stdout(final_board_output):
        elephantfish.print_pos(hist[-1])
    logs.append("移动后棋盘状态:")
    logs.extend(final_board_output.getvalue().strip().split('\n'))
    
    return ai_move, logs

if __name__ == '__main__':
    # 启动WebSocket服务器
    run_websocket_server()
