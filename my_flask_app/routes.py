from flask import render_template, request, jsonify
from my_flask_app import app
from my_flask_app.db import get_db_connection
import mysql.connector

@app.route('/')
def welcome_page():
    return render_template('welcome.html')

@app.route('/analysis', methods=['GET', 'POST'])
def analysis_page():
    data = None  # Initialize data variable

    if request.method == 'POST':
        selected_table = request.form['table']
        selected_column = request.form['column']

        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                query = f"SELECT {selected_column} FROM {selected_table};"
                cursor.execute(query)
                data = cursor.fetchall()

                cursor.close()
                connection.close()
            except mysql.connector.Error as error:
                return f"Error connecting to MySQL database: {error}"

    return render_template('index.html', data=data)

@app.route('/stores', methods=['GET'])
def get_stores():
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    s.storeID, 
                    s.latitude, 
                    s.longitude, 
                    s.city, 
                    s.state, 
                    YEAR(o.orderDate) as year, 
                    MONTH(o.orderDate) as month,
                    COALESCE(ROUND(SUM(o.total), 2), 0) as total
                FROM stores s
                LEFT JOIN orders o ON s.storeID = o.storeID
                GROUP BY s.storeID, s.latitude, s.longitude, s.city, s.state, YEAR(o.orderDate), MONTH(o.orderDate)
                ORDER BY s.storeID, year, month
            """)
            stores = cursor.fetchall()

            cursor.close()
            connection.close()

            return jsonify(stores)

        except mysql.connector.Error as error:
            return jsonify({"error": str(error)})
    else:
        return jsonify({"error": "Verbindung zur Datenbank konnte nicht hergestellt werden"})