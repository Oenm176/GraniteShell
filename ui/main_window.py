# granite_shell/ui/main_window.py

import sys
import os
import html
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit
)
from PyQt6.QtGui import QIcon, QTextCursor, QKeyEvent, QMouseEvent
from PyQt6.QtCore import Qt, pyqtSignal

class TerminalArea(QTextEdit):
    commandEntered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.prompt = "> " 
        self.input_start_pos = 0
        self.setAcceptRichText(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        self.protected_ranges: list[tuple[int, int]] = []

    def _pos_in_protected(self, pos: int) -> bool:
        for a, b in self.protected_ranges:
            if a <= pos < b:
                return True
        return False

    def _selection_overlaps_protected(self, start: int, end: int) -> bool:
        if start > end:
            start, end = end, start
        for a, b in self.protected_ranges:
            if start < b and end > a:
                return True
        return False


    def _show_prompt(self):
        self.moveCursor(QTextCursor.MoveOperation.End)
        prompt_html = f'<font color="#61afef">{html.escape(self.prompt)}</font>'
        self.textCursor().insertHtml(prompt_html)
        self.input_start_pos = self.textCursor().position()
        self.ensureCursorVisible()

    def add_hint(self, text: str):
        # Simpan posisi kursor input pengguna.
        input_cursor_position = self.textCursor().position()

        # Pindah ke akhir seluruh dokumen.
        self.moveCursor(QTextCursor.MoveOperation.End)

        # Sisipkan baris baru secara eksplisit menggunakan HTML <br>
        # Ini lebih dapat diandalkan daripada insertBlock() untuk menghindari indentasi.
        self.textCursor().insertHtml("<br>")

        # Simpan posisi awal dari hint untuk proteksi.
        start = self.textCursor().position()
        
        # Gunakan <font> atau <span> alih-alih <div> untuk menghindari margin/padding tak terduga.
        hint_html = f'<font style="color: #ff5555; font-style: italic;">{html.escape(text)}</font>'
        self.textCursor().insertHtml(hint_html)

        # Simpan posisi akhir untuk proteksi.
        end = self.textCursor().position()
        self.protected_ranges.append((start, end))

        # Kembalikan kursor ke posisi input yang benar.
        cursor = self.textCursor()
        cursor.setPosition(input_cursor_position)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()


    def keyPressEvent(self, event: QKeyEvent):
        cursor = self.textCursor()

        # === PERBAIKAN UTAMA: Cek tombol Enter SEBELUM pengecekan lainnya ===
        is_enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.modifiers()
        if is_enter:
            cursor.setPosition(self.input_start_pos)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            command = cursor.selectedText().strip()

            # Pindahkan kursor ke akhir DOKUMEN, bukan hanya akhir baris
            self.moveCursor(QTextCursor.MoveOperation.End)
            self.textCursor().insertText("\n")
            
            if command or self.prompt == "":
                self.commandEntered.emit(command)
            else:
                self._show_prompt()
            return # Selesai, hentikan proses lebih lanjut

        # Ctrl+A tetap hanya memilih area input aktif
        is_ctrl_a = (event.key() == Qt.Key.Key_A and event.modifiers() == Qt.KeyboardModifier.ControlModifier)
        if is_ctrl_a:
            cursor.setPosition(self.input_start_pos)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)
            return

        # Jika selection melintasi protected, tolak edit
        if cursor.hasSelection():
            if self._selection_overlaps_protected(cursor.selectionStart(), cursor.selectionEnd()):
                cursor.clearSelection()
                cursor.setPosition(self.input_start_pos)
                self.setTextCursor(cursor)
                return

        # === Pengecekan area terproteksi sekarang dilakukan SETELAH pengecekan Enter ===
        # Jika kursor berada di protected, hanya izinkan navigasi
        nav_keys = [Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right,
                    Qt.Key.Key_PageUp, Qt.Key.Key_PageDown, Qt.Key.Key_Home, Qt.Key.Key_End]
        if self._pos_in_protected(cursor.position()):
            if event.key() in nav_keys:
                super().keyPressEvent(event)
            else:
                # Jika bukan tombol navigasi, pindahkan kursor ke area input yang aman
                cursor.setPosition(self.input_start_pos)
                self.setTextCursor(cursor)
            return

        # Cegah Backspace/Delete yang menyentuh protected
        if event.key() == Qt.Key.Key_Backspace and cursor.position() <= self.input_start_pos:
            return
        if event.key() == Qt.Key.Key_Delete and self._pos_in_protected(cursor.position()):
            return

        # Batas bawah: jangan mengedit sebelum input_start_pos
        if cursor.position() < self.input_start_pos:
            self.moveCursor(QTextCursor.MoveOperation.End)
            return

        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        c = self.textCursor()
        if c.hasSelection() and self._selection_overlaps_protected(c.selectionStart(), c.selectionEnd()):
            return
        if self._pos_in_protected(c.position()):
            return
        return super().insertFromMimeData(source)
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            if self.textCursor().hasSelection():
                self.copy()
            else:
                self.paste()
            event.accept()
            return
        super().mousePressEvent(event)
        # Setelah klik kiri, kalau kursor mendarat di protected, kembalikan ke area input
        if self._pos_in_protected(self.textCursor().position()):
            cursor = self.textCursor()
            cursor.setPosition(self.input_start_pos)
            self.setTextCursor(cursor)

    def add_output(self, text: str, is_html: bool = False, show_prompt: bool = True):
        self.moveCursor(QTextCursor.MoveOperation.End)
        if is_html:
            self.insertHtml(text)
        else:
            self.textCursor().insertText(text)

        if show_prompt:
            self.append("")
            self._show_prompt()
        else:
            self.append("")
            
    def add_raw_text(self, text: str):
        self.moveCursor(QTextCursor.MoveOperation.End)
        self.textCursor().insertText(f"{text}: ")
        self.input_start_pos = self.textCursor().position()

    def set_prompt_label(self, label: str):
        self.prompt = label

class MainWindow(QMainWindow):
    command_submitted = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.username = "anonymous"
        icon_path = r"D:\Pemograman Python\Project_Pyhton\GraniteShell\asset\Granite_shell_png.png"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("GraniteShell")
        self.setGeometry(100, 100, 900, 600)
        self.setMinimumSize(900, 600)
        self.terminal = TerminalArea(self)
        self.setCentralWidget(self.terminal)
        self.terminal.commandEntered.connect(self.command_submitted.emit)
        self._apply_stylesheet()
        self.terminal.setFocus()

    def set_username(self, username: str, active_model: str = "N/A"):
        self.username = username
        self.set_prompt_label(f"{username}> ")
        self._show_welcome_message(active_model)

    def update_username_and_prompt(self, new_username: str):
        self.username = new_username
        self.set_prompt_label(f"{new_username}> ")

    def set_prompt_label(self, label: str):
        self.terminal.set_prompt_label(label)
        
    def display_raw_text(self, text: str):
        self.terminal.add_raw_text(text)

    def display_hint(self, text: str):
        self.terminal.add_hint(text)

    def _show_welcome_message(self, active_model: str):
        self.terminal.clear()
        welcome_art = r"""
   ______                        _   _      _____ _          _ _ 
  / ____/___  ____ _____ _____  (_) | |    / ____| |        | | |
 | |  __ ( _ )/ __ `/ __ `/ __ \/ /  | |   | (___ | |__   ___| | |
 | | |_ |/ _ \/ /_/ / /_/ / / / / /   | |    \___ \| '_ \ / _ \ | |
 | |__| |  __/ (_| / (_| / / / / /    | |________) | | | |  __/ | |
  \_____\___/\__, /\__,_/_/ /_/_/     |______|_____/|_| |_|\___|_|_|
            /____/                                                 
"""
        welcome_message = f"Welcome to GraniteShell, {self.username}. To find out the command, type `/help`!"
        model_info = f"Active AI Model: {active_model}"
        
        full_welcome_html = (
            f'<pre style="line-height: 1.0;"><font color="#61afef">{html.escape(welcome_art)}</font></pre>'
            f'<div>{html.escape(welcome_message)}</div>'
            f'<div><font color="#7ec699">{html.escape(model_info)}</font></div>'
        )
        
        self.terminal.insertHtml(full_welcome_html)
        self.terminal.append("")
        self.terminal._show_prompt()
    
    def display_output(self, text: str, is_html: bool = False, show_prompt: bool = True):
        self.terminal.add_output(text, is_html, show_prompt)

    def clear(self):
        super().clear()
        self.protected_ranges.clear()
        self.input_start_pos = 0

    def _apply_stylesheet(self):
        font_family = "Consolas, 'Courier New', monospace"
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #dcdcdc;
                font-family: {font_family};
                font-size: 14px;
                border: none;
                padding: 10px;
                line-height: 1.2;
            }}
            QScrollBar:vertical {{
                border: none;
                background: #252526;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #555555;
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())