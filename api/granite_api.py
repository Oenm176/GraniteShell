# granite_shell/api/granite_api.py

import os
import replicate
from PyQt6.QtCore import QObject, pyqtSignal

class ApiWorker(QObject):
    """
    A worker object that runs in a separate thread to prevent the GUI from freezing
    during a long-running API call. It communicates its results via signals.
    """
    finished = pyqtSignal(str)  # Signal emitted on success, carrying the string result.
    error = pyqtSignal(str)     # Signal emitted on failure, carrying the string error message.

    def __init__(self, api_client, prompt):
        """ Class constructor. """
        super().__init__()
        self.api_client = api_client
        self.prompt = prompt

    def run(self):
        """ This method will be executed in the separate thread. """
        try:
            # Perform the API call.
            result = self.api_client.send_prompt(self.prompt)
            # Emit the 'finished' signal with the result.
            self.finished.emit(result)
        except Exception as e:
            # If any exception occurs, emit the 'error' signal.
            self.error.emit(str(e))

class GraniteAPI:
    """
    A class to dynamically manage interactions with the Replicate API.
    """
    def __init__(self, model_config: dict):
        """
        MODIFIED: Initializes with a specific model configuration.
        Example model_config: {"id": "ibm-granite/...", "input_key": "prompt"}
        """
        # Check if the required API token is set as an environment variable.
        if not os.environ.get("REPLICATE_API_TOKEN"):
            raise ValueError("Please set the REPLICATE_API_TOKEN environment variable.")
        
        # Get the model ID from the configuration.
        self.model_id = model_config.get("id")
        # Get the specific input key for the model, defaulting to "prompt".
        self.input_key = model_config.get("input_key", "prompt")

        # The model ID is essential, so raise an error if it's missing.
        if not self.model_id:
            raise ValueError("Model configuration is missing the 'id' field.")
            
        # A variable to hold the content of a file, if provided as context.
        self.file_context = None

    def set_file_context(self, content: str):
        """ Stores file content to be used as context for the next prompt. """
        self.file_context = content

    def send_prompt(self, user_prompt: str) -> str:
        """
        Sends a prompt to the configured Replicate model and returns the response.
        """
        final_prompt = user_prompt
        # If file context has been set, prepend it to the user's prompt.
        if self.file_context:
            final_prompt = f"Based on the following file content:\n\n---\n{self.file_context}\n---\n\nNow, please do the following: {user_prompt}"
            # Clear the context after using it once.
            self.file_context = None

        try:
            # MODIFIED: Use the dynamic input_key from the configuration.
            # This creates a dictionary like {"prompt": "user's prompt here"}.
            model_input = {self.input_key: final_prompt}

            # Run the model on Replicate's servers.
            output = replicate.run(
                self.model_id,
                input=model_input
            )
            
            # The output is an iterator; join its parts to form the final string.
            generated_text = "".join(output)
            # Prepend a prefix to identify the response as coming from the AI agent.
            return f"ai_agent> {generated_text.strip()}"

        except Exception as e:
            # Provide a more informative error message if the API call fails.
            error_message = str(e)
            return f"Error communicating with Replicate API. The model may be incompatible or another issue occurred. \nDetails: {error_message}"