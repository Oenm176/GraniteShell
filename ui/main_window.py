# granite_shell/ui/main_window.py

# --- Standard & Third-Party Imports ---
import sys
import os
import html
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit
)
from PyQt6.QtGui import QIcon, QTextCursor, QKeyEvent, QMouseEvent
from PyQt6.QtCore import Qt, pyqtSignal

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller. """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS.
        base_path = sys._MEIPASS
    except Exception:
        # If not running as a PyInstaller bundle, use the current directory.
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# ===================================================================
# TerminalArea Class (The Core Interactive Widget)
# ===================================================================
# This class extends QTextEdit to create a custom, terminal-like input area.
# It handles input protection, command submission, and custom key presses.
class TerminalArea(QTextEdit):
    # A signal that is emitted when the user presses Enter to submit a command.
    commandEntered = pyqtSignal(str)

    def __init__(self, parent=None):
        """ Class constructor. Sets up the initial state of the terminal. """
        super().__init__(parent)
        self.prompt = "> " 
        self.input_start_pos = 0  # Stores the character position where user input begins.
        self.setAcceptRichText(False) # Disables rich text pasting to maintain plain text.
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu) # Disables the default right-click menu.
        
        # A list to store ranges of text (start, end positions) that should be read-only.
        self.protected_ranges: list[tuple[int, int]] = []


    def _pos_in_protected(self, pos: int) -> bool:
        """ Checks if a given cursor position is within any protected range. """
        for start, end in self.protected_ranges:
            if start <= pos < end:
                return True
        return False

    def _selection_overlaps_protected(self, start: int, end: int) -> bool:
        """ Checks if the current text selection overlaps with any protected range. """
        if start > end:
            start, end = end, start # Ensure start is always less than end.
        for protected_start, protected_end in self.protected_ranges:
            if start < protected_end and end > protected_start:
                return True
        return False


    def _show_prompt(self):
        """ Displays the command prompt at the end of the text area. """
        self.moveCursor(QTextCursor.MoveOperation.End)
        # Formats the prompt with a specific color using HTML.
        prompt_html = f'<font color="#61afef">{html.escape(self.prompt)}</font>'
        self.textCursor().insertHtml(prompt_html)
        # Records the position after the prompt as the start of user input.
        self.input_start_pos = self.textCursor().position()
        self.ensureCursorVisible()

    def add_hint(self, text: str):
        """ Adds a colored, italicized hint below the current input line. """
        # Save the user's current cursor position.
        input_cursor_position = self.textCursor().position()

        # Move to the very end of the document to add the hint.
        self.moveCursor(QTextCursor.MoveOperation.End)
        self.textCursor().insertHtml("<br>") # Add a new line.

        # Record the start position of the hint for protection.
        start = self.textCursor().position()
        
        # Insert the hint text formatted as colored, italic HTML.
        hint_html = f'<font style="color: #ff5555; font-style: italic;">{html.escape(text)}</font>'
        self.textCursor().insertHtml(hint_html)

        # Record the end position and add this range to the list of protected areas.
        end = self.textCursor().position()
        self.protected_ranges.append((start, end))

        # Restore the cursor back to where the user was typing.
        cursor = self.textCursor()
        cursor.setPosition(input_cursor_position)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()


    def keyPressEvent(self, event: QKeyEvent):
        """ Overrides the default key press handler to control user input. """
        cursor = self.textCursor()

        # --- MAJOR FIX: Check for the Enter key BEFORE any other checks ---
        is_enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.modifiers()
        if is_enter:
            # Select the text from the start of the input to the end of the line.
            cursor.setPosition(self.input_start_pos)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            command = cursor.selectedText().strip()

            # Move cursor to the absolute end of the document and add a newline.
            self.moveCursor(QTextCursor.MoveOperation.End)
            self.textCursor().insertText("\n")
            
            # If the command is not empty (or if the prompt is empty, for raw input), emit the signal.
            if command or self.prompt == "":
                self.commandEntered.emit(command)
            else:
                # If the command is empty, just show a new prompt.
                self._show_prompt()
            return # Stop further processing of the Enter key.

        # Handle Ctrl+A to select only the active input area.
        is_ctrl_a = (event.key() == Qt.Key.Key_A and event.modifiers() == Qt.KeyboardModifier.ControlModifier)
        if is_ctrl_a:
            cursor.setPosition(self.input_start_pos)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)
            return

        # If the selection overlaps with a protected area, reject the edit.
        if cursor.hasSelection():
            if self._selection_overlaps_protected(cursor.selectionStart(), cursor.selectionEnd()):
                cursor.clearSelection()
                cursor.setPosition(self.input_start_pos) # Move cursor to a safe position.
                self.setTextCursor(cursor)
                return

        # If the cursor is in a protected area, only allow navigation keys.
        nav_keys = [Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right,
                    Qt.Key.Key_PageUp, Qt.Key.Key_PageDown, Qt.Key.Key_Home, Qt.Key.Key_End]
        if self._pos_in_protected(cursor.position()):
            if event.key() in nav_keys:
                super().keyPressEvent(event) # Allow navigation.
            else:
                # If it's not a navigation key, move the cursor to the safe input area.
                cursor.setPosition(self.input_start_pos)
                self.setTextCursor(cursor)
            return

        # Prevent Backspace from deleting the prompt or protected text.
        if event.key() == Qt.Key.Key_Backspace and cursor.position() <= self.input_start_pos:
            return
        # Prevent Delete from working in protected areas.
        if event.key() == Qt.Key.Key_Delete and self._pos_in_protected(cursor.position()):
            return

        # Prevent editing anywhere before the current input line.
        if cursor.position() < self.input_start_pos:
            self.moveCursor(QTextCursor.MoveOperation.End)
            return

        # If all checks pass, allow the default key press behavior.
        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        """ Overrides the paste handler to prevent pasting into protected areas. """
        c = self.textCursor()
        # Reject paste if the selection overlaps with protected text.
        if c.hasSelection() and self._selection_overlaps_protected(c.selectionStart(), c.selectionEnd()):
            return
        # Reject paste if the cursor is in a protected area.
        if self._pos_in_protected(c.position()):
            return
        # Allow paste if all checks pass.
        return super().insertFromMimeData(source)
    
    def mousePressEvent(self, event: QMouseEvent):
        """ Overrides the mouse press handler for custom right-click behavior and cursor protection. """
        # Implement custom copy/paste on right-click.
        if event.button() == Qt.MouseButton.RightButton:
            if self.textCursor().hasSelection():
                self.copy()
            else:
                self.paste()
            event.accept()
            return
            
        super().mousePressEvent(event)
        
        # After a left-click, if the cursor lands in a protected area, move it back to the input prompt.
        if self._pos_in_protected(self.textCursor().position()):
            cursor = self.textCursor()
            cursor.setPosition(self.input_start_pos)
            self.setTextCursor(cursor)

    def add_output(self, text: str, is_html: bool = False, show_prompt: bool = True):
        """ Appends output to the terminal and optionally shows a new prompt. """
        self.moveCursor(QTextCursor.MoveOperation.End)
        # Insert text as either plain text or HTML.
        if is_html:
            self.insertHtml(text)
        else:
            self.textCursor().insertText(text)

        # Show a new prompt line after the output.
        if show_prompt:
            self.append("") # Ensures a new line.
            self._show_prompt()
        else:
            self.append("")
            
    def add_raw_text(self, text: str):
        """ Adds text for raw input (like 'Enter username: ') without a preceding prompt. """
        self.moveCursor(QTextCursor.MoveOperation.End)
        self.textCursor().insertText(f"{text}: ")
        self.input_start_pos = self.textCursor().position()

    def set_prompt_label(self, label: str):
        """ Sets the text for the command prompt. """
        self.prompt = label

# ===================================================================
# MainWindow Class (The Main Application Window)
# ===================================================================
# This class sets up the main window, contains the TerminalArea widget,
# and provides high-level methods to interact with the UI.
class MainWindow(QMainWindow):
    # A signal to forward the command from the terminal widget to the controller.
    command_submitted = pyqtSignal(str)

    def __init__(self):
        """ Class constructor. Sets up the window properties and UI. """
        super().__init__()
        self.username = "anonymous"
        # Set the application icon.
        icon_path = resource_path("asset\Granite_shell.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self._init_ui()

    def _init_ui(self):
        """ Initializes the User Interface elements of the main window. """
        self.setWindowTitle("GraniteShell")
        self.setGeometry(100, 100, 900, 600)
        self.setMinimumSize(900, 600)
        
        # Create the terminal widget and set it as the central widget.
        self.terminal = TerminalArea(self)
        self.setCentralWidget(self.terminal)
        
        # Connect the terminal's signal to this window's signal.
        self.terminal.commandEntered.connect(self.command_submitted.emit)
        
        self._apply_stylesheet()
        self.terminal.setFocus() # Set keyboard focus to the terminal on startup.

    def set_username(self, username: str, active_model: str = "N/A"):
        """ Sets the username, updates the prompt, and shows the welcome message. """
        self.username = username
        self.set_prompt_label(f"{username}> ")
        self._show_welcome_message(active_model)

    def update_username_and_prompt(self, new_username: str):
        """ Updates the username and the terminal prompt label. """
        self.username = new_username
        self.set_prompt_label(f"{new_username}> ")

    def set_prompt_label(self, label: str):
        """ A helper method to tell the terminal widget to change its prompt. """
        self.terminal.set_prompt_label(label)
        
    def display_raw_text(self, text: str):
        """ A helper method to display raw text for input. """
        self.terminal.add_raw_text(text)

    def display_hint(self, text: str):
        """ A helper method to display a hint message. """
        self.terminal.add_hint(text)

    def _show_welcome_message(self, active_model: str):
        """ Clears the screen and displays the initial welcome message and ASCII art. """
        self.terminal.clear()
        welcome_art = r"""
   ______                           _   _      _____ _          _ _ 
  / ____/___  ____ _____ _____  (_) | |    / ____| |         | | |
 | |  __ ( _ )/ __ `/ __ `/ __ \/ /  | |   | (___ | |__   ___| | |
 | | |_ |/ _ \/ /_/ / /_/ / / / / /   | |    \___ \| '_ \ / _ \ | |
 | |__| |  __/ (_| / (_| / / / / /    | |________) | | | |  __/ | |
  \_____\___/\__, /\__,_/_/ /_/_/     |______|_____/|_| |_|\___|_|_|
            /____/                                                  
"""
        welcome_message = f"Welcome to GraniteShell, {self.username}. To find out the command, type `/help`!"
        model_info = f"Active AI Model: {active_model}"
        
        # Combine all parts into a single HTML string for display.
        full_welcome_html = (
            f'<pre style="line-height: 1.0;"><font color="#61afef">{html.escape(welcome_art)}</font></pre>'
            f'<div>{html.escape(welcome_message)}</div>'
            f'<div><font color="#7ec699">{html.escape(model_info)}</font></div>'
        )
        
        # Display the message and show a new prompt.
        self.terminal.insertHtml(full_welcome_html)
        self.terminal.append("")
        self.terminal._show_prompt()
    
    def display_output(self, text: str, is_html: bool = False, show_prompt: bool = True):
        """ A high-level method to display output in the terminal. """
        self.terminal.add_output(text, is_html, show_prompt)

    def clear(self):
        """ Overrides the clear method to also reset protected ranges. """
        super().clear()
        self.protected_ranges.clear()
        self.input_start_pos = 0

    def clear_screen(self):
        """ Clears the terminal screen and displays a fresh prompt. """
        self.terminal.clear()
        self.terminal._show_prompt()

    def _apply_stylesheet(self):
        """ Applies a dark theme stylesheet to the terminal widget and its scrollbar. """
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

# Main entry point of the application.
if __name__ == '__main__':
    # This block is executed when the script is run directly.
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())