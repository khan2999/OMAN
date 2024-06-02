import mysql.connector
from mysql.connector import Error


def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            passwd="password",
            database="pizza"
        )
        return connection
    except Error as e:
        print(f"Fehler bei der Verbindung zur MySQL-Datenbank: {e}")
        return None
