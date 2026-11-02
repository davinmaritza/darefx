import logging
import os
import sys

# Unbuffer stdout so Pterodactyl console streams in real time
sys.stdout.reconfigure(line_buffering=True)

# Ensure src is in python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from darefx.notifications.telegram_server import TelegramServer

if __name__ == "__main__":
    print("==================================================", flush=True)
    print("  🚀 DareFX Aegis-Alpha (v2.1) Institutional Engine 🚀", flush=True)
    print("  ⚡ Powered by ByteNodes High-Performance Hosting ⚡", flush=True)
    print("==================================================", flush=True)
    server = TelegramServer()
    server.start_polling()
