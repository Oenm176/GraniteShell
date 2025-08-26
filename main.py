# granite_shell/main.py

import sys
import os
import re
import html
from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow
from utils.file_handler import ProfileHandler
from api.granite_api import GraniteAPI

class Controller:
    PROFILE_FILE = os.path.join('data', 'profil.json')

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.profile_handler = ProfileHandler(self.PROFILE_FILE)
        self.view = MainWindow()
        self.view.command_submitted.connect(self._handle_command)
        
        self.granite_api = None
        self.profile_data = {}
        self.current_mode = "default"

    def run(self):
        self.view.show()
        self._setup_user_profile()
        sys.exit(self.app.exec())

    def _initialize_api_from_profile(self):
        """Menginisialisasi atau re-inisialisasi API berdasarkan profil."""
        try:
            active_model_name = self.profile_data.get("active_model", "ibm-granite")
            model_config = self.profile_data.get("models", {}).get(active_model_name)
            
            if not model_config:
                raise ValueError(f"Configuration for active model '{active_model_name}' not found.")

            self.granite_api = GraniteAPI(model_config)
            self.save_path = self.profile_data.get("save_path", os.getcwd())
            self.view.username = self.profile_data.get("username", "anonymous")
            
            self.view.set_username(self.view.username, active_model_name)

        except ValueError as e:
            self.view.display_output(f"API Initialization Error: {e}\nPlease check your profile or token.")
            self.granite_api = None

    def _setup_user_profile(self):
        """
        PERBAIKAN: Merestrukturisasi logika setup secara total.
        """
        profile_data = self.profile_handler.read_profile()

        # Alur 1: Pengguna baru (profil.json tidak ada) -> WAJIB SETUP LENGKAP
        if not profile_data:
            self.current_mode = "setup_username"
            # Buat profil default di memori untuk diisi selama setup
            self.profile_data = self.profile_handler.get_default_profile()
            self.view.display_raw_text("Enter your username")
            return

        # Alur 2: Pengguna lama (profil.json ada) -> Lanjutkan dengan data yang ada
        self.profile_data = profile_data
        
        # Cek apakah token ada untuk sesi ini
        if not os.environ.get("REPLICATE_API_TOKEN"):
            # Jika tidak ada, minta token saja
            self.current_mode = "setup_token_only"
            self.view.display_raw_text("Enter your replicate token")
            hint_token = "Hint: Salin token dari halaman akun Replicate Anda. Token biasanya diawali dengan 'r8_...'"
            self.view.display_hint(hint_token)
        else:
            # Jika profil dan token ada, langsung inisialisasi
            self._initialize_api_from_profile()

    def _handle_command(self, command: str):
        if self.current_mode.startswith("setup"):
            self._handle_setup_command(command)
            return

        mode_handlers = {
            "ai_mode": self._handle_ai_subcommand,
            "save_confirmation": self._handle_save_confirmation,
            "save_filename": self._handle_save_filename,
            "unsetup": self._handle_unsetup_subcommand,
            "model_management": self._handle_model_management_subcommand,
        }
        handler = mode_handlers.get(self.current_mode, self._handle_default_command)
        handler(command)

    def _handle_model_management_subcommand(self, command: str):
        parts = command.strip().split(maxsplit=1)
        sub_cmd = parts[0].lower()

        if sub_cmd == '/list':
            models = self.profile_data.get("models", {})
            active_model = self.profile_data.get("active_model")
            output = "Available models:\n"
            for name, config in models.items():
                marker = "[ACTIVE]" if name == active_model else ""
                output += f" - {name} ({config['id']}) {marker}\n"
            self.view.display_output(output.strip())

        elif sub_cmd == '/set':
            if len(parts) < 2:
                self.view.display_output("Usage: /set <model_name>")
                return
            
            model_name = parts[1].strip()
            if model_name in self.profile_data.get("models", {}):
                self.profile_data['active_model'] = model_name
                self.profile_handler.write_profile(self.profile_data)
                self.view.display_output(f"Model changed to '{model_name}'. Re-initializing API...")
                self._initialize_api_from_profile()
            else:
                self.view.display_output(f"Error: Model '{model_name}' not found in configuration.")

        elif sub_cmd == '/exit':
            self.current_mode = "default"
            self.view.set_prompt_label(f"{self.view.username}> ")
            self.view.terminal._show_prompt()
        else:
            self.view.display_output(f"Unknown command in model management. Use /list, /set, or /exit.")

    def _handle_setup_command(self, command: str):
        try:
            if self.current_mode == "setup_username":
                # Saat setup baru, token pasti belum ada, jadi kita perlu memintanya
                self.profile_data['username'] = command.strip()
                self.current_mode = "setup_path"
                self.view.display_raw_text("Enter local storage path")
                hint_path = "Hint: Masukkan path lengkap ke folder. Gunakan tanda kutip jika ada spasi, contoh: \"D:\\File Proyek\""
                self.view.display_hint(hint_path)
            
            elif self.current_mode == "setup_path":
                path = command.strip().strip('"').replace('\\', '/')
                error_message = None
                if os.path.isdir(path): pass
                elif os.path.exists(path):
                    error_message = f"Path \"{path}\" points to a file, not a directory."
                else:
                    try: os.makedirs(path)
                    except OSError as e:
                        error_message = f"Could not create path. System error: {e}"
                
                if error_message:
                    self.view.display_output(error_message, show_prompt=False)
                    self.view.display_raw_text("Enter local storage path")
                    hint_path = "Hint: Masukkan path lengkap ke folder. Gunakan tanda kutip jika ada spasi, contoh: \"D:\\File Proyek\""
                    self.view.display_hint(hint_path)
                    return

                self.profile_data['save_path'] = path
                self.current_mode = "setup_token"
                self.view.display_raw_text("Enter your replicate token")
                hint_token = "Hint: Salin token dari halaman akun Replicate Anda. Token biasanya diawali dengan 'r8_...'"
                self.view.display_hint(hint_token)

            elif self.current_mode in ["setup_token", "setup_token_only"]:
                token = command.strip()
                if not token:
                    self.view.display_output("Token cannot be empty. Please try again.", show_prompt=False)
                    self.view.display_raw_text("Enter your replicate token")
                    hint_token = "Hint: Salin token dari halaman akun Replicate Anda. Token biasanya diawali dengan 'r8_...'"
                    self.view.display_hint(hint_token)
                    return
                
                os.environ['REPLICATE_API_TOKEN'] = token
                self._finalize_setup()

        except Exception as e:
            self.view.display_output(f"An error occurred during setup: {e}\nPlease restart the application.")

    def _finalize_setup(self):
        self.profile_handler.write_profile(self.profile_data)
        self.current_mode = "default"
        self._initialize_api_from_profile()
    
    def _format_ai_response(self, response: str) -> str:
        prefix = "ai_agent> "
        response_text = response[len(prefix):].strip() if response.startswith(prefix) else response
        parts = re.split(r'(```\w*\n.*?\n```)', response_text, flags=re.DOTALL)
        formatted_parts = []
        for part in filter(None, parts):
            part = part.strip()
            if not part: continue
            match = re.match(r'```(\w*)\n(.*?)\n```', part, flags=re.DOTALL)
            if match:
                language = (match.group(1) or "code").capitalize()
                code = html.escape(match.group(2).strip())
                header = f'<div style="background-color: #383e4a; padding: 5px 10px; border-top-left-radius: 5px; border-top-right-radius: 5px; color: #dcdcdc;">{language}</div>'
                body = f'<pre style="background-color: #2c313a; padding: 10px; border-bottom-left-radius: 5px; border-bottom-right-radius: 5px; margin: 0; white-space: pre-wrap; word-wrap: break-word; line-height: 1.0;">{code}</pre>'
                formatted_parts.append(f'<div>{header}{body}</div>')
            else:
                formatted_parts.append(f'<div>{html.escape(part).replace(chr(10), "<br>")}</div>')
        separator = f"<div>{'-' * 104}</div>"
        content = "<br>".join(formatted_parts)
        return f"{separator}<div>{prefix}{content}</div>{separator}"

    def _extract_code_and_docs(self, response: str) -> tuple[str, str, str]:
        match = re.search(r'```(\w*)?\s*\n(.*?)\s*```', response, re.DOTALL)
        clean_code = ""
        full_docs = response
        file_ext = ".txt"
        if match:
            language = (match.group(1) or "").lower()
            clean_code = match.group(2).strip()
            ext_map = {"python": ".py", "java": ".java", "javascript": ".js", "html": ".html", "css": ".css", "cpp": ".cpp"}
            file_ext = ext_map.get(language, ".txt")
            full_docs = re.sub(r'```\w*\s*\n.*?\s*```', f"\n[See code in {file_ext} file]\n", response, flags=re.DOTALL)
        return clean_code, full_docs, file_ext

    def _handle_ai_subcommand(self, command: str):
        if not self.granite_api:
            self.view.display_output("AI API is not initialized. Please check your token and restart.")
            return

        parts = command.strip().split(maxsplit=1)
        sub_cmd = parts[0].lower()

        if sub_cmd == '/exit':
            self.current_mode = "default"
            self.view.set_prompt_label(f"{self.view.username}> ")
            self.view.display_output("AI mode has been disabled.")
        elif sub_cmd == '/path': pass
        elif sub_cmd.startswith('/'):
            self.view.display_output(f"You are already in AI mode and the {sub_cmd} command is not available in this mode.")
        else:
            raw_response = self.granite_api.send_prompt(command)
            formatted_response = self._format_ai_response(raw_response)
            self.last_ai_response = raw_response
            self.last_code_block, _, _ = self._extract_code_and_docs(raw_response)
            self.view.display_output(formatted_response, is_html=True, show_prompt=False)
            if self.last_code_block:
                self.current_mode = "save_confirmation"
                self.view.set_prompt_label("Do you want to save the code above? (y/n)> ")
            else:
                self.view.set_prompt_label(f"{self.view.username}/mode_ai> ")
            self.view.terminal._show_prompt()

    def _handle_save_confirmation(self, command: str):
        answer = command.lower()
        if answer == 'y':
            self.current_mode = "save_filename"
            self.view.set_prompt_label("Enter the name of the file you want to save?> ")
            self.view.terminal._show_prompt()
        elif answer == 'n':
            self.current_mode = "ai_mode"
            self.view.set_prompt_label(f"{self.view.username}/mode_ai> ")
            self.view.terminal._show_prompt()
        else:
            self.view.display_output("Invalid input. Please enter 'y' or 'n'.", show_prompt=False)
            self.view.set_prompt_label("Do you want to save the code above? (y/n)> ")
            self.view.terminal._show_prompt()

    def _handle_save_filename(self, command: str):
        filename_base = command.strip()
        clean_code, docs, file_ext = self._extract_code_and_docs(self.last_ai_response)
        code_path = os.path.join(self.save_path, filename_base + file_ext)
        doc_path = os.path.join(self.save_path, filename_base + ".md")
        code_saved = self.profile_handler.write_file(code_path, clean_code)
        doc_saved = self.profile_handler.write_file(doc_path, docs)
        self.current_mode = "ai_mode"
        self.view.set_prompt_label(f"{self.view.username}/mode_ai> ")
        if code_saved and doc_saved:
            self.view.display_output(f"Code saved to: {code_path}\nDocumentation saved to: {doc_path}")
        else:
            self.view.display_output("An error occurred while saving the files.")

    def _handle_unsetup_subcommand(self, command: str):
        parts = command.strip().split(maxsplit=1)
        sub_cmd = parts[0].lower()
        
        if sub_cmd == '/rename_user':
            if len(parts) > 1:
                new_name = parts[1].strip('"')
                self.profile_data['username'] = new_name
                if self.profile_handler.write_profile(self.profile_data):
                    self.view.update_username_and_prompt(new_name)
                    self.current_mode = "default"
                    self.view.display_output(f"The username has been successfully changed to '{new_name}'.")
                else:
                    self.view.display_output("Failed to save new username.")
            else:
                self.view.display_output("Usage: /rename_user \"new_name\"")

        elif sub_cmd == '/delete':
            self._delete_profile()
        elif sub_cmd == '/change_path':
            if len(parts) > 1:
                new_path = parts[1].strip('"')
                if os.path.isdir(new_path):
                    self.save_path = new_path
                    self.profile_data["save_path"] = new_path
                    self.profile_handler.write_profile(self.profile_data)
                    self.view.display_output(f"Save path updated to: {new_path}")
                else:
                    self.view.display_output("Error: The provided path is not a valid directory.")
            else:
                self.view.display_output(f"Current save path: {self.save_path}\nUsage: /file_save_path \"new_path\"")
        elif sub_cmd == '/exit':
            self.current_mode = "default"
            self.view.set_prompt_label(f"{self.view.username}> ")
            self.view.terminal._show_prompt()
        else:
            self.view.display_output(f"Unrecognized subcommand")

    def _delete_profile(self):
        if self.profile_handler.delete_profile():
            self.view.display_output("Profile data successfully deleted. Please restart the application.")
        else:
            self.view.display_output("Failed to delete profile data.")

    def _handle_default_command(self, command: str):
        cmd_lower = command.lower()
        if cmd_lower.startswith('/'):
            if cmd_lower == '/clear': self.view.clear_screen()
            elif cmd_lower == '/help':
                help_text = (
                    "/model, used to manage AI models (/list, /set <name>)\n"
                    "/unsetup_profil, used to modify the terminal profile globally\n"
                    " |_ /rename_user \"new_name\", used to modify the user profile name\n"
                    " |_ /change_path \"new_path\", used to change the local save path\n"
                    " |_ /delete, To delete existing profile data\n"
                    " |_ /exit, Used to exit the settings mode\n"
                    "/clear, Used to clean terminals\n"
                    "/activate_ai, Used to activate ai mode\n"
                )
                self.view.display_output(help_text)
            elif cmd_lower == '/model':
                self.current_mode = "model_management"
                self.view.set_prompt_label(f"{self.view.username}/model> ")
                self.view.display_output("Entered model management mode. Use /list, /set <name>, or /exit.")
            elif cmd_lower == '/unsetup_profil':
                self.current_mode = "unsetup"
                self.view.set_prompt_label(f"{self.view.username}/unsetup_profil> ")
                self.view.terminal._show_prompt()
            elif cmd_lower == '/activate_ai':
                if not self.granite_api:
                    self.view.display_output("AI API is not initialized. Please check your token and restart.")
                    return
                self.current_mode = "ai_mode"
                self.view.set_prompt_label(f"{self.view.username}/mode_ai> ")
                self.view.display_output("AI mode is enabled, use ‘/exit’ to return to basic mode.")
            else:
                if cmd_lower not in ['/clear', '/help', '/unsetup_profil', '/activate_ai', '/model']:
                    self.view.display_output(f"Existing commands: '{command}' not recognized by the terminal")
        else:
            if self.granite_api:
                self.view.display_output("AI mode is inactive, use ‘/activate_ai’ to start.")
            else:
                self.view.display_output("AI API is not initialized. Please check your token and restart.")

if __name__ == '__main__':
    controller = Controller()
    controller.run()