# granite_shell/main.py

# --- Standard & Third-Party Imports ---
import sys  # For system interaction, like command-line arguments and exiting the app.
import os   # For operating system interaction, like file paths.
import re   # For Regular Expression operations, used when formatting text.
import html # For escaping special HTML characters (e.g., '<' to '&lt;').

# --- Local Imports from Your Project ---
from PyQt6.QtWidgets import QApplication           # The main framework for the GUI (Graphical User Interface).
from ui.main_window import MainWindow              # Your custom main window class.
from utils.file_handler import ProfileHandler      # A class to handle reading/writing the profile file.
from api.granite_api import GraniteAPI             # A class for interacting with the AI API.

# ===================================================================
# Controller Class (The Brain of the Application)
# ===================================================================
# This class acts as a "bridge" connecting the user interface (View)
# with the application logic and data (Model).
class Controller:
    # Defines the location of the profile file as a constant.
    PROFILE_FILE = os.path.join('data', 'profil.json')

    def __init__(self):
        """
        Class constructor. Called when a Controller object is created.
        Initializes all major components of the application.
        """
        # Initialize the PyQt6 application.
        self.app = QApplication(sys.argv)
        # Create a ProfileHandler instance to manage the profile.json file.
        self.profile_handler = ProfileHandler(self.PROFILE_FILE)
        # Create a MainWindow instance as the main application view.
        self.view = MainWindow()
        # Connect a "signal" from the view to a "slot" (method) in the controller.
        # When a command is submitted in the view, the _handle_command method is called.
        self.view.command_submitted.connect(self._handle_command)
        
        # Initialize application state variables.
        self.granite_api = None     # API object, initially None until the profile is loaded.
        self.profile_data = {}      # User profile data, loaded from the file.
        self.current_mode = "default" # The current terminal mode (default, setup, ai_mode, etc.).

    def run(self):
        """
        The main method to run the application.
        """
        self.view.show()  # Display the main window.
        self._setup_user_profile() # Start the user profile setup process.
        sys.exit(self.app.exec()) # Start the application's event loop and exit when closed.

    def _initialize_api_from_profile(self):
        """
        Initializes or re-initializes the GraniteAPI based on the profile data.
        This is called after a profile is successfully loaded or modified.
        """
        try:
            # Get the active AI model name, defaulting to "ibm-granite".
            active_model_name = self.profile_data.get("active_model", "ibm-granite")
            # Get the configuration (model ID) for the active model.
            model_config = self.profile_data.get("models", {}).get(active_model_name)
            
            # If the configuration for the active model isn't found, raise an error.
            if not model_config:
                raise ValueError(f"Configuration for active model '{active_model_name}' not found.")

            # Create a new instance of the GraniteAPI with the correct configuration.
            self.granite_api = GraniteAPI(model_config)
            # Set the save path and username from the profile.
            self.save_path = self.profile_data.get("save_path", os.getcwd())
            self.view.username = self.profile_data.get("username", "anonymous")
            
            # Update the username and model name display in the terminal prompt.
            self.view.set_username(self.view.username, active_model_name)

        except ValueError as e:
            # Handle errors if API initialization fails.
            self.view.display_output(f"API Initialization Error: {e}\nPlease check your profile or token.")
            self.granite_api = None # Set API to None so it can't be used.

    def _setup_user_profile(self):
        """
        Handles the workflow for setting up the user profile on first run
        or when the API token is not set.
        """
        profile_data = self.profile_handler.read_profile()

        # Flow 1: If profile.json doesn't exist (new user).
        if not profile_data:
            self.current_mode = "setup_username" # Enter username setup mode.
            self.profile_data = self.profile_handler.get_default_profile() # Create a temporary default profile.
            self.view.display_raw_text("Enter your username")
            return

        # Flow 2: If profile.json exists (returning user).
        self.profile_data = profile_data
        
        # Check if the Replicate API token is set as an environment variable.
        if not os.environ.get("REPLICATE_API_TOKEN"):
            # If not, enter a mode to ask for the token only.
            self.current_mode = "setup_token_only"
            self.view.display_raw_text("Enter your replicate token")
            hint_token = "Hint: Copy the token from your Replicate account page. It usually starts with 'r8_...'"
            self.view.display_hint(hint_token)
        else:
            # If profile and token exist, initialize the API immediately.
            self._initialize_api_from_profile()

    def _handle_command(self, command: str):
        """
        The main "router" function. It receives all user input and directs it
        to the appropriate handler based on the current mode.
        """
        # If in a setup mode, all commands are handled by the setup function.
        if self.current_mode.startswith("setup"):
            self._handle_setup_command(command)
            return

        # A dictionary that maps the current mode to its handler function.
        mode_handlers = {
            "ai_mode": self._handle_ai_subcommand,
            "save_confirmation": self._handle_save_confirmation,
            "save_filename": self._handle_save_filename,
            "unsetup": self._handle_unsetup_subcommand,
            "model_management": self._handle_model_management_subcommand,
        }
        # Get the appropriate handler from the dictionary. If none, use the default handler.
        handler = mode_handlers.get(self.current_mode, self._handle_default_command)
        # Execute the chosen handler function with the user's command.
        handler(command)

    def _handle_model_management_subcommand(self, command: str):
        """Handles sub-commands when in AI model management mode."""
        parts = command.strip().split(maxsplit=1)
        sub_cmd = parts[0].lower()

        if sub_cmd == '/list':
            # Display all available models and mark the active one.
            models = self.profile_data.get("models", {})
            active_model = self.profile_data.get("active_model")
            output = "Available models:\n"
            for name, config in models.items():
                marker = "[ACTIVE]" if name == active_model else ""
                output += f" - {name} ({config['id']}) {marker}\n"
            self.view.display_output(output.strip())

        elif sub_cmd == '/set':
            # Set the active AI model.
            if len(parts) < 2:
                self.view.display_output("Usage: /set <model_name>")
                return
            
            model_name = parts[1].strip()
            if model_name in self.profile_data.get("models", {}):
                self.profile_data['active_model'] = model_name
                self.profile_handler.write_profile(self.profile_data)
                self.view.display_output(f"Model changed to '{model_name}'. Re-initializing API...")
                self._initialize_api_from_profile() # Re-initialize the API with the new model.
            else:
                self.view.display_output(f"Error: Model '{model_name}' not found in configuration.")

        elif sub_cmd == '/exit':
            # Exit the model management mode.
            self.current_mode = "default"
            self.view.set_prompt_label(f"{self.view.username}> ")
            self.view.terminal._show_prompt()
        else:
            self.view.display_output(f"Unknown command in model management. Use /list, /set, or /exit.")

    def _handle_setup_command(self, command: str):
        """Handles user input during the initial setup workflow."""
        try:
            if self.current_mode == "setup_username":
                # Step 1: Save username, then ask for path.
                self.profile_data['username'] = command.strip()
                self.current_mode = "setup_path"
                self.view.display_raw_text("Enter local storage path")
                hint_path = "Hint: Enter the full path to the folder. Use quotes if there are spaces, e.g., \"D:\\Project Files\""
                self.view.display_hint(hint_path)
            
            elif self.current_mode == "setup_path":
                # Step 2: Validate the path. If valid, save and ask for token.
                path = command.strip().strip('"').replace('\\', '/')
                error_message = None
                if os.path.isdir(path): pass # Path exists and is a directory.
                elif os.path.exists(path):
                    error_message = f"Path \"{path}\" points to a file, not a directory."
                else:
                    try: 
                        os.makedirs(path) # Try to create the directory if it doesn't exist.
                    except OSError as e:
                        error_message = f"Could not create path. System error: {e}"
                
                if error_message:
                    # If there's an error, display it and re-prompt for the path.
                    self.view.display_output(error_message, show_prompt=False)
                    self.view.display_raw_text("Enter local storage path")
                    hint_path = "Hint: Enter the full path to the folder. Use quotes if there are spaces, e.g., \"D:\\Project Files\""
                    self.view.display_hint(hint_path)
                    return

                self.profile_data['save_path'] = path
                self.current_mode = "setup_token"
                self.view.display_raw_text("Enter your replicate token")
                hint_token = "Hint: Copy the token from your Replicate account page. It usually starts with 'r8_...'"
                self.view.display_hint(hint_token)

            elif self.current_mode in ["setup_token", "setup_token_only"]:
                # Step 3: Save the token and finalize the setup.
                token = command.strip()
                if not token:
                    # Validate that the token is not empty.
                    self.view.display_output("Token cannot be empty. Please try again.", show_prompt=False)
                    self.view.display_raw_text("Enter your replicate token")
                    hint_token = "Hint: Copy the token from your Replicate account page. It usually starts with 'r8_...'"
                    self.view.display_hint(hint_token)
                    return
                
                # Set the token as an environment variable for the current session.
                os.environ['REPLICATE_API_TOKEN'] = token
                self._finalize_setup()

        except Exception as e:
            self.view.display_output(f"An error occurred during setup: {e}\nPlease restart the application.")

    def _finalize_setup(self):
        """Finalizes the setup process by writing the profile to file and initializing the API."""
        self.profile_handler.write_profile(self.profile_data)
        self.current_mode = "default"
        self._initialize_api_from_profile()
    
    def _format_ai_response(self, response: str) -> str:
        """
        Formats the raw response from the AI into rich HTML.
        This function specifically looks for code blocks and wraps them in custom styling.
        """
        prefix = "ai_agent> "
        response_text = response[len(prefix):].strip() if response.startswith(prefix) else response
        # Split the text by code blocks (```...```) using regex.
        parts = re.split(r'(```\w*\n.*?\n```)', response_text, flags=re.DOTALL)
        formatted_parts = []
        for part in filter(None, parts):
            part = part.strip()
            if not part: continue
            match = re.match(r'```(\w*)\n(.*?)\n```', part, flags=re.DOTALL)
            if match:
                # If the part is a code block, format it with custom styles.
                language = (match.group(1) or "code").capitalize()
                code = html.escape(match.group(2).strip())
                # Create a header for the code block (displays the language name).
                header = f'<div style="background-color: #383e4a; padding: 5px 10px; border-top-left-radius: 5px; border-top-right-radius: 5px; color: #dcdcdc;">{language}</div>'
                # Create the body for the code block.
                body = f'<pre style="background-color: #2c313a; padding: 10px; border-bottom-left-radius: 5px; border-bottom-right-radius: 5px; margin: 0; white-space: pre-wrap; word-wrap: break-word; line-height: 1.0;">{code}</pre>'
                formatted_parts.append(f'<div>{header}{body}</div>')
            else:
                # If the part is plain text, convert it to basic HTML.
                formatted_parts.append(f'<div>{html.escape(part).replace(chr(10), "<br>")}</div>')
        # Join all the formatted parts back together.
        separator = f"<div>{'-' * 104}</div>"
        content = "<br>".join(formatted_parts)
        return f"{separator}<div>{prefix}{content}</div>{separator}"

    def _extract_code_and_docs(self, response: str) -> tuple[str, str, str]:
        """Extracts the first code block from the AI response and separates it from the documentation."""
        # Find the first code block using regex.
        match = re.search(r'```(\w*)?\s*\n(.*?)\s*```', response, re.DOTALL)
        clean_code = ""
        full_docs = response
        file_ext = ".txt" # Default file extension.
        if match:
            # If a code block is found...
            language = (match.group(1) or "").lower()
            clean_code = match.group(2).strip() # Get the clean code.
            # Determine the file extension based on the detected language.
            ext_map = {"python": ".py", "java": ".java", "javascript": ".js", "html": ".html", "css": ".css", "cpp": ".cpp"}
            file_ext = ext_map.get(language, ".txt")
            # Replace the code block in the documentation with a placeholder.
            full_docs = re.sub(r'```\w*\s*\n.*?\s*```', f"\n[See code in {file_ext} file]\n", response, flags=re.DOTALL)
        return clean_code, full_docs, file_ext

    def _handle_ai_subcommand(self, command: str):
        """Handles user input when in AI mode."""
        if not self.granite_api:
            self.view.display_output("AI API is not initialized. Please check your token and restart.")
            return

        parts = command.strip().split(maxsplit=1)
        sub_cmd = parts[0].lower()

        if sub_cmd == '/exit':
            # Exit AI mode and return to the default mode.
            self.current_mode = "default"
            self.view.set_prompt_label(f"{self.view.username}> ")
            self.view.display_output("AI mode has been disabled.")
        elif sub_cmd == '/path': pass # This command might not be implemented yet.
        elif sub_cmd.startswith('/'):
            self.view.display_output(f"You are already in AI mode and the {sub_cmd} command is not available in this mode.")
        else:
            # If it's not an internal command, send it as a prompt to the AI.
            raw_response = self.granite_api.send_prompt(command)
            formatted_response = self._format_ai_response(raw_response)
            self.last_ai_response = raw_response
            # Extract code from the response for potential saving.
            self.last_code_block, _, _ = self._extract_code_and_docs(raw_response)
            # Display the formatted AI response as HTML.
            self.view.display_output(formatted_response, is_html=True, show_prompt=False)
            
            # If the response contains a code block, ask the user if they want to save it.
            if self.last_code_block:
                self.current_mode = "save_confirmation"
                self.view.set_prompt_label("Do you want to save the code above? (y/n)> ")
            else:
                self.view.set_prompt_label(f"{self.view.username}/mode_ai> ")
            self.view.terminal._show_prompt()

    def _handle_save_confirmation(self, command: str):
        """Handles the 'y' or 'n' confirmation for saving code."""
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
        """Handles the filename input and saves the code and documentation."""
        filename_base = command.strip()
        clean_code, docs, file_ext = self._extract_code_and_docs(self.last_ai_response)
        
        # Create the full paths for the code and documentation files.
        code_path = os.path.join(self.save_path, filename_base + file_ext)
        doc_path = os.path.join(self.save_path, filename_base + ".md")
        
        # Write to the files.
        code_saved = self.profile_handler.write_file(code_path, clean_code)
        doc_saved = self.profile_handler.write_file(doc_path, docs)
        
        # Return to AI mode.
        self.current_mode = "ai_mode"
        self.view.set_prompt_label(f"{self.view.username}/mode_ai> ")
        if code_saved and doc_saved:
            self.view.display_output(f"Code saved to: {code_path}\nDocumentation saved to: {doc_path}")
        else:
            self.view.display_output("An error occurred while saving the files.")

    def _handle_unsetup_subcommand(self, command: str):
        """Handles sub-commands for modifying an existing profile."""
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
        """Deletes the profile.json file."""
        if self.profile_handler.delete_profile():
            self.view.display_output("Profile data successfully deleted. Please restart the application.")
        else:
            self.view.display_output("Failed to delete profile data.")

    def _handle_default_command(self, command: str):
        """Handles all commands when in the default mode (not AI or setup)."""
        cmd_lower = command.lower()
        if cmd_lower.startswith('/'):
            # Handle internal commands like /clear, /help, etc.
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
                # If the command starts with '/' but is not recognized.
                if cmd_lower not in ['/clear', '/help', '/unsetup_profil', '/activate_ai', '/model']:
                    self.view.display_output(f"Existing commands: '{command}' not recognized by the terminal")
        else:
            # If the input is not a command, display a help message.
            if self.granite_api:
                self.view.display_output("AI mode is inactive, use ‘/activate_ai’ to start.")
            else:
                self.view.display_output("AI API is not initialized. Please check your token and restart.")

# Main entry point of the application.
if __name__ == '__main__':
    # Create a Controller instance and run the application.
    controller = Controller()
    controller.run()