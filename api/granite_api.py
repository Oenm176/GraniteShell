# granite_shell/api/granite_api.py

import os
import replicate
from PyQt6.QtCore import QObject, pyqtSignal

class ApiWorker(QObject):
    finished = pyqtSignal(str)  # Sinyal saat berhasil, membawa hasil (string)
    error = pyqtSignal(str)     # Sinyal saat gagal, membawa pesan error (string)

    def __init__(self, api_client, prompt):
        super().__init__()
        self.api_client = api_client
        self.prompt = prompt

    def run(self):
        """Metode ini akan dijalankan di thread terpisah."""
        try:
            result = self.api_client.send_prompt(self.prompt)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class GraniteAPI:
    """
    Kelas untuk mengelola interaksi dengan Replicate API secara dinamis.
    """
    def __init__(self, model_config: dict):
        """
        PERUBAHAN: Inisialisasi dengan konfigurasi model yang spesifik.
        Contoh model_config: {"id": "ibm-granite/...", "input_key": "prompt"}
        """
        if not os.environ.get("REPLICATE_API_TOKEN"):
            raise ValueError("Silakan atur environment variable REPLICATE_API_TOKEN.")
        
        self.model_id = model_config.get("id")
        self.input_key = model_config.get("input_key", "prompt") # Default ke "prompt"

        if not self.model_id:
            raise ValueError("Model configuration is missing the 'id' field.")
            
        self.file_context = None

    def set_file_context(self, content: str):
        self.file_context = content

    def send_prompt(self, user_prompt: str) -> str:
        final_prompt = user_prompt
        if self.file_context:
            final_prompt = f"Berdasarkan konten file berikut:\n\n---\n{self.file_context}\n---\n\nSekarang, tolong lakukan hal berikut: {user_prompt}"
            self.file_context = None

        try:
            # PERUBAHAN: Gunakan input_key yang dinamis dari konfigurasi
            model_input = {self.input_key: final_prompt}

            output = replicate.run(
                self.model_id,
                input=model_input
            )
            
            generated_text = "".join(output)
            return f"ai_agent> {generated_text.strip()}"

        except Exception as e:
            # Memberikan pesan error yang lebih informatif
            error_message = str(e)
            return f"Error communicating with Replicate API. The model may be incompatible or another issue occurred. \nDetails: {error_message}"