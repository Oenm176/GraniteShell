# granite_shell/utils/file_handler.py

import os
import json

class ProfileHandler:
    """
    A class to manage all file operations related to the user profile.
    It handles reading, writing, and deleting the profile.json file.
    """
    def __init__(self, file_path: str):
        """
        Initializes the handler with the path to the profile file.
        """
        self.file_path = file_path
        # Ensure the directory for the profile file exists.
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    def get_default_profile(self) -> dict:
        """
        ADDED: Returns the default profile data structure.
        This is used when a new profile is being created.
        """
        return {
            "username": "anonymous",
            "save_path": os.getcwd(), # Defaults to the current working directory.
            "active_model": "ibm-granite",
            "models": {
                "ibm-granite": {
                    "id": "ibm-granite/granite-3.3-8b-instruct",
                    "input_key": "prompt"
                }
            }
        }

    def read_profile(self) -> dict | None:
        """
        Reads the profile file and returns its content as a dictionary.
        Returns None if the file doesn't exist or if an error occurs.
        """
        if not os.path.exists(self.file_path):
            return None
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # Handles cases where the file is corrupted or unreadable.
            return None

    def write_profile(self, data: dict) -> bool:
        """
        Writes a data dictionary to the profile file in JSON format.
        Returns True on success, False on failure.
        """
        try:
            with open(self.file_path, 'w') as f:
                # `indent=4` makes the JSON file human-readable.
                json.dump(data, f, indent=4)
            return True
        except IOError:
            return False

    def delete_profile(self) -> bool:
        """
        Deletes the profile file from the filesystem.
        Returns True if successful or if the file was already gone.
        """
        if os.path.exists(self.file_path):
            try:
                os.remove(self.file_path)
                return True
            except OSError:
                # This could happen due to permission issues.
                return False
        return True # If file doesn't exist, consider it a success.
    
    def write_file(self, full_path: str, content: str) -> bool:
        """
        A generic method to write any string content to a specified file.
        It creates the necessary directories if they don't already exist.
        """
        try:
            # Ensure the target directory exists before writing.
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            # `encoding='utf-8'` is best practice for handling all characters.
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except IOError as e:
            # Print an error to the console for debugging purposes.
            print(f"Error writing file {full_path}: {e}")
            return False