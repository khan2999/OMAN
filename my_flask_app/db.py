# my_flask_app/db.py
import mysql.connector
from flask import current_app

def get_db_connection():
    # Fügen Sie Ihre Datenbankverbindungsdetails hinzu
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        passwd="Password00123",
        database="test"
    )
    return connection

def execute_query(query, params=None):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    result = None
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        result = cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Error executing query: {e}")
    finally:
        cursor.close()
        connection.close()
    return result
