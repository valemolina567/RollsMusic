import os
from pymongo import MongoClient
from dotenv import load_dotenv

# SUBIR DOS NIVELES HASTA EL ROOT DEL PROYECTO
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_ROOT = os.path.abspath(
    os.path.join(BASE_DIR, "..", "..")
)

ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

# Opcional: Puedes comentar o eliminar estos prints si ya no necesitas debugear
print("DEBUG ENV PATH =", ENV_PATH)
print("EXISTS =", os.path.exists(ENV_PATH))

# 1. Cargamos las variables ocultas del archivo .env con la ruta exacta
load_dotenv(dotenv_path=ENV_PATH)

# 2. Obtenemos la URI de forma segura
URI_ATLAS = os.getenv("MONGO_URI")

# Opcional: Puedes comentar este print en producción por seguridad
print("DEBUG URI =", URI_ATLAS)

if not URI_ATLAS:
    raise Exception("----MONGO_URI no se está leyendo del .env----")

# 3. Conectamos a Atlas con manejo de errores y timeout
try:
    client = MongoClient(URI_ATLAS, serverSelectionTimeoutMS=5000)
    db = client["RollsMusicDB"]
    
    # Verificamos que la conexión es exitosa con un ping rápido
    client.admin.command("ping")
    print("----MongoDB Atlas conectado y verificado correctamente----")
except Exception as e:
    print(f"----Error conectando a MongoDB Atlas: {e}----")

## Cambios instanciados