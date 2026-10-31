import zmq
import time
import json
import os

# 从配置文件读取服务器地址
def load_server_config():
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'signal_config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        
        # server_id = cfg.get('default_server_id', 'local')
        # server = cfg['servers'].get(server_id, 'localhost')
        # port = cfg.get('req_port', 3333)
        
        server = cfg['server'].get('host', 'localhost')
        port = cfg['server'].get('port', 3333)
        return f"tcp://{server}:{port}"
    except Exception as e:
        print(f"加载配置失败: {e}，使用默认地址")
        return "tcp://localhost:3333"

url = load_server_config()
print(f"连接到服务器: {url}")

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect(url)
socket.setsockopt(zmq.RCVTIMEO, 2000)  # Set receive timeout to 2000ms (2 seconds)
socket.setsockopt(zmq.SNDTIMEO, 2000)  # Set send timeout to 2000ms


def sendsignal(client_name, signal):
    """Sends a signal using non-blocking I/O.

    Args:
        client_name: The name of the client.
        signal: The signal to send.
    
    Returns:
        bool: True if successful, False otherwise
    """

    try:
        # Send the signal (non-blocking)
        socket.send_pyobj([client_name, signal], flags=zmq.NOBLOCK)
        print(f'[{client_name}] 信号已发送: {signal}')
        
        # Poll the socket for a reply
        poller = zmq.Poller()
        poller.register(socket, zmq.POLLIN)
        socks = dict(poller.poll(2000))  # Wait up to 2000ms for a reply

        if socket in socks and socks[socket] == zmq.POLLIN:
            # Receive the reply
            reply = socket.recv_pyobj(flags=zmq.NOBLOCK)
            print(f"[{client_name}] ✓ 收到回复: {reply}")
            return True
        else:
            print(f"[{client_name}] ✗ 超时：服务器未响应")
            print(f"  提示：请确认服务器已启动并监听 {url}")
            return False
            
    except zmq.error.Again:
        print(f"[{client_name}] ✗ 发送操作会阻塞")
        return False
        
    except zmq.error.ZMQError as e:
        print(f"[{client_name}] ✗ ZMQ错误: {e}")
        print(f"  可能原因：")
        print(f"  1. 服务器未启动")
        print(f"  2. 网络连接问题")
        print(f"  3. 端口被占用或防火墙阻止")
        return False
        
    except Exception as e:
        print(f"[{client_name}] ✗ 未知错误: {e}")
        return False

if __name__=='__main__':
    signal={'策略': '突破火线', '合约': 'SHFE.sn2408', '周期': 900, '时间': '09:45:00', '当前信号': '空', '持续周期': 17, '信号价格': 274170.0, '现价': 266810.0, '信号盈亏': 7370.0}
    sendsignal('signal', signal)
    print('signal sent...')
    time.sleep(2) # Allow time for the server to process and reply.
