import socket
import threading
import json
import random
import datetime
import os

HOST = 'localhost'
PORT = 5555
GRID_SIZE = 10


class GameServer:
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rooms = {}
        self.players = {}
        self.running = False
        self.rooms_lock = threading.Lock()
        self.players_lock = threading.Lock()
        self.player_id_counter = 0
        self.registered_usernames = set()

        os.makedirs("game_results", exist_ok=True)

    def generate_random_positions(self):
        while True:
            start_x = random.randint(0, GRID_SIZE - 1)
            start_y = random.randint(0, GRID_SIZE - 1)
            target_x = random.randint(0, GRID_SIZE - 1)
            target_y = random.randint(0, GRID_SIZE - 1)

            if [start_x, start_y] != [target_x, target_y]:
                distance = abs(start_x - target_x) + abs(start_y - target_y)
                if distance >= 3:
                    return [start_x, start_y], [target_x, target_y]

    def start(self):
        try:
            self.server_socket.bind((HOST, PORT))
            self.server_socket.listen()
            self.running = True
            print(f"Сервер запущен на {HOST}:{PORT}")

            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    self.player_id_counter += 1
                    player_id = f"Player{self.player_id_counter}"

                    self.send_message(client_socket, {
                        'type': 'registration_required',
                        'message': 'Введите ваше имя'
                    })

                    print(f"Новое подключение: {address}, временный ID: {player_id}")
                    client_handler = threading.Thread(
                        target=self.handle_client,
                        args=(player_id, client_socket, address)
                    )
                    client_handler.daemon = True
                    client_handler.start()
                except Exception as e:
                    print(f"Ошибка соединения: {e}")

        except Exception as e:
            print(f"Ошибка сервера: {e}")
        finally:
            self.stop()

    def handle_client(self, temp_player_id, client_socket, address):
        buffer = ""
        username = None
        registered = False

        try:
            while self.running:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    print(f"---Игрок {temp_player_id} отключился")
                    break

                buffer += data

                while '\n' in buffer:
                    message_part, buffer = buffer.split('\n', 1)
                    if message_part.strip():
                        try:
                            message = json.loads(message_part)
                            print(f"---Получено сообщение от {temp_player_id}: {message.get('type')}")

                            if not registered and message.get('type') == 'register':
                                username = self.process_registration(temp_player_id, client_socket, message)
                                if username:
                                    registered = True
                                    with self.players_lock:
                                        self.players[username] = client_socket
                                continue

                            if registered:
                                self.process_message(username, client_socket, message)
                            else:
                                self.send_message(client_socket, {
                                    'type': 'registration_required',
                                    'message': 'Сначала зарегистрируйтесь с помощью {"type": "register", "username": "ваше_имя"}'
                                })

                        except json.JSONDecodeError as e:
                            print(f"! Ошибка JSON в буфере от {temp_player_id}: {e}, часть: {message_part[:50]}...")
                            continue

        except Exception as e:
            print(f"! Ошибка обработки клиента {temp_player_id}: {e}")
        finally:
            self.disconnect_player(username if username else temp_player_id, client_socket)

    def process_registration(self, temp_player_id, client_socket, message):
        username = message.get('username', '').strip()

        if not username:
            self.send_message(client_socket, {
                'type': 'registration_failed',
                'message': 'Имя не может быть пустым'
            })
            return None

        if len(username) > 20:
            self.send_message(client_socket, {
                'type': 'registration_failed',
                'message': 'Имя слишком длинное (макс. 20 символов)'
            })
            return None

        with self.players_lock:
            if username in self.registered_usernames:
                self.send_message(client_socket, {
                    'type': 'registration_failed',
                    'message': 'Имя уже занято'
                })
                return None

            self.registered_usernames.add(username)

        self.send_message(client_socket, {
            'type': 'registration_success',
            'username': username,
            'message': f'Добро пожаловать, {username}!'
        })

        print(f"---Игрок {temp_player_id} зарегистрирован как {username}")
        return username

    def process_message(self, username, client_socket, message):
        msg_type = message.get('type')

        if msg_type == 'join_game':
            players_count = 4
            self.create_or_join_room(username, client_socket, players_count)
        elif msg_type == 'move':
            self.process_player_move(username, message)
        elif msg_type == 'new_round':
            self.handle_new_round_request(username, client_socket, message)
        elif msg_type == 'save_result':
            self.save_game_result(username, message)
        elif msg_type == 'exit_game':
            self.handle_player_exit(username)

    def handle_new_round_request(self, username, client_socket, message):
        print(f"---Игрок {username} запросил новый раунд")
        self.remove_player_from_room(username)
        self.create_or_join_room(username, client_socket, 4)

    def handle_player_exit(self, username):
        print(f"---Игрок {username} вышел из игры")
        self.remove_player_from_room(username)

    def remove_player_from_room(self, username):
        room_to_check = None
        room_id_to_check = None

        with self.rooms_lock:
            for room_id, room in list(self.rooms.items()):
                if username in room['players']:
                    room_to_check = room
                    room_id_to_check = room_id

                    remaining_players = list(room['players'].keys())
                    if len(remaining_players) > 1:
                        exit_message = {
                            'type': 'player_left',
                            'username': username,
                            'remaining_players': [p for p in remaining_players if p != username],
                            'message': f'Игрок {username} покинул игру'
                        }

                        for player_name, player_info in room['players'].items():
                            if player_name != username:
                                try:
                                    self.send_message(player_info['socket'], exit_message)
                                    print(f"---Уведомление отправлено игроку {player_name}")
                                except Exception as e:
                                    print(f"! Ошибка отправки уведомления игроку {player_name}: {e}")

                    del room['players'][username]
                    print(f"---Игрок {username} удален из комнаты {room_id}")

                    break

        if room_to_check and room_id_to_check:
            self.check_game_conditions(room_id_to_check, room_to_check)

    def check_game_conditions(self, room_id, room):
        with room['room_lock']:
            current_players = len(room['players'])
            print(f"---Проверка условий для комнаты {room_id}: {current_players} игроков")

            if room.get('game_started', False) and current_players < 4:
                print(f"---В комнате {room_id} осталось {current_players} игроков, игра завершена")

                self.broadcast(room, {
                    'type': 'game_ended',
                    'message': f'Игра завершена: недостаточно игроков (осталось: {current_players})',
                    'reason': 'not_enough_players'
                })

                with self.rooms_lock:
                    if room_id in self.rooms:
                        del self.rooms[room_id]
                        print(f"---Комната {room_id} удалена")

            elif not room.get('game_started', False) and current_players < 4:
                print(f"---В комнате {room_id} недостаточно игроков для начала: {current_players}/4")

                self.broadcast(room, {
                    'type': 'waiting_for_players',
                    'current_players': current_players,
                    'total_players': 4,
                    'message': f'Ожидание игроков... ({current_players}/4)'
                })

    def save_game_result(self, username, message):
        try:
            game_data = message.get('game_data', {})
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            filename = f"game_results/{username}_results.txt"
            with open(filename, "a", encoding="utf-8") as f:
                f.write(f"=== Результат игры ===\n")
                f.write(f"Игрок: {username}\n")
                f.write(f"Время: {timestamp}\n")
                f.write(f"Позиция игрока: {game_data.get('player_pos', 'N/A')}\n")
                f.write(f"Позиция цели: {game_data.get('target_pos', 'N/A')}\n")
                f.write(f"Статус: {game_data.get('status', 'N/A')}\n")
                f.write(f"Количество ходов: {game_data.get('moves_count', 'N/A')}\n")
                f.write("-" * 30 + "\n\n")

            print(f"---Результат игры сохранен для {username}")

            with self.players_lock:
                if username in self.players:
                    self.send_message(self.players[username], {
                        'type': 'save_success',
                        'message': f'Результат сохранен в файл {filename}'
                    })

        except Exception as e:
            print(f"! Ошибка сохранения результата для {username}: {e}")

    def create_or_join_room(self, username, client_socket, players_count):
        with self.rooms_lock:
            room_found = None
            room_id_found = None

            for room_id, room in self.rooms.items():
                if (len(room['players']) < room['players_count'] and
                        room['players_count'] == players_count and
                        not room['game_started']):
                    room_found = room
                    room_id_found = room_id
                    break

            if room_found:
                direction = self.assign_direction(room_found['players'], players_count)
                room_found['players'][username] = {
                    'socket': client_socket,
                    'direction': direction,
                    'username': username
                }
                print(f"---Игрок {username} присоединился к комнате {room_id_found}, направление: {direction}")

                self.send_message(client_socket, {
                    'type': 'room_joined',
                    'direction': direction,
                    'current_players': len(room_found['players']),
                    'total_players': players_count
                })

                if len(room_found['players']) == players_count:
                    self.start_game(room_id_found, room_found)
                else:
                    self.broadcast(room_found, {
                        'type': 'waiting_for_players',
                        'current_players': len(room_found['players']),
                        'total_players': players_count,
                        'message': f'Ожидание игроков... ({len(room_found["players"])}/{players_count})'
                    })

            else:
                player_pos, target_pos = self.generate_random_positions()
                room_id = f"room_{len(self.rooms) + 1}"
                direction = self.assign_direction({}, players_count)
                self.rooms[room_id] = {
                    'players': {
                        username: {
                            'socket': client_socket,
                            'direction': direction,
                            'username': username
                        }
                    },
                    'players_count': players_count,
                    'game_started': False,
                    'player_pos': player_pos,
                    'target_pos': target_pos,
                    'grid_size': 10,
                    'room_lock': threading.Lock(),
                    'moves_count': 0
                }

                print(f"Создана комната {room_id} для {players_count} игроков")
                print(f"Случайные позиции: старт {player_pos}, цель {target_pos}")
                self.send_message(client_socket, {
                    'type': 'room_joined',
                    'direction': direction,
                    'current_players': 1,
                    'total_players': players_count
                })

    def process_player_move(self, username, message):
        with self.rooms_lock:
            room = None
            room_id = None
            for rid, r in self.rooms.items():
                if username in r['players']:
                    room = r
                    room_id = rid
                    break

            if not room:
                print(f"-! Комната не найдена для игрока {username}")
                return
            if not room['game_started']:
                print(f"-! Игра еще не началась в комнате {room_id}")
                return

        direction = message.get('direction')
        print(f"---Игрок {username} начинает движение: {direction}")

        player_info = room['players'][username]
        player_directions = player_info['direction']

        print(f"- -Направления игрока {username}: {player_directions}")

        can_move = (direction == player_directions)
        print(f"- -Проверка направления: {direction} == {player_directions} = {can_move}")

        if not can_move:
            print(f"-! Игрок {username} не может двигаться {direction}")
            return

        with room['room_lock']:
            old_pos = room['player_pos'].copy()
            new_pos = old_pos.copy()

            grid_size = 10

            if direction == 'up':
                if new_pos[1] > 0:
                    new_pos[1] -= 1
                    print(f"---Движение ВВЕРХ")
                else:
                    print(f"-! Не могу двигаться ВВЕРХ - достигнут верхний край")
            elif direction == 'down':
                if new_pos[1] < grid_size - 1:
                    new_pos[1] += 1
                    print(f"---Движение ВНИЗ")
                else:
                    print(f"-! Не могу двигаться ВНИЗ - достигнут нижний край")
            elif direction == 'left':
                if new_pos[0] > 0:
                    new_pos[0] -= 1
                    print(f"---Движение ВЛЕВО")
                else:
                    print(f"-! Не могу двигаться ВЛЕВО - достигнут левый край")
            elif direction == 'right':
                if new_pos[0] < grid_size - 1:
                    new_pos[0] += 1
                    print(f"---Движение ВПРАВО")
                else:
                    print(f"-! Не могу двигаться ВПРАВО - достигнут правый край")

            if new_pos != old_pos:
                room['player_pos'] = new_pos
                room['moves_count'] += 1
                print(f"---Позиция изменена: {old_pos} -> {new_pos}")
            else:
                print(f"- -Позиция не изменилась")

            game_won = (room['player_pos'] == room['target_pos'])

            print(f"---Текущая позиция: {room['player_pos']}, цель: {room['target_pos']}")

            game_state_message = {
                'type': 'game_state',
                'player_pos': room['player_pos'],
                'target_pos': room['target_pos'],
                'moved_by': username,
                'direction': direction,
                'position_changed': (new_pos != old_pos),
                'game_won': game_won,
                'moves_count': room.get('moves_count', 0)
            }

            print(f"- -Отправка обновления состояния: {game_state_message}")

            room_copy = {
                'players': room['players'].copy(),
                'room_lock': room['room_lock']
            }

        self.broadcast(room_copy, game_state_message)

        if game_won:
            print(f"ПОБЕДА в комнате {room_id}! Команда достигла цели!")
            self.save_victory_result(room_id, room)

    def save_victory_result(self, room_id, room):
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            player_names = list(room['players'].keys())

            for username in player_names:
                game_data = {
                    'player_pos': room['player_pos'],
                    'target_pos': room['target_pos'],
                    'status': 'ПОБЕДА',
                    'moves_count': room.get('moves_count', 0),
                    'room_id': room_id,
                    'players': player_names
                }

                filename = f"game_results/{username}_results.txt"
                with open(filename, "a", encoding="utf-8") as f:
                    f.write(f"=== ПОБЕДА! ===\n")
                    f.write(f"Игрок: {username}\n")
                    f.write(f"Время: {timestamp}\n")
                    f.write(f"Комната: {room_id}\n")
                    f.write(f"Участники: {', '.join(player_names)}\n")
                    f.write(f"Финальная позиция: {room['player_pos']}\n")
                    f.write(f"Цель: {room['target_pos']}\n")
                    f.write(f"Всего ходов: {room.get('moves_count', 0)}\n")
                    f.write("=" * 40 + "\n\n")

                print(f"---Результат победы сохранен для {username}")

        except Exception as e:
            print(f"! Ошибка сохранения результата победы: {e}")

    def disconnect_player(self, username, client_socket):
        try:
            client_socket.close()
        except:
            pass

        self.remove_player_from_room(username)

        with self.players_lock:
            if username in self.players:
                del self.players[username]
            if username in self.registered_usernames:
                self.registered_usernames.remove(username)

        print(f"---Игрок {username} отключен")

    def assign_direction(self, players, players_count):
        all_directions = ['up', 'down', 'left', 'right']
        used_directions = [p['direction'] for p in players.values()]
        available = [d for d in all_directions if d not in used_directions]
        if available:
            return available[0]
        return random.choice(all_directions)

    def start_game(self, room_id, room):
        print(f"Начинаем игру в комнате {room_id}")
        room['game_started'] = True

        self.broadcast(room, {'type': 'countdown_start', 'duration': 3})

        timer = threading.Timer(3.0, lambda: self.send_game_start(room_id, room))
        timer.daemon = True
        timer.start()

    def send_game_start(self, room_id, room):
        print(f"Игра началась в комнате {room_id}")
        print(f"Случайные позиции: старт {room['player_pos']}, цель {room['target_pos']}")
        self.broadcast(room, {
            'type': 'game_start',
            'player_pos': room['player_pos'],
            'target_pos': room['target_pos'],
            'grid_size': room.get('grid_size', 10)
        })

    def start_new_round(self, room_id, room):
        print(f"---Начинаем новый раунд в комнате {room_id}")

        player_pos, target_pos = self.generate_random_positions()

        with room['room_lock']:
            room['player_pos'] = player_pos
            room['target_pos'] = target_pos
            room['game_started'] = False
            room['moves_count'] = 0

        print(f"---Новые случайные позиции: старт {player_pos}, цель {target_pos}")
        self.broadcast(room, {'type': 'countdown_start', 'duration': 3})

        timer = threading.Timer(3.0, lambda: self.send_game_start(room_id, room))
        timer.daemon = True
        timer.start()

    def broadcast(self, room, message):
        disconnected_players = []
        players_copy = room['players'].copy()

        print(f"- -Рассылка сообщения {message.get('type')} для {len(players_copy)} игроков")

        for username, player_info in players_copy.items():
            try:
                self.send_message(player_info['socket'], message)
                print(f"- -Сообщение отправлено игроку {username}")
            except Exception as e:
                print(f"-! Не удалось отправить сообщение игроку {username}: {e}")
                disconnected_players.append(username)

        if disconnected_players:
            with self.rooms_lock:
                for room_id, actual_room in self.rooms.items():
                    if any(uname in actual_room['players'] for uname in disconnected_players):
                        with actual_room['room_lock']:
                            for uname in disconnected_players:
                                if uname in actual_room['players']:
                                    del actual_room['players'][uname]
                                    print(f"---Игрок {uname} удален из комнаты {room_id}")
                        break

    def send_message(self, socket, message):
        try:
            data = json.dumps(message).encode('utf-8') + b'\n'
            socket.sendall(data)
        except Exception as e:
            raise

    def stop(self):
        self.running = False
        try:
            self.server_socket.close()
        except:
            pass
        print("Сервер остановлен")


if __name__ == "__main__":
    server = GameServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("Останавливаем сервер...")
        server.stop()