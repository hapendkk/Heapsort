import sys
import socket
import json
import threading
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QFrame,
                             QMessageBox, QStackedWidget, QLineEdit, QDialog, QDialogButtonBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QFont
from PyQt6.QtCore import QRect

HOST = 'localhost'
PORT = 5555


class RegistrationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Регистрация")
        self.setFixedSize(300, 200)
        self.setModal(True)

        layout = QVBoxLayout()

        title = QLabel("Введите ваше имя")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #2E7D32; font-size: 18px; font-weight: bold;")

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Введите уникальное имя")
        self.username_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                font-size: 14px;
                border: 2px solid #4CAF50;
                border-radius: 10px;
            }
        """)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red; font-size: 12px;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(title)
        layout.addWidget(self.username_input)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_username(self):
        return self.username_input.text().strip()

    def show_error(self, message):
        self.error_label.setText(message)


class CommunicationThread(QObject):
    message_received = pyqtSignal(dict)
    connection_error = pyqtSignal(str)
    registration_required = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.socket = None
        self.running = False
        self.socket_lock = threading.Lock()
        self.connected = False
        self.registered = False
        self.username = None

    def connect_to_server(self, host, port):
        try:
            with self.socket_lock:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(5.0)
                self.socket.connect((host, port))
                self.socket.settimeout(None)
                self.running = True
                self.connected = True

            thread = threading.Thread(target=self.receive_messages)
            thread.daemon = True
            thread.start()
            return True

        except Exception as e:
            self.connection_error.emit(f"Ошибка подключения: {e}")
            return False

    def register(self, username):
        if not self.connected:
            return False

        self.username = username
        success = self.send_message({
            'type': 'register',
            'username': username
        })
        return success

    def send_message(self, message):
        if not self.connected or not self.running:
            return False

        with self.socket_lock:
            try:
                data = json.dumps(message).encode('utf-8') + b'\n'
                bytes_sent = self.socket.sendall(data)
                return True
            except Exception as e:
                print(f"! Ошибка отправки сообщения {message}: {e}")
                self.connected = False
                self.connection_error.emit(f"Ошибка отправки: {e}")
                return False

    def receive_messages(self):
        buffer = ""
        while self.running and self.connected:
            try:
                data = self.socket.recv(1024).decode('utf-8')
                if not data:
                    break

                buffer += data

                while '\n' in buffer:
                    message_part, buffer = buffer.split('\n', 1)
                    if message_part.strip():
                        try:
                            message = json.loads(message_part)

                            if message.get('type') == 'registration_required' and not self.registered:
                                self.registration_required.emit()
                            else:
                                self.message_received.emit(message)

                        except json.JSONDecodeError as e:
                            print(f"! Ошибка JSON в буфере: {e}, часть: {message_part[:50]}...")
                            continue

            except socket.timeout:
                continue
            except Exception as e:
                print(f"! Ошибка получения: {e}")
                break

        self.connected = False
        if self.running:
            self.connection_error.emit("! Соединение с сервером разорвано")

        self.disconnect()

    def disconnect(self):
        self.running = False
        self.connected = False
        self.registered = False
        self.username = None
        with self.socket_lock:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None


class RoundedButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(50)
        self.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 25px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)


class DirectionButton(QPushButton):
    def __init__(self, direction, parent=None):
        self.direction = direction
        direction_text = {
            'up': '↑ ВВЕРХ',
            'down': '↓ ВНИЗ',
            'left': '← ВЛЕВО',
            'right': '→ ВПРАВО'
        }
        text = direction_text.get(direction, direction)
        super().__init__(text, parent)
        self.setFixedHeight(60)
        self.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 15px;
                font-size: 14px;
                font-weight: bold;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)


class WelcomeScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("The Harmony of Chaos")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #2E7D32; font-size: 48px; font-weight: 900;")

        description = QLabel("Кооперативная игра для 4 игроков")
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setStyleSheet("color: #388E3C; font-size: 20px;")

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addStretch()

        start_btn = RoundedButton("Начать игру")
        start_btn.clicked.connect(lambda: self.parent.start_game(4))
        layout.addWidget(start_btn)

        info_label = QLabel("Для игры требуется 4 игрока")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: #388E3C; font-size: 12px; margin-top: 0;")
        layout.addWidget(info_label)

        layout.addStretch()
        self.setLayout(layout)
        self.setStyleSheet("background-color: #E8F5E8;")


class CountdownScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.countdown = 3
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)

        self.label = QLabel("ОЖИДАНИЕ ID")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #2E7D32; font-size: 64px; font-weight: 800;")

        self.info_label = QLabel("Подключение к серверу...")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #388E3C; font-size: 16px;")

        layout.addStretch()
        layout.addWidget(self.label)
        layout.addWidget(self.info_label)
        layout.addStretch()

        self.setLayout(layout)
        self.setStyleSheet("background-color: #E8F5E8;")

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_countdown)

    def start_countdown(self, duration):
        self.countdown = duration
        self.label.setText(str(self.countdown))
        self.info_label.setText("Игра начинается...")
        self.timer.start(1000)

    def update_countdown(self):
        self.countdown -= 1
        if self.countdown <= 0:
            self.timer.stop()
            self.label.setText("Старт!")
        else:
            self.label.setText(str(self.countdown))


class GameWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid_size = 10
        self.cell_size = 40
        self.player_pos = [4, 4]
        self.target_pos = [9, 9]
        self.setFixedSize(self.grid_size * self.cell_size + 20,
                          self.grid_size * self.cell_size + 20)

    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            painter.fillRect(self.rect(), QColor(240, 255, 240))

            painter.setPen(QColor(180, 200, 180))
            for i in range(self.grid_size + 1):
                painter.drawLine(10, 10 + i * self.cell_size,
                                 10 + self.grid_size * self.cell_size, 10 + i * self.cell_size)
                painter.drawLine(10 + i * self.cell_size, 10,
                                 10 + i * self.cell_size, 10 + self.grid_size * self.cell_size)

            painter.setPen(QColor(120, 120, 120))
            painter.setFont(QFont("Arial", 7))
            for i in range(self.grid_size):
                x = 10 + i * self.cell_size + 15
                y = 25
                painter.drawText(x, y, str(i))

            for j in range(self.grid_size):
                x = 5
                y = 10 + j * self.cell_size + 25
                painter.drawText(x, y, str(j))

            target_rect = QRect(
                10 + self.target_pos[0] * self.cell_size + 5,
                10 + self.target_pos[1] * self.cell_size + 5,
                self.cell_size - 10,
                self.cell_size - 10
            )

            painter.setBrush(QColor(255, 220, 0))
            painter.setPen(QColor(255, 140, 0))
            painter.drawEllipse(target_rect)

            painter.setPen(QColor(200, 100, 0))
            painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
            target_text_rect = QRect(
                10 + self.target_pos[0] * self.cell_size,
                10 + self.target_pos[1] * self.cell_size - 15,
                self.cell_size,
                15
            )
            painter.drawText(target_text_rect, Qt.AlignmentFlag.AlignCenter, "ЦЕЛЬ")

            player_rect = QRect(
                10 + self.player_pos[0] * self.cell_size + 3,
                10 + self.player_pos[1] * self.cell_size + 3,
                self.cell_size - 6,
                self.cell_size - 6
            )

            painter.setBrush(QColor(100, 200, 100))
            painter.setPen(QColor(0, 150, 0))
            painter.drawRoundedRect(player_rect, 10, 10)

            inner_rect = QRect(
                10 + self.player_pos[0] * self.cell_size + 6,
                10 + self.player_pos[1] * self.cell_size + 6,
                self.cell_size - 12,
                self.cell_size - 12
            )
            painter.setBrush(QColor(150, 255, 150))
            painter.drawRoundedRect(inner_rect, 8, 8)

            painter.setPen(QColor(0, 100, 0))
            painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
            player_text_rect = QRect(
                10 + self.player_pos[0] * self.cell_size,
                10 + self.player_pos[1] * self.cell_size - 15,
                self.cell_size,
                15
            )
            painter.drawText(player_text_rect, Qt.AlignmentFlag.AlignCenter, "ИГРОК")

            info_text = f"Позиция: ({self.player_pos[0]}, {self.player_pos[1]})"
            painter.setPen(QColor(0, 100, 0))
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            painter.drawText(10, self.height() - 5, info_text)

        except Exception as e:
            print(f"! Ошибка отрисовки: {e}")
            try:
                painter = QPainter(self)
                painter.fillRect(self.rect(), QColor(240, 255, 240))
                painter.setPen(QColor(255, 0, 0))
                painter.drawText(20, 30, f"! Ошибка отрисовки: {e}")
            except:
                pass

    def update_game_state(self, player_pos, target_pos):
        self.player_pos = player_pos
        self.target_pos = target_pos
        self.update()


class GameScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.directions = []
        self.moves_count = 0
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        self.game_widget = GameWidget()

        right_panel = QFrame()
        right_panel.setFixedWidth(280)
        right_layout = QVBoxLayout()
        right_layout.setSpacing(15)

        self.player_info_label = QLabel("Игрок: -")
        self.player_info_label.setStyleSheet("""
            QLabel {
                color: #2E7D32;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                background-color: #C8E6C9;
                border-radius: 10px;
            }
        """)
        self.player_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.player_info_label.setFixedHeight(50)

        self.direction_label = QLabel("Направления: -")
        self.direction_label.setStyleSheet("""
            QLabel {
                color: #2E7D32;
                font-size: 14px;
                font-weight: bold;
                padding: 15px;
                background-color: #C8E6C9;
                border-radius: 15px;
                border: 2px solid #4CAF50;
            }
        """)
        self.direction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.direction_label.setFixedHeight(80)

        self.move_btn = RoundedButton("Нажмите SPACE\nдля движения")
        self.move_btn.setFixedHeight(60)
        self.move_btn.clicked.connect(self.send_first_move)

        buttons_container = QWidget()
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        buttons_layout.setContentsMargins(0, 0, 0, 0)

        self.save_btn = QPushButton("Сохранить")
        self.save_btn.setFixedHeight(40)
        self.save_btn.clicked.connect(self.save_game_result)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 15px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """)

        self.new_round_btn = QPushButton("Новый раунд")
        self.new_round_btn.setFixedHeight(40)
        self.new_round_btn.clicked.connect(self.parent.start_new_round)
        self.new_round_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 15px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """)

        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.new_round_btn)
        buttons_container.setLayout(buttons_layout)

        instruction = QLabel(
            "Управление:\n"
            "• SPACE - сделать ход\n"
            "• Работайте в команде!\n"
            "• Сохраняйте результаты!"
        )
        instruction.setStyleSheet("""
            QLabel {
                color: #388E3C; 
                font-size: 12px; 
                padding: 10px;
                background-color: #F1F8E9;
                border-radius: 10px;
            }
        """)
        instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruction.setFixedHeight(100)

        right_layout.addWidget(self.player_info_label)
        right_layout.addWidget(self.direction_label)
        right_layout.addWidget(self.move_btn)
        right_layout.addWidget(buttons_container)
        right_layout.addWidget(instruction)
        right_layout.addStretch()

        right_panel.setLayout(right_layout)
        right_panel.setStyleSheet("""
            QFrame {
                background-color: #F1F8E9;
                border-radius: 15px;
                border: 2px solid #C8E6C9;
            }
        """)

        layout.addWidget(self.game_widget)
        layout.addWidget(right_panel)

        self.setLayout(layout)
        self.setStyleSheet("background-color: #E8F5E8;")

    def set_player_info(self, username):
        self.player_info_label.setText(f"Игрок: {username}")

    def set_direction(self, direction_str):
        self.directions = [direction_str]
        self.update_direction_display()
        print(f"Установлены направления: {self.directions}")

    def update_direction_display(self):
        directions_map = {
            'up': '↑ ВВЕРХ',
            'down': '↓ ВНИЗ',
            'left': '← ВЛЕВО',
            'right': '→ ВПРАВО'
        }

        if len(self.directions) == 1:
            text = directions_map.get(self.directions[0], self.directions[0])
            self.direction_label.setText(f"Ваше направление:\n{text}")
        else:
            texts = [directions_map.get(d, d) for d in self.directions]
            self.direction_label.setText(f"Ваши направления:\n{' и '.join(texts)}")

    def update_game(self, player_pos, target_pos, moves_count=0):
        print(f"---ОБНОВЛЕНИЕ ОТОБРАЖЕНИЯ: игрок {player_pos}, цель {target_pos}")
        self.game_widget.player_pos = player_pos
        self.game_widget.target_pos = target_pos
        self.moves_count = moves_count
        self.game_widget.update()
        print("---Отрисовка завершена")

    def send_first_move(self):
        if self.directions and self.parent.comm.connected:
            direction = self.directions[0]
            print(f"Отправка движения: {direction}")
            self.parent.send_move(direction)

    def start_new_round(self):
        self.parent.start_new_round()

    def save_game_result(self):
        if self.parent.comm.connected and self.parent.comm.registered:
            game_data = {
                'player_pos': self.game_widget.player_pos,
                'target_pos': self.game_widget.target_pos,
                'status': 'В процессе',
                'moves_count': self.moves_count
            }
            print("---Запрос сохранения результата")
            self.parent.save_game_result(game_data)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.send_first_move()


class VictoryScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel(" УРА, ПОБЕДА! ")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: #F57C00;
                font-size: 32px;
                font-weight: bold;
            }
        """)

        message = QLabel("Вы успешно довели объект до цели!\nОтличная командная работа!")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setStyleSheet("color: #388E3C; font-size: 16px;")

        buttons_container = QWidget()
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        buttons_layout.setContentsMargins(0, 0, 0, 0)

        save_btn = QPushButton("Сохранить")
        save_btn.setFixedHeight(40)
        save_btn.clicked.connect(self.save_victory_result)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 15px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """)

        new_round_btn = QPushButton("Новый раунд")
        new_round_btn.setFixedHeight(40)
        new_round_btn.clicked.connect(self.parent.start_new_round)
        new_round_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 15px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """)

        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(new_round_btn)
        buttons_container.setLayout(buttons_layout)

        back_btn = RoundedButton("В главное меню")
        back_btn.clicked.connect(self.parent.return_to_menu)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(message)
        layout.addStretch()
        layout.addWidget(buttons_container)
        layout.addWidget(back_btn)
        layout.addStretch()

        self.setLayout(layout)
        self.setStyleSheet("background-color: #E8F5E8;")

    def save_victory_result(self):
        if self.parent.comm.connected and self.parent.comm.registered:
            game_data = {
                'player_pos': self.parent.game_screen.game_widget.player_pos,
                'target_pos': self.parent.game_screen.game_widget.target_pos,
                'status': 'ПОБЕДА',
                'moves_count': self.parent.game_screen.moves_count
            }
            print("---Сохранение результата победы")
            self.parent.save_game_result(game_data)


class SyncPulseClient(QMainWindow):
    def __init__(self):
        super().__init__()
        try:
            self.comm = CommunicationThread()
            self.comm.message_received.connect(self.handle_message)
            self.comm.connection_error.connect(self.handle_connection_error)
            self.comm.registration_required.connect(self.show_registration_dialog)

            self.player_id = None
            self.username = None

            self.setup_ui()

        except Exception as e:
            print(f"! Ошибка инициализации: {e}")
            QMessageBox.critical(None, "Ошибка", f"Не удалось запустить приложение: {e}")

    def setup_ui(self):
        self.setWindowTitle("The Harmony of Chaos")
        self.setFixedSize(800, 500)

        self.stacked = QStackedWidget()
        self.setCentralWidget(self.stacked)

        self.welcome_screen = WelcomeScreen(self)
        self.countdown_screen = CountdownScreen(self)
        self.game_screen = GameScreen(self)
        self.victory_screen = VictoryScreen(self)

        self.stacked.addWidget(self.welcome_screen)
        self.stacked.addWidget(self.countdown_screen)
        self.stacked.addWidget(self.game_screen)
        self.stacked.addWidget(self.victory_screen)

        self.stacked.setCurrentWidget(self.welcome_screen)

    def show_registration_dialog(self):
        dialog = RegistrationDialog(self)
        while True:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                username = dialog.get_username()
                if username:
                    if self.comm.register(username):
                        break
                    else:
                        dialog.show_error("Ошибка отправки регистрации")
                else:
                    dialog.show_error("Имя не может быть пустым")
            else:
                self.return_to_menu()
                break

    def start_game(self, players_count=4):
        print(f"---Начинаем игру с {players_count} игроками")

        if self.comm.connect_to_server(HOST, PORT):
            self.stacked.setCurrentWidget(self.countdown_screen)
            self.countdown_screen.label.setText("РЕГИСТРАЦИЯ")
            self.countdown_screen.info_label.setText("Введите ваше имя...")
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось подключиться к серверу.")

    def exit_game(self):
        if self.comm.connected:
            print("---Выход из текущей игры")
        self.return_to_menu()

    def start_new_round(self):
        if self.comm.connected:
            current_widget = self.stacked.currentWidget()
            if current_widget in [self.game_screen, self.victory_screen]:
                reply = QMessageBox.question(
                    self,
                    "Новый раунд",
                    "Вы уверены, что хотите начать новый раунд?\nТекущая игра будет завершена.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            print("---Запуск нового раунда")
            self.comm.send_message({
                'type': 'new_round',
                'players_count': 4
            })

            self.stacked.setCurrentWidget(self.countdown_screen)
            self.countdown_screen.label.setText("НОВЫЙ РАУНД")
            self.countdown_screen.info_label.setText("Ожидание игроков...")

    def handle_message(self, message):
        try:
            msg_type = message.get('type')
            print(f"---Получено сообщение: {msg_type}")

            if msg_type == 'registration_success':
                self.username = message['username']
                self.comm.registered = True
                self.game_screen.set_player_info(self.username)
                QMessageBox.information(self, "Успех", f"Добро пожаловать, {self.username}!")

                print(f"---Автоматически присоединяемся к игре после регистрации")
                self.comm.send_message({
                    'type': 'join_game',
                    'players_count': 4
                })

                self.countdown_screen.label.setText("ОЖИДАНИЕ ИГРОКОВ")
                self.countdown_screen.info_label.setText("Ждем 4 игрока...")

            elif msg_type == 'registration_failed':
                QMessageBox.warning(self, "Ошибка регистрации", message['message'])
                self.show_registration_dialog()

            elif msg_type == 'player_id':
                pass

            elif msg_type == 'room_joined':
                direction = message['direction']
                current = message['current_players']
                total = message['total_players']

                print(f"---Присоединились к комнате. Направление: {direction}, Игроков: {current}/{total}")

                self.game_screen.set_direction(direction)

                self.countdown_screen.info_label.setText(
                    f"Направления: {direction}. Игроков: {current}/{total}"
                )

            elif msg_type == 'countdown_start':
                print("---Переключаемся на экран отсчета")
                self.stacked.setCurrentWidget(self.countdown_screen)
                self.countdown_screen.start_countdown(message['duration'])

            elif msg_type == 'game_start':
                print("---Переключаемся на игровой экран")
                player_pos = message.get('player_pos', [4, 4])
                target_pos = message.get('target_pos', [9, 9])
                print(f"---Игра началась! Старт: {player_pos}, Цель: {target_pos}")

                if self.stacked.currentWidget() is not self.game_screen:
                    self.stacked.setCurrentWidget(self.game_screen)

                self.game_screen.update_game(player_pos, target_pos)

            elif msg_type == 'game_state':
                player_pos = message.get('player_pos', [4, 4])
                target_pos = message.get('target_pos', [9, 9])
                moved_by = message.get('moved_by', 'unknown')
                direction = message.get('direction', 'unknown')
                position_changed = message.get('position_changed', False)
                game_won = message.get('game_won', False)
                moves_count = message.get('moves_count', 0)

                print(
                    f"---Обновление состояния: позиция {player_pos}, изменено: {position_changed}, переместил: {moved_by}")

                self.game_screen.update_game(player_pos, target_pos, moves_count)
                print(f"---Обновлено отображение: игрок {player_pos}, цель {target_pos}")

                if position_changed:
                    notification_msg = f"Игрок {moved_by} двигался {direction}"
                    print(f"---Уведомление: {notification_msg}")
                    self.show_move_notification(notification_msg)

                if game_won:
                    print("===ПОБЕДА! Переключаемся на экран победы")
                    self.stacked.setCurrentWidget(self.victory_screen)

            elif msg_type == 'save_success':
                QMessageBox.information(self, "Сохранение", message['message'])

            elif msg_type == 'player_left':
                username = message.get('username', 'неизвестный')
                remaining_players = message.get('remaining_players', [])
                message_text = message.get('message', '')

                print(f"---Игрок {username} покинул игру. Осталось: {len(remaining_players)}")

                current_widget = self.stacked.currentWidget()
                if current_widget in [self.game_screen, self.countdown_screen]:
                    QMessageBox.information(
                        self,
                        "Игрок вышел",
                        f"{message_text}\n\nОсталось игроков: {len(remaining_players)}"
                    )

            elif msg_type == 'game_ended':
                message_text = message.get('message', 'Игра завершена')
                reason = message.get('reason', 'unknown')

                print(f"---Игра завершена: {message_text}")

                QMessageBox.warning(self, "Игра завершена", message_text)
                self.return_to_menu()

            elif msg_type == 'waiting_for_players':
                current_players = message.get('current_players', 0)
                total_players = message.get('total_players', 4)
                status_message = message.get('message', '')

                print(f"---Ожидание игроков: {current_players}/{total_players}")

                if self.stacked.currentWidget() is self.countdown_screen:
                    self.countdown_screen.label.setText("ОЖИДАНИЕ ИГРОКОВ")
                    self.countdown_screen.info_label.setText(
                        f"{status_message}\n({current_players}/{total_players})"
                    )

        except Exception as e:
            print(f"! Ошибка обработки сообщения: {e}")

    def save_game_result(self, game_data):
        if self.comm.connected and self.comm.registered:
            success = self.comm.send_message({
                'type': 'save_result',
                'game_data': game_data
            })
            if success:
                print("---Запрос на сохранение отправлен")
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось отправить запрос на сохранение")

    def show_move_notification(self, message):
        try:
            msg = QMessageBox(self)
            msg.setWindowTitle("Ход")
            msg.setText(message)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #E8F5E8;
                }
                QMessageBox QLabel {
                    color: #2E7D32;
                    font-size: 12px;
                }
            """)
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)

            QTimer.singleShot(1000, msg.close)
            msg.show()

        except Exception as e:
            print(f"! Ошибка показа уведомления: {e}")

    def handle_connection_error(self, error_msg):
        print(f"! Ошибка соединения: {error_msg}")
        QMessageBox.warning(self, "Ошибка соединения", error_msg)
        self.return_to_menu()

    def send_move(self, direction):
        if not self.comm.connected:
            print("! Нет соединения с сервером!")
            QMessageBox.warning(self, "Ошибка", "Нет соединения с сервером!")
            return

        print(f"---Попытка отправить движение: {direction}")

        success = self.comm.send_message({
            'type': 'move',
            'direction': direction
        })

        if success:
            print(f"---Движение отправлено: {direction}")
        else:
            print(f"! Не удалось отправить движение: {direction}")
            QMessageBox.warning(self, "Ошибка", "Не удалось отправить движение на сервер")

    def return_to_menu(self):
        self.comm.disconnect()
        self.username = None
        self.stacked.setCurrentWidget(self.welcome_screen)

    def closeEvent(self, event):
        self.comm.disconnect()
        event.accept()


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setStyleSheet("""
            QMainWindow {
                background-color: #E8F5E8;
            }
            QMessageBox {
                background-color: #E8F5E8;
            }
        """)

        client = SyncPulseClient()
        client.show()

        sys.exit(app.exec())

    except Exception as e:
        print(f"Критическая ошибка: {e}")
        QMessageBox.critical(None, "Ошибка", f"Приложение завершилось с ошибкой: {e}")