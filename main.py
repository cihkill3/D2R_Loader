import sys
import os
import json
import subprocess
import psutil
import winreg
import ctypes
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, 
                             QGroupBox, QSystemTrayIcon, QMenu, QAction, 
                             QFileDialog, QMessageBox, QCheckBox, QFrame)
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import Qt, QSharedMemory

# =============================================================================
# 1. 리소스 경로 및 설정 관리
# =============================================================================
def resource_path(relative_path):
    """
    PyInstaller로 빌드된 EXE 실행 시, 임시 폴더(_MEIPASS)에서 리소스를 찾고
    개발 중일 때는 현재 폴더에서 찾습니다.
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class ConfigManager:
    def __init__(self):
        # 설정 파일은 실제 실행 파일이 있는 위치에 저장 (임시 폴더 아님)
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.config_file = os.path.join(base_dir, "config.json")
        self.default_config = {
            "nunchi_path": r"C:\Users\cihki\Downloads\눈치코치_무설치\NunchiRun.exe",
            "d2r_path": r"C:\Program Files (x86)\Diablo II Resurrected\Diablo II Resurrected Launcher.exe",
            "d2rso_path": r"C:\Users\cihki\Downloads\D2RSO.1.0.6\D2RSO.exe",
            "auto_start": False
        }
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return self.default_config
        return self.default_config

    def save_config(self, new_config):
        self.config = new_config
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

# =============================================================================
# 2. 프로세스 제어 클래스
# =============================================================================
class ProcessManager:
    @staticmethod
    def run_process(path):
        if os.path.exists(path):
            try:
                subprocess.Popen(path, shell=True, cwd=os.path.dirname(path))
                return True, "실행 성공"
            except Exception as e:
                return False, str(e)
        else:
            return False, "파일을 찾을 수 없습니다."

    @staticmethod
    def kill_process_by_name(proc_name):
        count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and proc_name.lower() in proc.info['name'].lower():
                    proc.kill()
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return count

# =============================================================================
# 3. 메인 GUI 클래스
# =============================================================================
class D2RLoaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg_mgr = ConfigManager()
        self.config = self.cfg_mgr.config
        
        # 1. 아이콘 로드 (내장 리소스 활용)
        self.icon_path = resource_path("app_icon.ico")
        if os.path.exists(self.icon_path):
            self.app_icon = QIcon(self.icon_path)
        else:
            self.app_icon = self.style().standardIcon(self.style().SP_ComputerIcon)
        
        self.initUI()
        self.setup_tray()
        self.apply_stylesheet()
        self.apply_dark_title_bar() 

        # 자동 실행 여부 체크
        if self.config["auto_start"]:
            self.register_startup(True)
        
    def initUI(self):
        self.setWindowTitle("D2R Program Loader")
        self.setWindowIcon(self.app_icon)
        self.setFixedSize(450, 580)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 1. Nunchi Card
        self.card_nunchi, self.input_nunchi = self.create_card(
            "1. Nunchi (눈치코치)", 
            self.config["nunchi_path"], 
            lambda: self.run_single("nunchi"), 
            lambda: self.kill_single("nunchi")
        )
        main_layout.addWidget(self.card_nunchi)

        # 2. D2R Card
        self.card_d2r, self.input_d2r = self.create_card(
            "2. Diablo II Resurrected", 
            self.config["d2r_path"], 
            lambda: self.run_single("d2r"), 
            lambda: self.kill_single("d2r")
        )
        main_layout.addWidget(self.card_d2r)

        # 3. D2RSO Card
        self.card_d2rso, self.input_d2rso = self.create_card(
            "3. D2R Skill Overlay", 
            self.config["d2rso_path"], 
            lambda: self.run_single("d2rso"), 
            lambda: self.kill_single("d2rso")
        )
        main_layout.addWidget(self.card_d2rso)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)

        # 옵션
        self.chk_autostart = QCheckBox("윈도우 시작 시 자동 실행")
        self.chk_autostart.setChecked(self.config["auto_start"])
        self.chk_autostart.stateChanged.connect(self.toggle_autostart)
        main_layout.addWidget(self.chk_autostart)

        # 4. 전체 제어 버튼
        control_layout = QHBoxLayout()
        
        btn_run_all = QPushButton("🚀 전체 실행 (Run All)")
        btn_run_all.setObjectName("btn_run_all")
        btn_run_all.clicked.connect(self.run_all)
        btn_run_all.setMinimumHeight(45)
        
        btn_kill_all = QPushButton("💀 전체 종료 (Kill All)")
        btn_kill_all.setObjectName("btn_kill_all")
        btn_kill_all.clicked.connect(self.kill_all)
        btn_kill_all.setMinimumHeight(45)

        control_layout.addWidget(btn_run_all)
        control_layout.addWidget(btn_kill_all)
        main_layout.addLayout(control_layout)

    def create_card(self, title, initial_path, run_func, kill_func):
        group = QGroupBox(title)
        layout = QVBoxLayout()
        
        path_layout = QHBoxLayout()
        input_field = QLineEdit(initial_path)
        input_field.setReadOnly(True)
        
        btn_find = QPushButton("📂")
        btn_find.setFixedSize(30, 30)
        btn_find.clicked.connect(lambda: self.find_file(input_field, title))
        
        path_layout.addWidget(input_field)
        path_layout.addWidget(btn_find)
        
        btn_layout = QHBoxLayout()
        btn_run = QPushButton("▶ 실행")
        btn_run.setObjectName("btn_run")
        btn_run.clicked.connect(run_func)
        
        btn_kill = QPushButton("■ 종료")
        btn_kill.setObjectName("btn_kill")
        btn_kill.clicked.connect(kill_func)
        
        btn_layout.addWidget(btn_run)
        btn_layout.addWidget(btn_kill)
        
        layout.addLayout(path_layout)
        layout.addLayout(btn_layout)
        group.setLayout(layout)
        
        return group, input_field

    def apply_dark_title_bar(self):
        """ 윈도우 10/11 DWM API를 사용하여 타이틀바를 다크 모드로 변경 """
        try:
            hwnd = int(self.winId())
            value = ctypes.c_int(1) # True
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), 4)
        except Exception:
            pass

    def apply_stylesheet(self):
        style = """
        QMainWindow { background-color: #2b2b2b; }
        QGroupBox {
            background-color: #383838;
            border: 1px solid #444;
            border-radius: 8px;
            margin-top: 10px;
            font-weight: bold;
            color: #eeeeee;
            font-size: 13px;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }
        QLineEdit {
            background-color: #1e1e1e; color: #aaaaaa;
            border: 1px solid #444; border-radius: 4px; padding: 5px;
        }
        QPushButton {
            background-color: #505050; color: white;
            border: none; border-radius: 4px; padding: 6px; font-weight: bold;
        }
        QPushButton:hover { background-color: #606060; }
        QPushButton:pressed { background-color: #404040; }
        
        QPushButton#btn_run { background-color: #2e7d32; }
        QPushButton#btn_run:hover { background-color: #388e3c; }
        
        QPushButton#btn_kill { background-color: #c62828; }
        QPushButton#btn_kill:hover { background-color: #d32f2f; }

        QPushButton#btn_run_all { background-color: #1565c0; font-size: 14px; }
        QPushButton#btn_run_all:hover { background-color: #1976d2; }

        QPushButton#btn_kill_all { background-color: #b71c1c; font-size: 14px; }
        QPushButton#btn_kill_all:hover { background-color: #c62828; }

        QCheckBox { color: #eeeeee; spacing: 8px; }
        """
        self.setStyleSheet(style)

    # --- 기능 구현 ---
    def find_file(self, line_edit, title):
        fname, _ = QFileDialog.getOpenFileName(self, f'{title} 실행파일 선택', '', 'Executable (*.exe)')
        if fname:
            fname = os.path.normpath(fname)
            line_edit.setText(fname)
            self.save_current_settings()

    def save_current_settings(self):
        new_config = {
            "nunchi_path": self.input_nunchi.text(),
            "d2r_path": self.input_d2r.text(),
            "d2rso_path": self.input_d2rso.text(),
            "auto_start": self.chk_autostart.isChecked()
        }
        self.cfg_mgr.save_config(new_config)
        self.config = new_config

    def toggle_autostart(self, state):
        self.register_startup(state == Qt.Checked)
        self.save_current_settings()

    def register_startup(self, enable):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "D2RLoader"
        exe_path = f'"{sys.executable}"'
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            pass

    # --- 실행 / 종료 로직 ---
    def run_single(self, key):
        path = self.config.get(f"{key}_path", "")
        success, msg = ProcessManager.run_process(path)
        if not success:
            QMessageBox.warning(self, "실행 오류", f"실행 실패: {msg}\n경로를 확인해주세요.")

    def kill_single(self, key):
        target = ""
        if key == "nunchi": target = "Nunchi.exe"
        elif key == "d2r": target = "D2R.exe"
        elif key == "d2rso": target = "D2RSO.exe"
        
        ProcessManager.kill_process_by_name(target)
        if key == "d2r":
            ProcessManager.kill_process_by_name("Battle.net.exe")

    def run_all(self):
        paths = [self.config["nunchi_path"], self.config["d2r_path"], self.config["d2rso_path"]]
        missing = [p for p in paths if not os.path.exists(p)]
        
        if missing:
            reply = QMessageBox.question(self, '확인', 
                '설정된 경로에 없는 파일이 있습니다.\n존재하는 프로그램만 실행할까요?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return

        if os.path.exists(self.config["nunchi_path"]): ProcessManager.run_process(self.config["nunchi_path"])
        if os.path.exists(self.config["d2r_path"]): ProcessManager.run_process(self.config["d2r_path"])
        if os.path.exists(self.config["d2rso_path"]): ProcessManager.run_process(self.config["d2rso_path"])

    def kill_all(self):
        """ 모든 관련 프로세스 종료 """
        targets = ["nunchi.exe", "D2R.exe", "D2RSO.exe", "Battle.net.exe"]
        for t in targets:
            ProcessManager.kill_process_by_name(t)
        # QApplication.quit()

    def kill_all_exit(self):
        """ 모든 관련 프로세스 종료 및 프로그램 종료 """
        self.kill_all()
        QApplication.quit()

    def quit_loader(self):
        """ 프로그램만 종료 """
        QApplication.quit()

    # --- 트레이 아이콘 설정 ---
    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)
        
        menu = QMenu()
        
        # 1. 열기
        action_open = QAction("열기", self)
        action_open.triggered.connect(self.show_window)
        menu.addAction(action_open)

        menu.addSeparator()
        
        # 2. 전체 실행 (추가됨)
        action_run_all = QAction("🚀 전체 실행 (Run All)", self)
        action_run_all.triggered.connect(self.run_all)
        menu.addAction(action_run_all)
        
        # 3. 전체 종료
        action_kill_all = QAction("🔥 전체 종료 (Kill All)", self)
        action_kill_all.triggered.connect(self.kill_all)
        menu.addAction(action_kill_all)

        menu.addSeparator()

        # 4. 전체 종료 & 프로그램 종료
        action_kill_all_exit = QAction("⛔ 전체 && 로더 종료 (Kill All && Exit)", self)
        action_kill_all_exit.triggered.connect(self.kill_all_exit)
        menu.addAction(action_kill_all_exit)

        # 5. 프로그램 종료
        action_quit = QAction("🔚 로더 종료 (Exit)", self)
        action_quit.triggered.connect(self.quit_loader)
        menu.addAction(action_quit)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_activate)
        self.tray_icon.show()

    def on_tray_activate(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_window()

    def show_window(self):
        self.show()
        self.activateWindow()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)

    def closeEvent(self, event):
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 중복 실행 방지
    shared = QSharedMemory("D2RLoader_Unique_ID_Key_v1")
    if not shared.create(1):
        sys.exit(0)
    
    font = QFont("Malgun Gothic", 9)
    app.setFont(font)
    
    loader = D2RLoaderApp()
    # 시작 시 창 안 띄움
    
    sys.exit(app.exec_())