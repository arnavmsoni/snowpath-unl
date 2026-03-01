import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
CAMPUS_LAT = float(os.getenv("CAMPUS_LAT", "40.8200"))
CAMPUS_LON = float(os.getenv("CAMPUS_LON", "-96.7000"))
BBOX = os.getenv("BBOX", "40.812,-96.713,40.827,-96.690")