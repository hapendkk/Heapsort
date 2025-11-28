import socket
import threading
import json


class TaskServer:
    def __init__(self, host='localhost', port=5555):
        self.host = host
        self.port = port
        self.clients = [] #клиенты как кортеж
        self.tasks = {}
        self.lock = threading.Lock()
        self.tasks["Главная доска"] = []

    def broadcast_board(self, board_name):
        tasks_for_board = self.tasks.get(board_name, [])
        message = f"TASKS:{board_name}:{json.dumps(tasks_for_board)}"

        with self.lock:
            for client_socket, client_board in self.clients[:]:
                if client_board == board_name:
                    try:
                        client_socket.send((message + '\n').encode('utf-8'))
                    except:
                        self._remove_client(client_socket) #если не получилось - удаляем клиента

    def _remove_client(self, client_socket):
        self.clients = [
            (s, b) for s, b in self.clients if s != client_socket
        ]

    def _add_client_to_board(self, client_socket, board_name):
        self._remove_client(client_socket)
        self.clients.append((client_socket, board_name))
        print(f"Клиент {client_socket.getpeername()} привязан к доске '{board_name}'")

    def handle_client(self, client_socket):
        print(f"Новое подключение: {client_socket.getpeername()}")
        current_board = None

        try:
            while True:
                data = client_socket.recv(1024).decode('utf-8').strip()
                if not data:
                    break
                print(f"Получено: {data}")

                parts = data.split(':', 2)
                command = parts[0]
                board_name = parts[1] if len(parts) > 1 else "Главная доска"
                payload = parts[2] if len(parts) > 2 else None

                with self.lock:
                    if board_name not in self.tasks:
                        self.tasks[board_name] = []
                        print(f"Создана новая доска: {board_name}")

                tasks_for_board = self.tasks[board_name]

                if command in ["ADD", "UPDATE", "GET_TASKS"]:
                    if board_name != current_board:
                        self._add_client_to_board(client_socket, board_name)
                        current_board = board_name

                if command == "ADD":
                    try:
                        if payload: #перед тем как парсить, чекаем что не нон
                            task = json.loads(payload)
                            tasks_for_board.append(task)
                            self.broadcast_board(board_name)
                        else:
                            print(f"ADD Error: Payload is missing for board {board_name}")
                    except json.JSONDecodeError as e:
                        print(f"JSON Decode Error for ADD on {board_name}: {e}")

                elif command == 'UPDATE':
                    try:
                        if payload:
                            update_tasks = json.loads(payload)
                            self.tasks[board_name] = update_tasks
                            self.broadcast_board(board_name)
                        else:
                            print(f"UPDATE Error: Payload is missing for board {board_name}")
                    except json.JSONDecodeError as e:
                        print(f"JSON Decode Error for UPDATE on {board_name}: {e}")

                elif command == 'GET_TASKS':

                    self.send_tasks_to_client(client_socket, board_name)

                elif command == 'GET_BOARDS':
                    self.send_board_list_to_client(client_socket)


        except Exception as e:
            print(f"Ошибка в handle_client: {e}")
        finally:
            with self.lock:
                self._remove_client(client_socket)
            client_socket.close()

    def send_tasks_to_client(self, client_socket, board_name):
        tasks_for_board = self.tasks.get(board_name, [])
        message = f"TASKS:{board_name}:{json.dumps(tasks_for_board)}"
        try:
            client_socket.send((message + '\n').encode('utf-8'))
        except Exception as e:
            print(f"Ошибка отправки задач клиенту: {e}")

    def send_board_list_to_client(self, client_socket):
        board_names = list(self.tasks.keys())
        message = f"BOARDS:{json.dumps(board_names)}"
        try:
            client_socket.send((message + '\n').encode('utf-8'))
        except Exception as e:
            print(f"Ошибка отправки списка досок клиенту: {e}")


#погнал
    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)

        print(f"Сервер задач запущен на {self.host}:{self.port}")

        try:
            while True:
                client_socket, address = server_socket.accept()

                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket,),
                    daemon=True
                )
                client_thread.start()

        except KeyboardInterrupt:
            print("Останавливаем сервер...")
        finally:
            server_socket.close()


if __name__ == "__main__":
    server = TaskServer()
    server.start()