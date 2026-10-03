import psycopg2

from app.core.config import settings


def fetch_all(statement: str, parameters=None):
    connection = psycopg2.connect(settings.database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            return cursor.fetchall()
    finally:
        connection.close()


def fetch_one(statement: str, parameters=None):
    connection = psycopg2.connect(settings.database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            return cursor.fetchone()
    finally:
        connection.close()
