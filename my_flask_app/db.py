import mysql.connector
from mysql.connector import Error


def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            passwd="Password00123",
            database="test"
        )
        return connection
    except Error as e:
        print(f"Fehler bei der Verbindung zur MySQL-Datenbank: {e}")
        return None
