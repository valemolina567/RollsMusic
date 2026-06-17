import os
from pymongo import MongoClient
from dotenv import load_dotenv

# 1. Cargamos las variables ocultas del archivo .env
load_dotenv()

# 2. Obtenemos la URI de forma segura
URI_ATLAS = os.getenv("MONGO_URI")

# 3. Conectamos a Atlas
try:
    client = MongoClient(URI_ATLAS)
    db = client['RollsMusicDB'] 
    # Opcional: Esto hace un ping rápido para verificar que la conexión es exitosa
    client.admin.command('ping')
    print("Conexión a MongoDB Atlas exitosa.")
except Exception as e:
    print(f"Error conectando a MongoDB Atlas: {e}")
    
## Cambios instanciados
