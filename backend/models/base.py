"""
Base declarativa para todos los modelos
"""

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Schema para todas las tablas
SCHEMA_NAME = 'appmediciones'
