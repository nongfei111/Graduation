import os
from config.settings import Config


LOCK_FILE = os.path.join(Config.DATA_DIR, 'lockdown.flag')


def is_locked() -> bool:
    return os.path.exists(LOCK_FILE)


def lock(reason: str = '') -> None:
    os.makedirs(Config.DATA_DIR, exist_ok=True)
    with open(LOCK_FILE, 'w', encoding='utf-8') as f:
        f.write(reason or 'locked')


def unlock() -> None:
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        return
