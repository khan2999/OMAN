import locale
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

# Ensure the welcome_page route is defined only once
@app.route('/')
def welcome_page():
    return render_template('welcome.html')

@app.route('/get_data', methods=['POST'])
def get_data():
    category = request.form['category']
    start_year = request.form['start_year']
    end_year = request.form['end_year']

    logging.info(f"Selected category: {category}")
    logging.info(f"Start year: {start_year}")
    logging.info(f"End year: {end_year}")

    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        if category == "all":
            query = """
                SELECT SUM(o.total) AS total_revenue, AVG(o.total/o.nitems) AS average_order_value, 
                       COUNT(o.orderID) AS total_orders, SUM(o.nitems) AS total_sales
                FROM orders o
                WHERE YEAR(o.orderDate) BETWEEN %s AND %s
                """
            cursor.execute(query, (start_year, end_year))
        else:
            query = """
                SELECT SUM(o.total) AS total_revenue, AVG(o.total/o.nitems) AS average_order_value, 
                       COUNT(o.orderID) AS total_orders, SUM(o.nitems) AS total_sales
                FROM orders o
                JOIN orderitems oi ON o.orderID = oi.orderID
                JOIN products p ON oi.SKU = p.SKU
                WHERE p.Name = %s AND YEAR(o.orderDate) BETWEEN %s AND %s
                """
            cursor.execute(query, (category, start_year, end_year))
        data = cursor.fetchone()
        cursor.close()
        connection.close()

        logging.info(f"Fetched data: {data}")

        total_revenue = locale.format_string('%.2f', data[0], grouping=True).replace(",", ".")
        average_order_value = locale.format_string('%.2f', data[1], grouping=True).replace(",", ".")
        total_orders = locale.format_string('%d', data[2], grouping=True).replace(",", ".")
        total_sales = locale.format_string('%.2f', data[3], grouping=True).replace(",", ".")

        if len(total_revenue) > 6:
            total_revenue = str(int(float(total_revenue) / 1000)) + "K"
        if len(average_order_value) > 6:
            average_order_value = str(int(float(average_order_value) / 1000)) + "K"
        if len(total_orders) > 6:
            total_orders = str(int(float(total_orders) / 1000)) + "K"
        if len(total_sales) > 6:
            total_sales = str(int(float(total_sales) / 1000)) + "K"

        return render_template('welcome.html', total_revenue=total_revenue,
                               average_order_value=average_order_value,
                               total_orders=total_orders,
                               total_sales=total_sales)
    else:
        return jsonify({"error": "Could not establish a database connection"})

@app.route('/top_stores', methods=['GET'])
def get_top_stores():
    query = """
        SELECT 
            s.storeID,
            s.city,
            s.state,
            SUM(COALESCE(o.total, 0)) AS total_revenue
        FROM stores s
        LEFT JOIN orders o ON s.storeID = o.storeID AND YEAR(o.orderDate) BETWEEN 2020 AND 2023
        GROUP BY s.storeID, s.city, s.state
        ORDER BY total_revenue DESC
        LIMIT 5
    """
    top_stores = execute_query(query)
    return jsonify(top_stores if top_stores else {"error": "Error fetching top stores data"})

@app.route('/top_products', methods=['GET'])
def get_top_products():
    query = """
        SELECT 
            p.Name AS product_name,
            COUNT(oi.orderID) AS total_orders
        FROM products p
        JOIN orderitems oi ON p.SKU = oi.SKU
        JOIN orders o ON oi.orderID = o.orderID AND YEAR(o.orderDate) BETWEEN 2020 AND 2023
        GROUP BY p.Name
        ORDER BY total_orders DESC
        LIMIT 5
    """
    top_products = execute_query(query)
    return jsonify(top_products if top_products else {"error": "Error fetching top products data"})

@app.route('/sales_by_size', methods=['GET'])
def get_sales_by_size():
    query = """
        SELECT 
            p.Size AS size,
            COUNT(DISTINCT oi.orderID) AS total_sales  -- Count distinct orders per size
        FROM products p
        LEFT JOIN orderitems oi ON p.SKU = oi.SKU
        LEFT JOIN orders o ON oi.orderID = o.orderID
        WHERE YEAR(o.orderDate) IN (2020, 2022, 2023)
        GROUP BY p.Size
        ORDER BY p.Size
    """
    sales_by_size = execute_query(query)
    return jsonify(sales_by_size if sales_by_size else {"error": "Error fetching sales by size data"})

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
                YEAR(o.orderDate) AS year, 
                COUNT(DISTINCT o.customerID) AS customer_count
            FROM orders o
            WHERE o.storeID = %s
            GROUP BY YEAR(o.orderDate)
        ) AS yearly_customers
    """
    customer_counts = execute_query(query, (storeID,))
    return jsonify(customer_counts if customer_counts else {"error": "Error fetching customer counts data"})
