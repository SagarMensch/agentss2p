from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://mrityunjaygupta:dYuyQzS24KtAI2Ez@sequeldev-expense.l3ygq.mongodb.net/VaOM_CLM_DEV?retryWrites=true&w=majority")
DB_NAME = "VaOM_CLM_DEV"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

def get_collection(collection_name: str):
    return db[collection_name]
