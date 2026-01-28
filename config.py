import os

# 🔒 SECURE: Get token from environment variables, NOT hardcoded
BOT_TOKEN = os.environ.get('BOT_TOKEN')  # Will be set in Heroku

# Admin IDs (comma separated in Heroku config)
admin_ids_str = os.environ.get('ADMIN_IDS', '')
ADMIN_IDS = []
if admin_ids_str:
    for id_str in admin_ids_str.split(','):
        id_str = id_str.strip()
        if id_str:
            try:
                ADMIN_IDS.append(int(id_str))
            except ValueError:
                pass

COUNTRIES = {
    "BD": {
        "name": "Bangladesh",
        "flag": "🇧🇬",
        "manager": "@SupportManager_BD",
        "commission": "20–30%",
        "language": "Русский"
    },
    "PK": {
        "name": "Pakistan",
        "flag": "🇵🇰", 
        "manager": "@SupportManager_PK",
        "commission": "20–30%",
        "language": "English"
    },
    "IN": {
        "name": "India",
        "flag": "🇮🇳",
        "manager": "@SupportManager_IN",
        "commission": "15–25%",
        "language": "English"
    },
    "RU": {
        "name": "Russia",
        "flag": "🇷🇺",
        "manager": "@SupportManager_RU",
        "commission": "25–35%",
        "language": "Русский"
    }
}
