# granite_shell/utils/file_handler.py

import os
import json

class ProfileHandler:
    """
    Kelas untuk mengelola semua operasi file terkait profil pengguna.
    Membaca, menulis, dan menghapus file profil.json.
    """
    def __init__(self, file_path: str):
        """
        Inisialisasi handler dengan path ke file profil.
        """
        self.file_path = file_path
        # Pastikan direktori untuk file profil ada
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    def get_default_profile(self) -> dict:
        """
        DITAMBAHKAN: Mengembalikan struktur data profil default.
        Ini akan digunakan saat profil baru dibuat.
        """
        return {
            "username": "anonymous",
            "save_path": os.getcwd(),
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
        Membaca file profil dan mengembalikan isinya sebagai dictionary.
        Mengembalikan None jika file tidak ada atau terjadi error.
        """
        if not os.path.exists(self.file_path):
            return None
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def write_profile(self, data: dict) -> bool:
        """
        Menulis dictionary data ke file profil.
        Mengembalikan True jika berhasil, False jika gagal.
        """
        try:
            with open(self.file_path, 'w') as f:
                json.dump(data, f, indent=4)
            return True
        except IOError:
            return False

    def delete_profile(self) -> bool:
        """
        Menghapus file profil.
        Mengembalikan True jika berhasil atau file sudah tidak ada.
        """
        if os.path.exists(self.file_path):
            try:
                os.remove(self.file_path)
                return True
            except OSError:
                return False
        return True # File sudah tidak ada, dianggap berhasil
    
    def write_file(self, full_path: str, content: str) -> bool:
        """
        Metode generik untuk menulis konten ke file.
        Membuat direktori jika belum ada.
        """
        try:
            # Pastikan direktori tujuan ada
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except IOError as e:
            print(f"Error writing file {full_path}: {e}")
            return False
