import os
import requests
from dotenv import load_dotenv

load_dotenv()

def send_telegram_message(message: str) -> bool:
    """
    Send a text message through Telegram.
    """
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if dry_run:
        print("\n================================")
        print("      TELEGRAM DRY RUN")
        print("================================")
        print(f"Would send to chat ID: {chat_id}")
        print(message)
        print("================================\n")
        return True

    if not bot_token or not chat_id:
        print("[TELEGRAM ERROR] Bot token or chat ID is missing.")
        return False

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        r = requests.post(url, data={"chat_id": chat_id, "text": message})
        if r.status_code == 200:
            print("[TELEGRAM] Message sent successfully.")
            return True
        else:
            print(f"[TELEGRAM ERROR] {r.text}")
            return False
    except Exception as e:
        print(f"[TELEGRAM ERROR] {e}")
        return False


def send_telegram_photo(photo_path: str, caption: str = "") -> bool:
    """
    Send a photo through Telegram.
    """
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if dry_run:
        print("\n================================")
        print("   TELEGRAM PHOTO DRY RUN")
        print("================================")
        print(f"Would send photo to chat ID: {chat_id}")
        print(f"Photo: {photo_path}")
        print("Caption:", caption)
        print("================================\n")
        return True

    if not bot_token or not chat_id:
        print("[TELEGRAM PHOTO ERROR] Bot token or chat ID is missing.")
        return False

    if not os.path.exists(photo_path):
        print(f"[TELEGRAM PHOTO ERROR] Photo not found: {photo_path}")
        return False

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        with open(photo_path, "rb") as photo:
            r = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption},
                files={"photo": photo}
            )
        if r.status_code == 200:
            print("[TELEGRAM] Photo sent successfully.")
            return True
        else:
            print(f"[TELEGRAM PHOTO ERROR] {r.text}")
            return False
    except Exception as e:
        print(f"[TELEGRAM PHOTO ERROR] {e}")
        return False
