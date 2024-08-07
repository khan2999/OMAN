from flask import render_template, request, jsonify
from my_flask_app import app
from my_flask_app.db import get_db_connection
import mysql.connector
import logging
from decimal import Decimal

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


@app.route('/get_data', methods=['POST'])
def get_data_summary():
    data = request.json
    period = data.get('period')

    if period == 'last_week':
        start_date, end_date = '2022-12-25', '2022-12-31'
    elif period == 'last_month':
        start_date, end_date = '2022-12-01', '2022-12-31'
    elif period == 'last_year':
        start_date, end_date = '2022-01-01', '2022-12-31'
    else:
        start_date, end_date = '2019-01-01', '2024-12-31'

    logging.info(f"Selected period: {period}")
    logging.info(f"Start date: {start_date}")
    logging.info(f"End date: {end_date}")

    queries = {
        "total_revenue": "SELECT SUM(total) AS total_revenue FROM orders WHERE orderDate BETWEEN %s AND %s",
        "average_order_value": "SELECT AVG(total / nitems) AS average_order_value FROM orders WHERE orderDate BETWEEN %s AND %s",
        "total_orders": "SELECT COUNT(orderID) AS total_orders FROM orders WHERE orderDate BETWEEN %s AND %s",
        "total_sales": "SELECT SUM(nitems) AS total_sales FROM orders WHERE orderDate BETWEEN %s AND %s",
    }

    results = {}
    for key, query in queries.items():
        result = execute_query(query, (start_date, end_date))
        results[key] = result[0][key] if result else '0'

    logging.info(f"Fetched data: {results}")

    return jsonify(results)


@app.route('/top_stores', methods=['POST'])
def get_top_stores_data():
    data = request.json
    period = data.get('period', '')

    if period == 'last_week':
        start_date, end_date = '2022-12-25', '2022-12-31'
    elif period == 'last_month':
        start_date, end_date = '2022-12-01', '2022-12-31'
    elif period == 'last_year':
        start_date, end_date = '2022-01-01', '2022-12-31'
    else:
        start_date, end_date = '2019-01-01', '2024-12-31'

    logging.info(f"Selected period: {period}")
    logging.info(f"Start date: {start_date}")
    logging.info(f"End date: {end_date}")

    top_stores_query = """
        SELECT s.storeID, s.city, SUM(o.total) AS total_income
        FROM orders o
        JOIN stores s ON o.storeID = s.storeID
        WHERE o.orderDate BETWEEN %s AND %s
        GROUP BY s.storeID, s.city
        ORDER BY total_income DESC
        LIMIT 5
    """

    top_stores_data = execute_query(top_stores_query, (start_date, end_date))
    logging.info(f"Top stores data: {top_stores_data}")

    results = {
        "top_stores": top_stores_data
    }

    return jsonify(results)


@app.route('/income_timeline', methods=['POST'])
def income_timeline():
    data = request.json
    period = data.get('period', '')

    if period == 'last_week':
        start_date, end_date = '2022-12-25', '2022-12-31'
    elif period == 'last_month':
        start_date, end_date = '2022-12-01', '2022-12-31'
    elif period == 'last_year':
        start_date, end_date = '2022-01-01', '2022-12-31'
    else:
        start_date, end_date = '2019-01-01', '2024-12-31'

    income_timeline_query = """
        SELECT DATE(orderDate) as date, SUM(total) as income
        FROM orders
        WHERE orderDate BETWEEN %s AND %s
        GROUP BY DATE(orderDate)
        ORDER BY DATE(orderDate)
    """

    try:
        result = execute_query(income_timeline_query, (start_date, end_date))
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error fetching income timeline data: {str(e)}")
        return jsonify([]), 500


@app.route('/customer_types', methods=['POST'])
def get_customer_types():
    data = request.json
    period = data.get('period', '')

    default_start_date = '2019-01-01'
    default_end_date = '2024-12-31'

    if period == 'last_week':
        selected_start_date, selected_end_date = '2022-12-25', '2022-12-31'
    elif period == 'last_month':
        selected_start_date, selected_end_date = '2022-12-01', '2022-12-31'
    elif period == 'last_year':
        selected_start_date, selected_end_date = '2022-01-01', '2022-12-31'
    else:
        selected_start_date, selected_end_date = '2019-01-01', '2024-12-31'

    logging.info(f"Selected period: {period}")
    logging.info(f"Start date: {selected_start_date}")
    logging.info(f"End date: {selected_end_date}")

    customer_types_query = """
        SELECT customerID,
               CASE 
                   WHEN total_orders <= 2 THEN 'walk_ins'
                   WHEN total_orders BETWEEN 3 AND 10 THEN 'regulars'
                   ELSE 'vip'
               END AS customer_type
        FROM (
            SELECT customerID, COUNT(orderID) AS total_orders
            FROM orders
            WHERE orderDate BETWEEN %s AND %s
            GROUP BY customerID
        ) AS customer_orders
    """

    customer_types_result = execute_query(customer_types_query, (default_start_date, default_end_date))

    if not customer_types_result:
        logging.warning("No data found for the default period.")
        return jsonify({'walk_ins': 0, 'regulars': 0, 'vip': 0})

    customer_types_dict = {row['customerID']: row['customer_type'] for row in customer_types_result}

    orders_query = """
        SELECT customerID, COUNT(orderID) as order_count
        FROM orders
        WHERE orderDate BETWEEN %s AND %s
        GROUP BY customerID
    """

    orders_result = execute_query(orders_query, (selected_start_date, selected_end_date))

    if not orders_result:
        logging.warning("No orders found for the selected period.")
        return jsonify({'walk_ins': 0, 'regulars': 0, 'vip': 0})

    customer_type_counts = {'walk_ins': 0, 'regulars': 0, 'vip': 0}

    for order in orders_result:
        customer_id = order['customerID']
        customer_type = customer_types_dict.get(customer_id, 'walk_ins')
        customer_type_counts[customer_type] += 1

    logging.info(f"Customer type counts for the selected period: {customer_type_counts}")

    return jsonify(customer_type_counts)


@app.route('/top_products', methods=['POST'])
def get_top_products():
    data = request.json
    period = data.get('period', '')

    if period == 'last_week':
        start_date, end_date = '2022-12-25', '2022-12-31'
    elif period == 'last_month':
        start_date, end_date = '2022-12-01', '2022-12-31'
    elif period == 'last_year':
        start_date, end_date = '2022-01-01', '2022-12-31'
    else:
        start_date, end_date = '2019-01-01', '2024-12-31'

    logging.info(f"Selected period: {period}")
    logging.info(f"Start date: {start_date}")
    logging.info(f"End date: {end_date}")

    top_products_query = """
        SELECT p.Name, SUM(o.nItems) AS total_sales
        FROM orderitems oi
        JOIN products p ON oi.SKU = p.SKU
        JOIN orders o ON oi.orderID = o.orderID
        WHERE o.orderDate BETWEEN %s AND %s
        GROUP BY p.Name
        ORDER BY total_sales DESC
        LIMIT 5
    """

    top_products_data = execute_query(top_products_query, (start_date, end_date))
    logging.info(f"Top products data: {top_products_data}")

    result_data = []
    for item in top_products_data:
        result_data.append({
            'name': item['Name'],
            'total_sales': float(item['total_sales']) if isinstance(item['total_sales'], Decimal) else item[
                'total_sales']
        })

    logging.info(f"Transformed top products data: {result_data}")

    results = {"top_products": result_data}

    return jsonify(results)
