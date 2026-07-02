import os
from pymongo import MongoClient
from dotenv import load_dotenv

# 🔥 SUBIR DOS NIVELES HASTA EL ROOT DEL PROYECTO
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_ROOT = os.path.abspath(
    os.path.join(BASE_DIR, "..", "..")
)

ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

print("DEBUG ENV PATH =", ENV_PATH)
print("EXISTS =", os.path.exists(ENV_PATH))

load_dotenv(dotenv_path=ENV_PATH)

URI_ATLAS = os.getenv("MONGO_URI")

print("DEBUG URI =", URI_ATLAS)

if not URI_ATLAS:
    raise Exception("❌ MONGO_URI no se está leyendo del .env")

client = MongoClient(URI_ATLAS, serverSelectionTimeoutMS=5000)
client.admin.command("ping")

db = client["RollsMusicDB"]

print("✔ MongoDB Atlas conectado correctamente")