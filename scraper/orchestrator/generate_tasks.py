"""
Orquestrador: gera tasks.json com os meses que ainda faltam coletar.
Roda ANTES do spider. Consulta o MongoDB para não reprocessar o que já existe.
"""

import json
import calendar
from datetime import date
from pymongo import MongoClient
