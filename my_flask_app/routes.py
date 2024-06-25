from flask import render_template, request, jsonify
from my_flask_app import app
from my_flask_app.db import get_db_connection
import mysql.connector
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

def execute_query(query, params=None):
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, params)
            result = cursor.fetchall()
            cursor.close()
            connection.close()
            return result
        except mysql.connector.Error as error:
            logging.error(f"Error executing query: {error}")
            return None
    else:
        logging.error("Failed to establish database connection")
        return None

@app.route('/')
def welcome_page():
    return render_template('welcome.html')

@app.route('/analysis', methods=['GET', 'POST'])
def analysis_page():
    data = None  # Initialize data variable

    if request.method == 'POST':
        selected_table = request.form['table']
        selected_column = request.form['column']

        query = f"SELECT {selected_column} FROM {selected_table};"
        data = execute_query(query)

    return render_template('index.html', data=data)

@app.route('/stores', methods=['GET'])
def get_stores():
    query = """
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
    """
    stores = execute_query(query)
    return jsonify(stores if stores else {"error": "Error fetching stores data"})


@app.route('/customers/<storeID>', methods=['GET'])
def get_customer_counts(storeID):
    query = """
        SELECT 
            year, 
            customer_count,
            COALESCE(customer_count - LAG(customer_count) OVER (ORDER BY year), 0) AS delta
        FROM (
            SELECT 
                YEAR(o.orderDate) as year, 
                COUNT(DISTINCT o.customerID) as customer_count
            FROM orders o
            WHERE o.storeID = %s
            GROUP BY YEAR(o.orderDate)
            ORDER BY year
        ) yearly_counts
    """
    customer_counts = execute_query(query, (storeID,))
    return jsonify(customer_counts if customer_counts else {"error": "Error fetching customer counts data"})

