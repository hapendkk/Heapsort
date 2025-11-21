import sys
import socket
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QMenuBar, QMenu, QInputDialog
)
from PyQt6.QtCore import pyqtSignal, QObject, Qt

HOST = '127.0.0.1'
PORT = 12345

class Worker(QObject):
    message_received = pyqtSignal(str)
    disconnected = pyqtSignal()

    def __init__(self, client_socket):
        super().__init__()
        self.client_socket = client_socket
        self._running = True

    def run(self):
        while self._running:
            try:
                data = self.client_socket.recv(1024).decode('utf-8')
                if data:
                    self.message_received.emit(f"{data}")
                else:
                    self.message_received.emit("[ОТКЛЮЧЕНИЕ] Соединение разорвано сервером.")
                    self.disconnected.emit()
                    break
            except ConnectionResetError:
                self.message_received.emit("[ОТКЛЮЧЕНИЕ] Соединение разорвано сервером.")
                self.disconnected.emit()
                break
            except OSError:
                break
            except Exception as e:
                self.message_received.emit(f"[ОШИБКА РАБОЧЕГО]: {e}")
                self.disconnected.emit()
                break

    def stop(self):
        self._running = False

class ChatClient(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Пикми чатик")
        self.setGeometry(100, 100, 700, 500)

        self.client_socket = None
        self.is_connected = False
        self.worker_thread = None

        self.setup_ui()
        self.update_gui_state(False)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setStyleSheet(
            "background-color: #f2b5e4; color: #ab274f;"
        )
        main_layout.addWidget(self.chat_area)
        input_container = QHBoxLayout()

        self.msg_entry = QLineEdit()
        self.msg_entry.setPlaceholderText("Введите команду или сообщение...")
        self.msg_entry.returnPressed.connect(self.send_message_gui)

        self.msg_entry.setStyleSheet(
            "background-color: #f2b5e4; color: white;"
        )
        input_container.addWidget(self.msg_entry)

        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.send_message_gui)

        self.send_button.setStyleSheet(
            "background-color: #ab274f; color: white; padding: 5px;"
        )
        input_container.addWidget(self.send_button)

        main_layout.addLayout(input_container)

        self._create_menu()

    def _create_menu(self):
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        self.connect_menu = QMenu("&Подключение", self)
        menu_bar.addMenu(self.connect_menu)

        self.connect_action = self.connect_menu.addAction("Подключиться")
        self.connect_action.triggered.connect(self.connect_to_server)

        self.disconnect_action = self.connect_menu.addAction("Отключиться")
        self.disconnect_action.triggered.connect(self.disconnect)

        self.room_menu = QMenu("&Комната", self)
        menu_bar.addMenu(self.room_menu)

        self.room_menu.addAction("/join...").triggered.connect(self.join_room_gui)
        self.room_menu.addAction("/leave").triggered.connect(self.leave_room_gui)
        self.room_menu.addAction("/list").triggered.connect(self.list_rooms_gui)

    def log(self, message):
        self.chat_area.append(message)

    def update_gui_state(self, connected):
        self.is_connected = connected

        self.msg_entry.setEnabled(connected)
        self.send_button.setEnabled(connected)

        self.connect_action.setEnabled(not connected)
        self.disconnect_action.setEnabled(connected)

        self.room_menu.setEnabled(connected)

    def closeEvent(self, event):
        self.disconnect()
        super().closeEvent(event)

    def connect_to_server(self):
        if self.is_connected:
            self.log("Уже подключено.")
            return

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((HOST, PORT))
            self.log("[ПОДКЛЮЧЕНИЕ] Подключено к серверу.")
            self.update_gui_state(True)

            self.worker = Worker(self.client_socket)

            self.worker.message_received.connect(self.log)
            self.worker.disconnected.connect(self.disconnect)

            self.worker_thread = threading.Thread(target=self.worker.run)
            self.worker_thread.daemon = True
            self.worker_thread.start()

        except ConnectionRefusedError:
            self.log("[ОШИБКА] Не удалось подключиться. Убедитесь, что сервер запущен.")
        except Exception as e:
            self.log(f"[ОШИБКА] Проблема подключения: {e}")

    def disconnect(self):
        if self.is_connected:
            if self.worker and self.worker_thread:
                self.worker.stop()

            try:
                self.client_socket.sendall("exit".encode('utf-8'))
            except Exception:
                pass

            try:
                self.client_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            self.client_socket.close()
            self.update_gui_state(False)
            self.log("[ВЫХОД] Вы отключились от сервера.")

    def send_command(self, command):
        if self.is_connected:
            try:
                self.client_socket.sendall(command.encode('utf-8'))
            except Exception as e:
                self.log(f"[ОШИБКА ОТПРАВКИ]: {e}")
                self.disconnect()

    def send_message_gui(self):
        message = self.msg_entry.text().strip()
        self.msg_entry.clear()

        if not message or not self.is_connected:
            return

        if message.startswith('/'):
            self.send_command(message)
            self.log(f"[КОМАНДА]: {message}")
        elif message.lower() == 'exit':
            self.disconnect()
        else:
            self.send_command(message)
            self.log(f"Вы: {message}")

    def join_room_gui(self):
        room_name, ok = QInputDialog.getText(self, "Присоединиться", "Введите имя комнаты:")
        if ok and room_name:
            self.send_command(f"/join {room_name.strip()}")

    def leave_room_gui(self):
        self.send_command("/leave")

    def list_rooms_gui(self):
        self.send_command("/list")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    client_window = ChatClient()
    client_window.show()
    sys.exit(app.exec())