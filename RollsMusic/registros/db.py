from pymongo import MongoClient

# Conexión a tu servidor local de MongoDB (asegúrate de tener MongoDB Compass abierto y corriendo)
client = MongoClient('mongodb://localhost:27017/')

# Seleccionamos la base de datos de tu proyecto
db = client['RollsMusicDB']