import socket
import threading

HOST = '127.0.0.1'
PORT = 12345

clients = {}
rooms = {}
client_rooms = {}

def remove_client_from_room(conn):
    room_name = client_rooms.get(conn)
    if room_name and room_name in rooms:
        if conn in rooms[room_name]:
            rooms[room_name].remove(conn)
            if not rooms[room_name]:
                del rooms[room_name]
                print(f"[КОМНАТА] Комната '{room_name}' удалена (пустая).")

        del client_rooms[conn]
        return room_name
    return None


def send_message(conn, message):
    try:
        conn.sendall(message.encode('utf-8'))
    except ConnectionResetError:
        pass


def broadcast_message(sender_conn, room_name, message, include_sender=False):
    if room_name in rooms:
        sender_name = clients.get(sender_conn, "Неизвестный")
        full_message = f"[{room_name}] {sender_name}: {message}"

        for conn in rooms[room_name]:
            if conn != sender_conn or include_sender:
                send_message(conn, full_message)

def handle_client(conn, addr):
    print(f"[НОВОЕ ПОДКЛЮЧЕНИЕ] {addr}")
    player_name = f"Player{addr[1]}"
    clients[conn] = player_name
    client_rooms[conn] = None
    current_room = None

    try:
        send_message(conn, f"Привет! Вы подключены как {player_name}. Используйте /join <Название комнаты>:")

        while True:
            data = conn.recv(1024).decode('utf-8').strip()
            if not data:
                break

            print(f"[{player_name} в {current_room if current_room else 'LOBBY'}]: {data}")

            if data.startswith("/join"):
                parts = data.split(maxsplit=1)
                if len(parts) < 2:
                    send_message(conn, "Ошибка: Используйте /join <имя_комнаты>")
                    continue

                new_room_name = parts[1]
                old_room = remove_client_from_room(conn)
                if old_room:
                    broadcast_message(conn, old_room, f"покинул(а) чат.", include_sender=False)
                    send_message(conn, f"Вы покинули комнату {old_room}")
                if new_room_name not in rooms:
                    rooms[new_room_name] = []

                rooms[new_room_name].append(conn)
                client_rooms[conn] = new_room_name
                current_room = new_room_name

                send_message(conn, f"Вы вошли в комнату {new_room_name}")
                broadcast_message(conn, current_room, f"присоединился к чату.", include_sender=False)


            elif data.startswith("/leave"):
                if not current_room:
                    send_message(conn, "Вы не находитесь ни в одной комнате.")
                    continue

                broadcast_message(conn, current_room, f"покинул(а) чат.", include_sender=False)

                remove_client_from_room(conn)
                send_message(conn, "Вы покинули комнату")
                current_room = None

            elif data.startswith("/list"):
                msg = "Доступные комнаты:\n"
                if not rooms:
                    msg += "Нет активных комнат."
                else:
                    for room, participants in rooms.items():
                        names = [clients[c] for c in participants if c in clients]
                        msg += f" {room} ({len(names)}): {', '.join(names)}\n"
                send_message(conn, msg)

            elif data.lower() == "exit":
                break

            else:
                if current_room:
                    broadcast_message(conn, current_room, data)
                else:
                    send_message(conn,
                                 "Вы не находитесь в комнате. Используйте /join <имя_комнаты>, чтобы начать общение.")

    except ConnectionResetError:
        print(f"[ОТКЛЮЧЕНИЕ] Клиент {addr} отключился (ConnectionResetError)")
    except Exception as e:
        print(f"[ОШИБКА] Непредвиденная ошибка с клиентом {addr}: {e}")

    finally:
        print(f"[ОЧИСТКА] Завершение работы с клиентом {addr}")
        room_was = remove_client_from_room(conn)
        if room_was:
            broadcast_message(conn, room_was, f"отключился от сервера.", include_sender=False)

        if conn in clients:
            del clients[conn]
    conn.close()


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    with server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"[СЕРВЕР ЗАПУЩЕН] {HOST}:{PORT}")
        while True:
            conn, addr = server_socket.accept()
            threading.Thread(target=handle_client, args=(conn, addr)).start()


if __name__ == "__main__":
    start_server()