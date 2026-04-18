import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = os.environ["TOKEN_ENCRYPTION_KEY"]
        _fernet = Fernet(key.encode())
    return _fernet


def encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    return _get_fernet().decrypt(encrypted.encode()).decode()
