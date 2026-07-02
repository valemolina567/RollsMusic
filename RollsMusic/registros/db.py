import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Subir un nivel hasta la carpeta RollsMusic (donde vive el .env)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

# Cargamos las variables ocultas del archivo .env
load_dotenv(dotenv_path=ENV_PATH)

# Obtenemos la URI de forma segura
URI_ATLAS = os.getenv("MONGO_URI")

if not URI_ATLAS:
    raise Exception(f"MONGO_URI no se está leyendo del .env (buscado en: {ENV_PATH})")

# Conectamos a Atlas con manejo de errores y timeout
try:
    client = MongoClient(URI_ATLAS, serverSelectionTimeoutMS=5000)
    db = client["RollsMusicDB"]

    # Ping rápido para verificar que la conexión es exitosa
    client.admin.command("ping")
    print("Conexión a MongoDB Atlas exitosa.")
except Exception as e:
    print(f"Error conectando a MongoDB Atlas: {e}")