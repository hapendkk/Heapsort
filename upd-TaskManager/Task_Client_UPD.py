import sys
import socket
import threading
import json
from datetime import datetime

from PyQt6.QtCore import Q_ARG, Qt, QMetaObject, QTimer, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QApplication, QPushButton, QHBoxLayout, QListWidget, \
    QRadioButton, QListWidgetItem, QCheckBox, QLabel, QMessageBox, QMainWindow, QInputDialog


class TaskWidget(QWidget):
    def __init__(self, text, priority, completed=False):
        super().__init__()
        self.text = text
        self.priority = priority
        self.completed = completed
        #добавили ссылку на клиента
        self.client = None

        layout = QHBoxLayout(self)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(completed)
        self.checkbox.stateChanged.connect(self.update_style)
        self.label = QLabel(text)
        self.apply_priority_style()
        self.up_button = QPushButton("↑")
        self.down_button = QPushButton("↓")
        self.up_button.clicked.connect(self.increase_priority)
        self.down_button.clicked.connect(self.decrease_priority)

        layout.addWidget(self.checkbox)
        layout.addWidget(self.label)
        layout.addWidget(self.up_button)
        layout.addWidget(self.down_button)
        layout.addStretch()

    def set_client(self, client): #ссылка на клиента
        self.client = client

    # стиль для определенного приоритета (остается без изменений)
    def apply_priority_style(self):
        colors = {
            "high": "red",
            "medium": "orange",
            "low": "green"
        }
        color = colors.get(self.priority)
        self._default_style = f"color: {color}; font-weight: bold"
        if not self.completed:
            self.label.setStyleSheet(self._default_style)
        else:
            self.label.setStyleSheet("color: gray; text-decoration: line-through;")

    # функция для смены стиля, если чекбокс прожали + отправляем клиенту изменения
    @pyqtSlot(int)
    def update_style(self, state):
        self.completed = state == 2
        if self.completed:
            self.label.setStyleSheet("color: gray; text-decoration: line-through;")
        else:
            self.label.setStyleSheet(self._default_style)

        if self.client:
            self.client.send_task_update()

    @pyqtSlot()
    def increase_priority(self):
        order = ["low", "medium", "high"]
        idx = order.index(self.priority)
        if idx < 2:
            self.priority = order[idx + 1]
            self.apply_priority_style()
            if self.client:
                self.client.send_task_update()

    @pyqtSlot()
    def decrease_priority(self):
        order = ["low", "medium", "high"]
        idx = order.index(self.priority)
        if idx > 0:
            self.priority = order[idx - 1]
            self.apply_priority_style()
            if self.client:
                self.client.send_task_update()


class TaskSignals(QObject):
    tasks_updated = pyqtSignal(list, str)
    boards_updated = pyqtSignal(list)


class TaskClient:
    def __init__(self, host='localhost', port=5555, board="Главная доска"):
        self.host = host
        self.port = port
        self.current_board = board
        self.socket = None
        # ссылка на поток для приема сообщений с сервера
        self.receive_thread = None
        # флаг для контроля работы потока
        self.running = False
        # ссылка на главное окно (то есть мы делаем взаимную связь между ними
        self.task_manager = None
        self.signals = TaskSignals()

    # функция для подключения к серверу
    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            # ставим флаг работы - типа "да, теперь мы работаем, говорите..."
            self.running = True
            # создаем поток для постоянного приема сообщений от сервера
            self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            self.receive_thread.start()
            return True
        except Exception as e:
            print(f"Ошибка подключения: {e}")
            return False

    # функция получения сообщений с сервера
    def receive_messages(self):
        # буфер для накопления неполных сообщений
        buffer = ""
        while self.running:
            try:
                data = self.socket.recv(1024).decode('utf-8')
                # если данных нет - сервер отключился, выходим из цикла
                if not data:
                    print("Сервер отключен.")
                    break
                # добавляем полученные данные в буфер
                buffer += data
                # обрабатываем все полные сообщения (разделенные \n)
                while '\n' in buffer:
                    # разделяем буфер на первую строку и оставшуюся часть
                    line, buffer = buffer.split('\n', 1)
                    # обрабатываем полученное сообщение (убираем пробелы)
                    self.process_message(line.strip())
            except Exception as e:
                if self.running:
                    print(f"Ошибка получения данных: {e}")
                break
        self.running = False

    # функция обработки сообщений, которые пришли к нам с сервера
    def process_message(self, message):
        if message.startswith('TASKS:'):
            try:
                parts = message.split(':', 2)
                board_name = parts[1]
                tasks_data = parts[2]
                tasks = json.loads(tasks_data)
                self.signals.tasks_updated.emit(tasks, board_name)
            except (json.JSONDecodeError, IndexError) as e:
                print(f"Ошибка обработки задач: {e} | Message: {message}")

        elif message.startswith('BOARDS:'):
            try:
                boards_data = message[7:]
                boards = json.loads(boards_data)
                self.signals.boards_updated.emit(boards)
            except json.JSONDecodeError as e:
                print(f"Ошибка обработки списка досок: {e}")

    # отправляем сообщение на сервер
    def send(self, message):
        if not self.running:
            print("Клиент не подключен или отключен.")
            return

        try:
            self.socket.send((message + '\n').encode('utf-8'))
        except Exception as e:
            print(f"Ошибка отправки: {e}")
            self.disconnect()

    # отправляем новую таску на сервер
    def add_task(self, task):
        self.send(f"ADD:{self.current_board}:{json.dumps(task)}")

    # отправляем обновленный список тасок на сервер
    def update_tasks(self, tasks):
        self.send(f"UPDATE:{self.current_board}:{json.dumps(tasks)}")

    # Запрос задач для текущей или новой доски
    def get_tasks(self, board_name=None):
        if board_name:
            self.current_board = board_name
        self.send(f"GET_TASKS:{self.current_board}")

    def get_boards(self):
        self.send("GET_BOARDS:ALL")

    # отрубиться от сервера
    def disconnect(self):
        if self.running:
            self.running = False
            if self.socket:
                try:
                    self.socket.shutdown(socket.SHUT_RDWR)
                    self.socket.close()
                except:
                    pass

    @pyqtSlot()
    def send_task_update(self):
        if self.task_manager:
            self.task_manager.send_task_update()


class TaskManager(QWidget):
    def __init__(self, board_name="Главная доска"):
        super().__init__()
        self.board_name = board_name
        # обмениваемся ссылками друг на друга
        self.client = TaskClient(board=self.board_name)
        self.client.signals.tasks_updated.connect(self.update_tasks)
        self.client.task_manager = self

        self.tasks = []  # локальная копия задач
        self.task_widgets = []  # ссылки на виджеты задач

        self.setWindowTitle(f"Task Manager - {self.board_name}")

        layout = QVBoxLayout(self)

        # добавили статус подключения
        self.status_label = QLabel("Статус: Подключение...")
        layout.addWidget(self.status_label)

        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Введите задачу...")

        buttons_layout = QHBoxLayout()

        add_button = QPushButton("Добавить задачу")
        delete_button = QPushButton("Удалить выбранную задачу")
        clear_completed_task = QPushButton("Удалить все выполненные")

        self.tasks_list = QListWidget()

        buttons_layout.addWidget(add_button)
        buttons_layout.addWidget(delete_button)
        buttons_layout.addWidget(clear_completed_task)

        priority_layout = QHBoxLayout()

        self.low_priority = QRadioButton("Низкий")
        self.medium_priority = QRadioButton("Средний")
        self.high_priority = QRadioButton("Высокий")

        self.medium_priority.setChecked(True)

        priority_layout.addWidget(self.low_priority)
        priority_layout.addWidget(self.medium_priority)
        priority_layout.addWidget(self.high_priority)
        priority_layout.addStretch()

        layout.addWidget(self.task_input)
        layout.addLayout(priority_layout)
        layout.addLayout(buttons_layout)
        layout.addWidget(self.tasks_list)

        add_button.clicked.connect(self.add_task)
        self.task_input.returnPressed.connect(self.add_task)
        delete_button.clicked.connect(self.delete_task)
        clear_completed_task.clicked.connect(self.delete_completed_tasks)

        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_clock)
        self.time_timer.start(1000)

        # пытаемся подрубиться к серверу
        if self.client.connect():
            # запрашиваем текущие задачи
            self.client.get_tasks()
            self.update_clock()
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось подключиться к серверу")
            self.status_label.setText("Статус: Отключено")

    @pyqtSlot()
    def update_clock(self):
        now = datetime.now().strftime("%H:%M:%S")
        status_text = "Подключено" if self.client.running else "Отключено"
        self.status_label.setText(
            f"Доска: {self.board_name} | Статус: {status_text} | Задач: {len(self.tasks)} | Время: {now}")

    def get_priority(self):
        if self.high_priority.isChecked():
            return "high"
        elif self.low_priority.isChecked():
            return "low"
        return "medium"

    @pyqtSlot()
    def add_task(self):
        text = self.task_input.text().strip()
        if text:
            task_dict = {
                "text": text,
                "priority": self.get_priority(),
                "completed": False
            }
            # отправляем на сервер
            self.client.add_task(task_dict)
            self.task_input.clear()

    @pyqtSlot()
    def delete_task(self):
        selected_item = self.tasks_list.currentItem()
        if selected_item:
            reply = QMessageBox.question(
                self,
                "Подтверждение удаления",
                "Вы уверены?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                row = self.tasks_list.row(selected_item)
                current_tasks = []
                for i in range(self.tasks_list.count()):
                    item = self.tasks_list.item(i)
                    widget = self.tasks_list.itemWidget(item)
                    current_tasks.append({
                        "text": widget.text,
                        "priority": widget.priority,
                        "completed": widget.completed
                    })
                if 0 <= row < len(current_tasks):
                    current_tasks.pop(row)
                    self.client.update_tasks(current_tasks)

    @pyqtSlot()
    def delete_completed_tasks(self):
        # создаем новый список только с не выполненными задачами
        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            "Вы уверены?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            new_tasks = []
            for i in range(self.tasks_list.count()):
                item = self.tasks_list.item(i)
                widget = self.tasks_list.itemWidget(item)
                if not widget.completed:
                    new_tasks.append({
                        "text": widget.text,
                        "priority": widget.priority,
                        "completed": widget.completed
                    })
            # проверяем, есть ли что удалять
            if len(new_tasks) < self.tasks_list.count():
                # отправляем обновленный список на сервер
                self.client.update_tasks(new_tasks)
                # просто уведомление
                deleted_count = self.tasks_list.count() - len(new_tasks)
                msg = f"Удалено {deleted_count} выполненных задач"
                QMessageBox.information(self, "Информация", msg)
            else:
                QMessageBox.information(self, "Информация", "Нет выполненных задач для удаления")

    # функция отправки задачек на сервер
    def send_task_update(self):
        # собираем актуальное состояние из виджетов в словари
        current_tasks = []
        for i in range(self.tasks_list.count()):
            item = self.tasks_list.item(i)
            widget = self.tasks_list.itemWidget(item)
            # создаем словарь с данными задачи
            task_data = {
                "text": widget.text,
                "priority": widget.priority,
                "completed": widget.completed
            }
            current_tasks.append(task_data)

        # отправляем на сервер
        self.client.update_tasks(current_tasks)

    # обновляем интерфейс на основе полученных задач (вызывается из сетевого потока)
    @pyqtSlot(list, str)
    def update_tasks(self, tasks, board_name):
        if board_name != self.board_name:
            return

        self.tasks = tasks
        self.tasks_list.clear()
        self.task_widgets.clear()

        for task in tasks:
            widget = TaskWidget(task["text"], task["priority"], task["completed"])
            widget.set_client(self.client)

            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            self.tasks_list.addItem(item)
            self.tasks_list.setItemWidget(item, widget)
            self.task_widgets.append(widget)

        self.update_clock()
        self.setWindowTitle(f"Task Manager - {self.board_name}")

    # закрываем окошко
    def closeEvent(self, event):
        self.client.disconnect()
        self.time_timer.stop() #стопаем таймер
        event.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Выбор и управление досками")
        self.resize(400, 300)
        self.task_clients = {}

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        self.boads_list = QListWidget()
        self.create_board_button = QPushButton("Создать новую доску")
        self.refresh_button = QPushButton("Обновить список досок")
        self.open_button = QPushButton("Открыть доску")

        layout.addWidget(self.boads_list)
        layout.addWidget(self.create_board_button)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.open_button)

        self.open_button.clicked.connect(self.open_board)
        self.boads_list.itemDoubleClicked.connect(self.open_board)
        self.create_board_button.clicked.connect(self.create_new_board)
        self.refresh_button.clicked.connect(self.get_boards)

        self.board_client = TaskClient()
        self.board_client.signals.boards_updated.connect(self.update_board_list)

        if self.board_client.connect():
            self.get_boards()
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось подключиться к серверу досок")

    @pyqtSlot()
    def get_boards(self):
        self.board_client.get_boards()

    @pyqtSlot(list)
    def update_board_list(self, boards):
        self.boads_list.clear()
        for board_name in boards:
            self.boads_list.addItem(board_name)

    @pyqtSlot()
    def create_new_board(self):

        board_name, ok = QInputDialog.getText(self, 'Создать доску', 'Имя новой доски:')

        if ok and board_name.strip():
            board_name = board_name.strip()
            self.board_client.get_tasks(board_name=board_name)
            self.get_boards()


    @pyqtSlot()
    def open_board(self):
        selected_item = self.boads_list.currentItem()
        if selected_item:
            board_name = selected_item.text()

            if board_name in self.task_clients:
                self.task_clients[board_name].show()
                self.task_clients[board_name].activateWindow()
                return

            task_manager = TaskManager(board_name)
            task_manager.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            task_manager.destroyed.connect(lambda: self.task_clients.pop(board_name, None))

            self.task_clients[board_name] = task_manager
            task_manager.show()

    def closeEvent(self, event):
        self.board_client.disconnect()

        for manager in list(self.task_clients.values()):
            manager.close()

        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())