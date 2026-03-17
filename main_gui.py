# main_gui_pyside6_fixed.py
import sys
import re
import threading
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QTextEdit,
    QTabWidget, QFrame, QScrollArea, QMessageBox, QCheckBox,
    QSizePolicy, QSpacerItem, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QObject, QThread, QTimer
from PySide6.QtGui import QFont, QColor, QPalette

# 直接导入业务逻辑模块
from fun_class_logic import run_fun_class
from normal_full_logic import run_normal_full
from normal_logic import run_normal_class


class LogSignal(QObject):
    """用于线程安全地更新日志"""
    log_signal = Signal(str)
    clear_signal = Signal()
    task_finished_signal = Signal()


class XKHelperApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("西电选课脚本 v1.3")
        self.resize(700, 950)

        # 全局状态
        self.running = False
        self.task_active = False
        self.stop_flag = lambda: not self.running

        # 全局配置变量
        self.global_ua = ""
        self.global_lang = ""
        self.global_batch = ""
        self.global_cookie = ""

        # 信号对象
        self.log_signal_obj = LogSignal()
        self.log_signal_obj.log_signal.connect(self.append_log)
        self.log_signal_obj.clear_signal.connect(self.clear_log)
        self.log_signal_obj.task_finished_signal.connect(self.on_task_finished)

        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 1. 顶部粘贴解析区
        self.create_paste_parse_section(main_layout)
        self.create_global_inputs(main_layout)

        # 2. 选项卡区域
        self.notebook = QTabWidget()
        self.notebook.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.notebook)

        # Tab 1: 普通/体育自动选课
        self.tab1 = QWidget()
        self.notebook.addTab(self.tab1, "普通/体育自动选课")
        self.create_normal_tab(self.tab1)

        # Tab 2: 普通/体育补选监控
        self.tab2 = QWidget()
        self.notebook.addTab(self.tab2, "普通/体育补选监控")
        self.create_full_tab(self.tab2)

        # Tab 3: 通识选修补选监控
        self.tab3 = QWidget()
        self.notebook.addTab(self.tab3, "通识选修补选监控")
        self.create_fun_tab(self.tab3)

        # 3. 日志区域
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMinimumHeight(120)
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_group)

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #2c3e50;
            }
            QTabWidget::pane {
                border: 1px solid #ccc;
                border-radius: 5px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                border: 1px solid #ccc;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 15px;
                margin-right: 2px;
                color: #555;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #2c3e50;
                font-weight: bold;
            }
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
                background-color: #fff;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
            QPushButton#stopBtn {
                background-color: #e74c3c;
            }
            QPushButton#stopBtn:hover {
                background-color: #c0392b;
            }
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #2b2b2b;
                color: #f8f8f2;
            }
            QLabel {
                color: #333;
            }
        """)

    def create_paste_parse_section(self, parent_layout):
        group = QGroupBox("📌 粘贴完整配置字符串")
        layout = QVBoxLayout(group)

        self.paste_input = QLineEdit()
        self.paste_input.setPlaceholderText("在此粘贴包含 UserAgentTypeIn, AcceptLanguage 等的配置文本...")
        layout.addWidget(self.paste_input)

        btn = QPushButton("自动解析并填充全局配置")
        btn.clicked.connect(self.parse_and_fill)
        layout.addWidget(btn)

        parent_layout.addWidget(group)

    def parse_and_fill(self):
        text = self.paste_input.text().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请先粘贴配置字符串！")
            return

        ua_match = re.search(r'UserAgentTypeIn\s*=\s*"([^"]+)"', text)
        lang_match = re.search(r'AcceptLanguage\s*=\s*"([^"]+)"', text)
        batch_match = re.search(r'BatchID\s*=\s*"([^"]+)"', text)
        cookie_match = re.search(r'CookieIsHere\s*=\s*"([^"]+)"', text)

        updated = False

        if ua_match:
            self.global_ua = ua_match.group(1)
            self.ua_input.setText(self.global_ua)
            updated = True
        if lang_match:
            self.global_lang = lang_match.group(1)
            self.lang_input.setText(self.global_lang)
            updated = True
        if batch_match:
            self.global_batch = batch_match.group(1)
            self.batch_input.setText(self.global_batch)
            updated = True
        if cookie_match:
            self.global_cookie = cookie_match.group(1)
            self.cookie_input.setText(self.global_cookie)
            updated = True

        if updated:
            QMessageBox.information(self, "成功", "全局配置已自动填充！")
            self.paste_input.clear()
        else:
            QMessageBox.warning(self, "警告", "未识别到有效字段，请检查格式。")

    def create_global_inputs(self, parent_layout):
        group = QGroupBox("🌐 全局配置 (所有页面共用)")
        layout = QVBoxLayout(group)
        grid = QGridLayout()

        labels = ["User-Agent:", "Accept-Language:", "BatchID:", "Cookie:"]

        for i, label in enumerate(labels):
            lbl = QLabel(label)
            lbl.setFixedWidth(100)
            entry = QLineEdit()
            entry.setPlaceholderText(f"请输入 {label}")

            # 保存引用以便 parse_and_fill 使用
            if i == 0:
                self.ua_input = entry
            elif i == 1:
                self.lang_input = entry
            elif i == 2:
                self.batch_input = entry
            elif i == 3:
                self.cookie_input = entry

            # 实时同步全局变量
            entry.textChanged.connect(lambda text, idx=i: self.update_global_var(idx, text))

            grid.addWidget(lbl, i, 0)
            grid.addWidget(entry, i, 1)

        layout.addLayout(grid)
        parent_layout.addWidget(group)

    def update_global_var(self, idx, text):
        if idx == 0:
            self.global_ua = text
        elif idx == 1:
            self.global_lang = text
        elif idx == 2:
            self.global_batch = text
        elif idx == 3:
            self.global_cookie = text

    def create_normal_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setSpacing(10)

        # 轮询参数
        param_group = QGroupBox("⚙️ 轮询参数")
        param_layout = QHBoxLayout(param_group)

        self.normal_try_input = QLineEdit("2")
        self.normal_between_input = QLineEdit("1")

        param_layout.addWidget(QLabel("尝试次数:"))
        param_layout.addWidget(self.normal_try_input)
        param_layout.addSpacing(20)
        param_layout.addWidget(QLabel("轮询间隔 (秒):"))
        param_layout.addWidget(self.normal_between_input)
        param_layout.addStretch()
        layout.addWidget(param_group)

        # 定时启动
        self.time_group = QGroupBox("🕒 定时启动（可选）")
        time_layout = QVBoxLayout(self.time_group)

        self.enable_time_check = QCheckBox("启用定时启动（到达指定时间自动开始）")
        self.enable_time_check.stateChanged.connect(self.toggle_time_inputs)
        time_layout.addWidget(self.enable_time_check)

        self.time_input_frame = QFrame()
        time_row = QHBoxLayout(self.time_input_frame)
        time_row.setContentsMargins(20, 0, 0, 0)

        self.target_hour = QLineEdit("09")
        self.target_minute = QLineEdit("00")
        self.target_second = QLineEdit("00")
        self.target_hour.setFixedWidth(40)
        self.target_minute.setFixedWidth(40)
        self.target_second.setFixedWidth(40)

        time_row.addWidget(QLabel("目标时间:"))
        time_row.addWidget(self.target_hour)
        time_row.addWidget(QLabel("时"))
        time_row.addWidget(self.target_minute)
        time_row.addWidget(QLabel("分"))
        time_row.addWidget(self.target_second)
        time_row.addWidget(QLabel("秒"))
        time_row.addStretch()

        self.time_input_frame.setVisible(False)
        time_layout.addWidget(self.time_input_frame)
        layout.addWidget(self.time_group)

        # 课程列表
        course_group = QGroupBox("课程列表（可添加多门）")
        self.course_layout = QVBoxLayout(course_group)
        self.normal_courses_widgets = []

        btn_row = QHBoxLayout()
        add_btn = QPushButton("添加课程")
        add_btn.clicked.connect(self.add_normal_course)
        clear_btn = QPushButton("清空所有课程")
        clear_btn.clicked.connect(self.clear_normal_courses)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()

        self.course_layout.addLayout(btn_row)

        # 滚动区域容纳课程
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(150)
        scroll_content = QWidget()
        self.course_container_layout = QVBoxLayout(scroll_content)
        scroll_content.setLayout(self.course_container_layout)
        scroll.setWidget(scroll_content)
        self.course_layout.addWidget(scroll)

        layout.addWidget(course_group)

        # 底部按钮
        action_row = QHBoxLayout()
        self.normal_start_btn = QPushButton("开始抢课")
        self.normal_start_btn.clicked.connect(self.start_normal)
        self.normal_stop_btn = QPushButton("停止抢课")
        self.normal_stop_btn.setObjectName("stopBtn")
        self.normal_stop_btn.setEnabled(False)
        self.normal_stop_btn.clicked.connect(self.stop_task)

        action_row.addWidget(self.normal_start_btn)
        action_row.addWidget(self.normal_stop_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        layout.addStretch()

    def toggle_time_inputs(self, state):
        self.time_input_frame.setVisible(bool(state))

    def add_normal_course(self):
        idx = len(self.normal_courses_widgets) + 1
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        row = QHBoxLayout(frame)
        row.setContentsMargins(5, 5, 5, 5)

        campus_input = QLineEdit("S")
        campus_input.setFixedWidth(40)
        type_input = QLineEdit("TJKC")
        type_input.setFixedWidth(80)
        key_input = QLineEdit()
        key_input.setPlaceholderText("请输入课程关键词")

        del_btn = QPushButton("删除")
        del_btn.setFixedWidth(60)
        del_btn.setStyleSheet("background-color: #e74c3c; padding: 4px;")
        del_btn.clicked.connect(lambda: self.remove_normal_course(frame))

        row.addWidget(QLabel(f"课程{idx}:"))
        row.addWidget(QLabel("校区:"))
        row.addWidget(campus_input)
        row.addWidget(QLabel("类型:"))
        row.addWidget(type_input)
        row.addWidget(QLabel("关键词:"))
        row.addWidget(key_input)
        row.addWidget(del_btn)
        row.addStretch()

        self.course_container_layout.addWidget(frame)
        self.normal_courses_widgets.append({
            "frame": frame,
            "campus": campus_input,
            "type": type_input,
            "key": key_input
        })

    def remove_normal_course(self, frame):
        for item in self.normal_courses_widgets:
            if item["frame"] == frame:
                self.course_container_layout.removeWidget(frame)
                frame.deleteLater()
                self.normal_courses_widgets.remove(item)
                break

    def clear_normal_courses(self):
        for item in self.normal_courses_widgets[:]:
            self.course_container_layout.removeWidget(item["frame"])
            item["frame"].deleteLater()
        self.normal_courses_widgets.clear()

    def create_full_tab(self, parent):
        layout = QVBoxLayout(parent)

        param_group = QGroupBox("⚙️ 监控参数")
        param_layout = QHBoxLayout(param_group)
        self.full_try_input = QLineEdit("1000")
        self.full_between_input = QLineEdit("5")
        param_layout.addWidget(QLabel("尝试次数:"))
        param_layout.addWidget(self.full_try_input)
        param_layout.addWidget(QLabel("轮询间隔 (秒):"))
        param_layout.addWidget(self.full_between_input)
        param_layout.addStretch()
        layout.addWidget(param_group)

        self._create_single_course_ui(layout, prefix="full", title="监控课程", default_type="TJKC",
                                      placeholder="请输入课程关键词")

        action_row = QHBoxLayout()
        self.full_start_btn = QPushButton("开始监控")
        self.full_start_btn.clicked.connect(self.start_full)
        self.full_stop_btn = QPushButton("停止监控")
        self.full_stop_btn.setObjectName("stopBtn")
        self.full_stop_btn.setEnabled(False)
        self.full_stop_btn.clicked.connect(self.stop_task)
        action_row.addWidget(self.full_start_btn)
        action_row.addWidget(self.full_stop_btn)
        action_row.addStretch()
        layout.addLayout(action_row)
        layout.addStretch()

    def create_fun_tab(self, parent):
        layout = QVBoxLayout(parent)

        param_group = QGroupBox("⚙️ 监控参数")
        param_layout = QHBoxLayout(param_group)
        self.fun_try_input = QLineEdit("1000")
        self.fun_between_input = QLineEdit("5")
        param_layout.addWidget(QLabel("尝试次数:"))
        param_layout.addWidget(self.fun_try_input)
        param_layout.addWidget(QLabel("轮询间隔 (秒):"))
        param_layout.addWidget(self.fun_between_input)
        param_layout.addStretch()
        layout.addWidget(param_group)

        self._create_single_course_ui(layout, prefix="fun", title="通识课程", default_type="XGKC",
                                      placeholder="请输入通识课关键词")

        action_row = QHBoxLayout()
        self.fun_start_btn = QPushButton("开始监控")
        self.fun_start_btn.clicked.connect(self.start_fun)
        self.fun_stop_btn = QPushButton("停止监控")
        self.fun_stop_btn.setObjectName("stopBtn")
        self.fun_stop_btn.setEnabled(False)
        self.fun_stop_btn.clicked.connect(self.stop_task)
        action_row.addWidget(self.fun_start_btn)
        action_row.addWidget(self.fun_stop_btn)
        action_row.addStretch()
        layout.addLayout(action_row)
        layout.addStretch()

    def _create_single_course_ui(self, layout, prefix, title, default_type, placeholder):
        group = QGroupBox(title)
        gl = QVBoxLayout(group)
        row = QHBoxLayout()

        campus_input = QLineEdit("S")
        campus_input.setFixedWidth(40)
        type_input = QLineEdit(default_type)
        type_input.setFixedWidth(100)
        key_input = QLineEdit()
        key_input.setPlaceholderText(placeholder)

        setattr(self, f"{prefix}_campus", campus_input)
        setattr(self, f"{prefix}_type", type_input)
        setattr(self, f"{prefix}_key", key_input)

        row.addWidget(QLabel("校区:"))
        row.addWidget(campus_input)
        row.addWidget(QLabel("课程类型:"))
        row.addWidget(type_input)
        row.addWidget(QLabel("关键词:"))
        row.addWidget(key_input)
        row.addStretch()

        gl.addLayout(row)
        layout.addWidget(group)

    def append_log(self, msg):
        self.log_text.append(msg)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_log(self):
        self.log_text.clear()

    def stop_task(self):
        if self.task_active:
            self.append_log("正在请求停止任务...")
            self.running = False


    def set_buttons_state(self, running):
        start_enabled = not running
        stop_enabled = running

        self.normal_start_btn.setEnabled(start_enabled)
        self.full_start_btn.setEnabled(start_enabled)
        self.fun_start_btn.setEnabled(start_enabled)

        self.normal_stop_btn.setEnabled(stop_enabled)
        self.full_stop_btn.setEnabled(stop_enabled)
        self.fun_stop_btn.setEnabled(stop_enabled)

    def on_task_finished(self):
        self.task_active = False
        self.running = False
        self.set_buttons_state(False)
        self.append_log("任务已结束。")

    def validate_number(self, line_edit, min_val=0, allow_float=False):
        text = line_edit.text().strip()
        try:
            val = float(text) if allow_float else int(text)
            if val <= min_val:
                raise ValueError
            return val
        except ValueError:
            return None

    def start_normal(self):
        if self.task_active:
            QMessageBox.warning(self, "警告", "已有任务正在运行！")
            return

        courses = []
        for c in self.normal_courses_widgets:
            key = c["key"].text().strip()
            if key:
                courses.append({
                    "campus": c["campus"].text().strip() or "S",
                    "teachingClassType": c["type"].text(),
                    "KEY": key,
                    "clazzType": c["type"].text()
                })

        if not courses:
            QMessageBox.warning(self, "警告", "请至少添加一门有效课程！")
            return

        try_times = self.validate_number(self.normal_try_input)
        between_time = self.validate_number(self.normal_between_input, allow_float=True)

        if try_times is None or between_time is None:
            QMessageBox.critical(self, "错误", "轮询参数必须为正数！")
            return

        config = {
            "UserAgent": self.global_ua,
            "AcceptLanguage": self.global_lang,
            "BatchID": self.global_batch,
            "Cookie": self.global_cookie,
            "campus": "S",
            "TryTimes": try_times,
            "BetweenTime": between_time,
            "courses": courses,
            "SetTimeAndStart": 1 if self.enable_time_check.isChecked() else 0
        }

        if config["SetTimeAndStart"]:
            try:
                h = int(self.target_hour.text())
                m = int(self.target_minute.text())
                s = int(self.target_second.text())
                if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
                    raise ValueError
                config["target_hour"] = h
                config["target_minute"] = m
                config["target_second"] = s
            except:
                QMessageBox.critical(self, "错误", "目标时间格式错误！")
                return

        self.run_task_thread(run_normal_class, config)

    def start_full(self):
        self._start_single_monitor("full", run_normal_full)

    def start_fun(self):
        self._start_single_monitor("fun", run_fun_class)

    def _start_single_monitor(self, prefix, target_func):
        if self.task_active:
            QMessageBox.warning(self, "警告", "已有任务正在运行！")
            return

        key_input = getattr(self, f"{prefix}_key")
        key = key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "警告", "请输入课程关键词！")
            return

        try_times = self.validate_number(getattr(self, f"{prefix}_try_input"))
        between_time = self.validate_number(getattr(self, f"{prefix}_between_input"), allow_float=True)

        if try_times is None or between_time is None:
            QMessageBox.critical(self, "错误", "轮询参数无效！")
            return

        config = {
            "UserAgent": self.global_ua,
            "AcceptLanguage": self.global_lang,
            "BatchID": self.global_batch,
            "Cookie": self.global_cookie,
            "campus": getattr(self, f"{prefix}_campus").text().strip() or "S",
            "teachingClassType": getattr(self, f"{prefix}_type").text(),
            "KEY": key,
            "ClazzType": getattr(self, f"{prefix}_type").text(),
            "TryTimes": try_times,
            "BetweenTime": between_time,
            "SetTimeAndStart": 0
        }

        self.run_task_thread(target_func, config)

    def run_task_thread(self, target_func, config):
        self.clear_log()
        self.running = True
        self.task_active = True
        self.set_buttons_state(True)
        self.append_log("任务启动中...")

        thread = threading.Thread(target=self._worker, args=(target_func, config), daemon=True)
        thread.start()

    def _worker(self, target_func, config):
        try:
            target_func(config, self.log_wrapper, self.stop_flag)
        except Exception as e:
            self.log_signal_obj.log_signal.emit(f"发生错误：{str(e)}")
        finally:
            self.log_signal_obj.task_finished_signal.emit()

    def log_wrapper(self, msg):
        self.log_signal_obj.log_signal.emit(str(msg))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)

    window = XKHelperApp()
    window.show()
    sys.exit(app.exec())