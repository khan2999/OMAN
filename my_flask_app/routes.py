import locale

from flask import render_template, request, jsonify
from my_flask_app import app
from my_flask_app.db import get_db_connection
import mysql.connector
from flask import jsonify

db = mysql.connector.connect(
    host="localhost",
    user="root",
    passwd="password",
    database="Pizza"
)
cursor = db.cursor()

@app.route('/')
def welcome_page():
    return render_template('welcome.html')

@app.route('/get_data', methods=['POST'])
def get_data():
    category = request.form['category']
    start_year = request.form['start_year']
    end_year = request.form['end_year']

    print("Selected category:", category)
    print("Start year:", start_year)
    print("End year:", end_year)

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

    print("Fetched data:", data)


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



@app.route('/top_stores', methods=['GET'])
def get_top_stores():
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
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
            cursor.execute(query)
            top_stores = cursor.fetchall()

            cursor.close()
            connection.close()

            return jsonify(top_stores)

        except mysql.connector.Error as error:
            connection.close()
            return jsonify({"error": str(error)})
    else:
        return jsonify({"error": "Could not establish a database connection"})

@app.route('/top_products', methods=['GET'])
def get_top_products():
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
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
            cursor.execute(query)
            top_products = cursor.fetchall()

            cursor.close()
            connection.close()

            return jsonify(top_products)

        except mysql.connector.Error as error:
            connection.close()
            return jsonify({"error": str(error)})
    else:
        return jsonify({"error": "Could not establish a database connection"})



@app.route('/sales_by_size', methods=['GET'])
def get_sales_by_size():
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
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
            cursor.execute(query)
            sales_by_size = cursor.fetchall()

            cursor.close()
            connection.close()

            return jsonify(sales_by_size)

        except mysql.connector.Error as error:
            connection.close()
            return jsonify({"error": str(error)})
    else:
        return jsonify({"error": "Could not establish a database connection"})


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
