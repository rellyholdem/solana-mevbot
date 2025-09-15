import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# VseGPT
VSEGPT_API_KEY = os.getenv("VSEGPT_API_KEY", "")
VSEGPT_BASE_URL = os.getenv("VSEGPT_BASE_URL", "https://api.vsegpt.ru/v1")
VSEGPT_CHAT_MODEL = os.getenv("VSEGPT_CHAT_MODEL", "openai/gpt-5-chat")
VSEGPT_STT_MODEL = os.getenv("VSEGPT_STT_MODEL", "stt-openai/gpt-4o-transcribe")
BOT_TITLE = os.getenv("BOT_TITLE", "MIREA Bot EOSO-01-25")

# NextCloud
NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL", "")
NEXTCLOUD_USERNAME = os.getenv("NEXTCLOUD_USERNAME", "")
NEXTCLOUD_PASSWORD = os.getenv("NEXTCLOUD_PASSWORD", "")

# SSH (optional admin)
SSH_HOST = os.getenv("SSH_HOST", "")
SSH_USER = os.getenv("SSH_USER", "")
SSH_PASSWORD = os.getenv("SSH_PASSWORD", "")

DISCIPLINES = [
    "Введение в профессиональную деятельность",
    "Иностранный язык",
    "Информатика",
    "История России",
    "Линейная алгебра и аналитическая геометрия",
    "Математический анализ",
    "Начертательная геометрия, инженерная и компьютерная графика",
    "Основы российской государственности",
    "Русский язык и культура речи",
    "Современные оптические и оптико-электронные приборы и лазерные технологии",
    "Физика",
    "Физическая культура и спорт",
    "Химия",
]

# Bot constants
ROOT_FOLDER = "Лекции"
CONSPECTS_FOLDER = "Конспекты"
MESSAGE_THROTTLE_SECONDS = 2
MAX_AUDIO_BYTES = 100 * 1024 * 1024
MAX_DOC_BYTES = 50 * 1024 * 1024
ALLOWED_AUDIO_EXT = {"mp3", "m4a", "wav", "ogg"}
TEMP_DIR = "/tmp/mirea-bot"

# Optional targeting and admin
TARGET_GROUP_CHAT_ID = int(os.getenv("TARGET_GROUP_CHAT_ID", "0")) or None
ADMIN_USER_IDS = [
    int(x) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip().isdigit()
]

os.makedirs(TEMP_DIR, exist_ok=True)
