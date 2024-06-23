import json
import logging
import re
import sqlite3
from decimal import Decimal
from math import radians, cos, sin, asin, sqrt

import mysql.connector
import plotly.graph_objects as go
import plotly.io as pio
from flask import jsonify
from flask import render_template, request, send_file

from my_flask_app import app
from my_flask_app.db import get_db_connection

# Database connection
mydb = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    passwd="DBml##%%98",
    database="omanpl"
)


def execute_query(query, params=None):
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            for result in cursor.execute(query, params, multi=True):
                if result.with_rows:
                    data = result.fetchall()
            cursor.close()
            connection.close()
            return data
        except mysql.connector.Error as error:
            app.logger.error(f"Error connecting to MySQL database: {error}")
            return None


def decimal_to_float(data):
    if data is None:
        return []
    return [[round(float(item), 2) if isinstance(item, Decimal) else item for item in row] for row in data]


queries = {
    'total_sales_by_category': """
                SELECT p.Category, SUM(p.Price * o.nItems) AS total_sales
                FROM orderItems oi
                JOIN products p ON oi.SKU = p.SKU
                JOIN orders o ON oi.orderID = o.orderID
                JOIN stores s ON o.storeID = s.storeID
                {filter_clause}
                GROUP BY p.Category;
    """,

    'sales_trends_over_time': """
            SELECT YEAR(orderDate) AS year, MONTH(orderDate) AS month, SUM(total) AS total_sales
            FROM orders o
            JOIN stores s ON o.storeID = s.storeID
            {filter_clause}
            GROUP BY YEAR(orderDate), MONTH(orderDate)
            ORDER BY YEAR(orderDate), MONTH(orderDate);
        """,
    'top_selling_products': """
        SELECT p.Name, SUM(o.nItems) AS total_quantity_sold
        FROM orderItems oi
        JOIN products p ON oi.SKU = p.SKU
        JOIN orders o ON oi.orderID = o.orderID
        JOIN stores s ON o.storeID = s.storeID
        {filter_clause}
        GROUP BY p.Name
        ORDER BY total_quantity_sold DESC
        LIMIT 10;
    """,

    'customer_distribution': """
            SELECT s.state_abbr, COUNT(c.customerID) AS customer_count
            FROM customers c
            JOIN orders o ON c.customerID = o.customerID
            JOIN stores s ON o.storeID = s.storeID
            {filter_clause}
            GROUP BY s.state_abbr;
        """,
    'customer_order_frequency_distribution': """
            SELECT COUNT(o.customerID) AS order_frequency, COUNT(DISTINCT o.customerID) AS customer_count
            FROM orders o
            {filter_clause}
            GROUP BY o.customerID
            ORDER BY order_frequency ASC;
        """,
    'customer_growth': """
            SELECT DATE_FORMAT(orderDate, '%Y-%m') AS month, COUNT(DISTINCT customerID) AS total_customers
            FROM orders o
            JOIN stores s ON o.storeID = s.storeID
            {filter_clause}
            GROUP BY month;
        """,
    'order_frequency': """
            SELECT ROUND(AVG(order_count), 2) AS average_order_frequency
            FROM (
                SELECT customerID, COUNT(orderID) AS order_count
                FROM orders
                GROUP BY customerID
            ) AS subquery
            {filter_clause};
        """,
    'average_order_value': """
            SELECT AVG(total) AS average_order_value
            FROM orders o
            JOIN stores s ON o.storeID = s.storeID
            {filter_clause};
        """,
    'sales_by_day_of_week': """SELECT DAYNAME(o.orderDate) AS day_of_week, SUM(o.total) AS total_sales
FROM orders o
GROUP BY DAYNAME(o.orderDate)
ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
{filter_clause}; 
""",
    'store_performance_by_category': """
SELECT s.storeID, p.Category, 
SUM(o.nItems) AS total_quantity_sold
FROM orderItems oi 
JOIN products p ON oi.SKU = p.SKU 
JOIN orders o ON oi.orderID = o.orderID 
JOIN stores s ON o.storeID = s.storeID 
GROUP BY s.storeID, p.Category 
ORDER BY s.storeID, total_quantity_sold DESC
{filter_clause}; 
    """,
    'average_order_value_over_time': """
  SELECT 
 DATE_FORMAT(o.orderDate, '%Y-%m') AS month,
 AVG(o.total) AS average_order_value
FROM orders o
GROUP BY month
ORDER BY month;
{filter_clause}; 
""",
    'store_performance_comparison': """
    SELECT s.storeID,
SUM(o.total) AS total_sales,
COUNT(o.orderID) AS num_orders,
AVG(o.total) AS average_order_size
FROM orders o
JOIN stores s ON o.storeID = s.storeID
GROUP BY s.storeID
ORDER BY total_sales DESC
{filter_clause}; 
    """
}


@app.route('/kpi_data', methods=['GET'])
def kpi_data():
    kpis = {}
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    date_filter = ""
    params = []

    if start_date and end_date:
        date_filter = "WHERE orderDate BETWEEN %s AND %s"
        params = [start_date, end_date]

    # Average Order Value
    avg_order_value_query = f"""
           SELECT AVG(o.total) AS average_order_value
           FROM orders o
           {date_filter}
       """
    avg_order_value = execute_query(avg_order_value_query, params)[0][0]  # Extract value directly
    kpis['average_order_value'] = avg_order_value if avg_order_value is not None else 0

    # Customer Retention Rate (30-day rolling)
    customer_retention_query = f"""
            WITH recent_orders AS (
                SELECT DISTINCT customerID 
                FROM orders
                WHERE orderDate BETWEEN DATE_SUB(%s, INTERVAL 30 DAY) AND %s
            ),
            previous_orders AS (
                SELECT DISTINCT customerID
                FROM orders
                WHERE orderDate BETWEEN DATE_SUB(%s, INTERVAL 60 DAY) AND DATE_SUB(%s, INTERVAL 30 DAY)
            )
            SELECT 
                ROUND(
                    (
                        COUNT(DISTINCT ro.customerID) /
                        COUNT(DISTINCT po.customerID) 
                    ) * 100, 2
                ) AS retention_rate
            FROM recent_orders ro
            RIGHT JOIN previous_orders po ON ro.customerID = po.customerID
        """
    retention_params = [end_date, end_date, end_date, end_date]  # Repeat params for both periods
    customer_retention_rate = execute_query(customer_retention_query, retention_params)[0][0]
    kpis['customer_retention_rate'] = customer_retention_rate if customer_retention_rate is not None else 0
    # Order Frequency
    order_frequency_query = f"""
        SELECT ROUND(AVG(order_count), 2) AS average_order_frequency
        FROM (
            SELECT customerID, COUNT(orderID) AS order_count
            FROM orders
            {date_filter}
            GROUP BY customerID
        ) AS subquery;
    """
    order_frequency = execute_query(order_frequency_query, params)
    kpis['order_frequency'] = decimal_to_float(order_frequency)

    # Conversion Rate
    conversion_rate_query = f"""
        SELECT ROUND((COUNT(orderID) / COUNT(DISTINCT customerID)) * 100, 2) AS conversion_rate
        FROM orders
        {date_filter};
    """
    conversion_rate = execute_query(conversion_rate_query, params)
    kpis['conversion_rate'] = decimal_to_float(conversion_rate)

    # Customer Segmentation (include average order value)
    customer_segmentation_query = f"""
            SELECT 
                c.customerID, 
                SUM(o.total) AS total_spend, 
                COUNT(o.orderID) AS order_frequency, 
                AVG(o.total) AS avg_order_value,
                s.state_abbr AS state
            FROM customers c
            JOIN orders o ON c.customerID = o.customerID
            JOIN stores s ON o.storeID = s.storeID
            {date_filter}
            GROUP BY c.customerID, s.state_abbr
            ORDER BY total_spend DESC;
        """
    customer_segmentation_data = execute_query(customer_segmentation_query, params)
    kpis['customer_segmentation'] = customer_segmentation_data

    # Top Selling Products
    top_selling_products_query = f"""
        SELECT
            p.Name,
            COUNT(oi.SKU) AS total_orders
        FROM orderitems oi
        JOIN products p ON oi.SKU = p.SKU
        JOIN orders o ON oi.orderID = o.orderID
        {date_filter}
        GROUP BY p.Name
        ORDER BY total_orders DESC;
    """
    top_selling_products_data = execute_query(top_selling_products_query, params)
    kpis['top_selling_products'] = decimal_to_float(top_selling_products_data)

    return jsonify(kpis)


@app.route('/kpi_reports', methods=['GET', 'POST'])
def kpi_reports():
    kpi_data = {}

    for kpi, query in queries.items():
        if '{filter_clause}' in query:
            query = query.format(filter_clause="")
        data = execute_query(query)
        kpi_data[kpi] = decimal_to_float(data)

    return render_template('kpi_reports.html', kpi_data=json.dumps(kpi_data))


def fetch_chart_data():
    chart_data = {}

    for chart, query in queries.items():
        if '{filter_clause}' in query:
            query = query.format(filter_clause="")
        data = execute_query(query)
        chart_data[chart] = decimal_to_float(data)

        # Generate chart as PDF
        if chart == 'top_selling_products':
            fig = go.Figure(data=go.Bar(x=[item[0] for item in data], y=[item[1] for item in data]))
            pio.write_image(fig, 'top_selling_products.pdf')

    return chart_data


@app.route('/analysis1', methods=['GET', 'POST'])
def analysis1_page():
    charts_data = {}

    for chart, query in queries.items():
        data = execute_query(query)
        charts_data[chart] = decimal_to_float(data)

    return render_template('melle.html', charts_data=json.dumps(charts_data))


@app.route('/download_chart_pdf', methods=['GET'])
def download_chart_pdf():
    chart = request.args.get('chart')
    file_path = f'{chart}.pdf'
    return send_file(file_path, as_attachment=True)


@app.route('/states', methods=['GET'])
def get_states():
    query = "SELECT DISTINCT state FROM stores;"
    states = execute_query(query)
    states = [s[0] for s in states if s[0]]  # Extract state names from the result set

    return jsonify(states)


def validate_date(date_str):
    """Validate date format (YYYY-MM-DD)."""
    return re.match(r'^\d{4}-\d{2}-\d{2}$', date_str) is not None


@app.route('/filter', methods=['GET'])
def filter_data():
    try:
        chart = request.args.get('chart')
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')
        category = request.args.get('category')
        region = request.args.get('region')
        state = request.args.get('state')

        # Validate and sanitize inputs
        if start_date and not validate_date(start_date):
            return jsonify({"error": "Invalid start date format"}), 400
        if end_date and not validate_date(end_date):
            return jsonify({"error": "Invalid end date format"}), 400

        # Construct query based on validated and sanitized inputs
        filters = []
        params = []

        if start_date:
            filters.append("o.orderDate >= %s")
            params.append(start_date)
        if end_date:
            filters.append("o.orderDate <= %s")
            params.append(end_date)
        if category:
            filters.append("p.Category = %s")
            params.append(category)
        if region:
            filters.append("s.region = %s")
            params.append(region)
        if state:
            filters.append("s.state = %s")
            params.append(state)

        filter_clause = " AND ".join(filters)
        if filter_clause:
            filter_clause = " WHERE " + filter_clause

        query_template = queries.get(chart)
        if not query_template:
            return jsonify({"error": "Invalid chart type"}), 400

        query = query_template.format(filter_clause=filter_clause)
        data = execute_query(query, params)
        return jsonify(decimal_to_float(data))

    except mysql.connector.Error as error:
        app.logger.error(f"Error connecting to MySQL database: {error}")
        return jsonify({"error": "Database error"}), 500

    except Exception as error:
        app.logger.error(f"An error occurred: {error}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/drilldown', methods=['GET'])
def drilldown_data():
    category = request.args.get('category')
    query = """
            SELECT p.Name, SUM(o.nItems) AS total_quantity_sold
            FROM orderItems oi
            JOIN products p ON oi.SKU = p.SKU
            JOIN orders o ON oi.orderID = o.orderID
            WHERE p.Category = %s
            GROUP BY p.Name
            ORDER BY total_quantity_sold DESC;
        """
    data = execute_query(query, (category,))
    return jsonify(decimal_to_float(data))


@app.route('/charts')
def charts_page():
    return render_template('extra_charts.html')


# Adding the new API routes
@app.route('/api/sales_by_day_of_week')
def sales_by_day_of_week():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT DAYNAME(o.orderDate) AS day_of_week, SUM(o.total) AS total_sales
            FROM orders o
            GROUP BY DAYNAME(o.orderDate)
            ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday');
        ''')
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching sales by day of week data: {error}")
        return jsonify({"error": "Database error"}), 500


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees) using the Haversine formula.
    """
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers. Use 3956 for miles
    return c * r


@app.route('/api/distance_analysis')
def distance_analysis():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT 
            o.customerID, 
            AVG(o.total) as aov, 
            COUNT(o.orderID) as order_frequency,
            SUM(o.total) as total_sales,  # Calculate total sales
            ANY_VALUE(s.latitude) as store_lat,  
            ANY_VALUE(s.longitude) as store_lon,
            ANY_VALUE(c.latitude) as customer_lat, 
            ANY_VALUE(c.longitude) as customer_lon
        FROM Orders o
        JOIN Stores s ON o.storeID = s.storeID
        JOIN Customers c ON o.customerID = c.customerID
        GROUP BY o.customerID 
    ''')

    data = []
    for row in cursor.fetchall():
        distance = calculate_distance(row['store_lat'], row['store_lon'], row['customer_lat'], row['customer_lon'])
        data.append({
            'distance': distance,
            'aov': row['aov'],
            'order_frequency': row['order_frequency'],
            'total_sales': row['total_sales']  # Add total sales to data
        })

    # Bin distances into 5 km intervals
    distance_bins = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    binned_data = {}
    for d in data:
        for i in range(len(distance_bins) - 1):
            if distance_bins[i] <= d['distance'] < distance_bins[i + 1]:
                bin_key = f"{distance_bins[i]}-{distance_bins[i + 1]}"
                if bin_key not in binned_data:
                    binned_data[bin_key] = {'aov': [], 'order_frequency': [], 'total_sales': []}
                binned_data[bin_key]['aov'].append(d['aov'])
                binned_data[bin_key]['order_frequency'].append(d['order_frequency'])
                binned_data[bin_key]['total_sales'].append(d['total_sales'])  # Add total sales to bin data
                break

    # Calculate aggregate statistics for each bin
    aggregate_data = []
    for bin_key, bin_data in binned_data.items():
        aov_mean = sum(bin_data['aov']) / len(bin_data['aov'])
        aov_std = (sum((x - aov_mean) ** 2 for x in bin_data['aov']) / len(bin_data['aov'])) ** 0.5
        order_frequency_mean = sum(bin_data['order_frequency']) / len(bin_data['order_frequency'])
        order_frequency_std = (sum((x - order_frequency_mean) ** 2 for x in bin_data['order_frequency']) / len(
            bin_data['order_frequency'])) ** 0.5
        total_sales_mean = sum(bin_data['total_sales']) / len(bin_data['total_sales'])
        total_sales_std = (sum((x - total_sales_mean) ** 2 for x in bin_data['total_sales']) / len(
            bin_data['total_sales'])) ** 0.5
        aggregate_data.append({
            'distance_bin': bin_key,
            'aov_mean': aov_mean,
            'aov_std': aov_std,
            'order_frequency_mean': order_frequency_mean,
            'order_frequency_std': order_frequency_std,
            'total_sales_mean': total_sales_mean,  # Add mean total sales
            'total_sales_std': total_sales_std  # Add total sales std
        })

    conn.close()
    cursor.close()

    print("Aggregate Data:", aggregate_data)  # Log the aggregate data

    return jsonify(aggregate_data)


@app.route('/api/store_performance_by_category')
def store_performance_by_category():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT s.storeID, p.Category, 
            SUM(o.nItems) AS total_quantity_sold
            FROM orderItems oi 
            JOIN products p ON oi.SKU = p.SKU 
            JOIN orders o ON oi.orderID = o.orderID 
            JOIN stores s ON o.storeID = s.storeID 
            GROUP BY s.storeID, p.Category 
            ORDER BY total_quantity_sold DESC;
        ''')
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching store performance by category data: {error}")
        return jsonify({"error": "Database error"}), 500
    except Exception as error:
        app.logger.error(f"An unexpected error occurred: {error}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/api/average_order_value_over_time')
def average_order_value_over_time():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT 
            DATE_FORMAT(o.orderDate, '%Y-%m') AS month,
            AVG(o.total) AS average_order_value
            FROM orders o
            GROUP BY month
            ORDER BY month;
        ''')
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching average order value over time data: {error}")
        return jsonify({"error": "Database error"}), 500


@app.route('/api/store_performance_comparison')
def store_performance_comparison():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT s.storeID,
            SUM(o.total) AS total_sales,
            COUNT(o.orderID) AS num_orders,
            AVG(o.total) AS average_order_size
            FROM orders o
            JOIN stores s ON o.storeID = s.storeID
            GROUP BY s.storeID
            ORDER BY total_sales DESC;
        ''')
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching store performance comparison data: {error}")
        return jsonify({"error": "Database error"}), 500


@app.route('/api/customer_segmentation')
def customer_segmentation():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT c.customerID,
            SUM(o.total) AS total_spend,
            COUNT(o.orderID) AS num_orders,
            s.state_abbr AS state,
            s.city AS city
            FROM orders o
            JOIN customers c ON o.customerID = c.customerID
            JOIN stores s ON o.storeID = s.storeID
            GROUP BY c.customerID, s.state_abbr, s.city
            ORDER BY total_spend DESC;
        ''')
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching customer segmentation data: {error}")
        return jsonify({"error": "Database error"}), 500


@app.route('/api/inventory_turnover_rate')
def inventory_turnover_rate():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT p.SKU, SUM(o.nItems) AS total_quantity_sold,
            SUM(p.Price * o.nItems) AS total_revenue,
            SUM(o.nItems) AS turnover_rate
            FROM orderItems oi
            JOIN products p ON oi.SKU =p.SKU
            JOIN orders o ON oi.orderID = o.orderID
            GROUP BY p.SKU
            ORDER BY turnover_rate DESC;
        ''')
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching inventory turnover rate data: {error}")
        return jsonify({"error": "Database error"}), 500
    except Exception as error:
        app.logger.error(f"An unexpected error occurred: {error}")
        return jsonify({"error": "Internal server error"}), 500


# New API routes with filtering functionality

@app.route('/api/filter_sales_by_day_of_week', methods=['POST'])
def filter_sales_by_day_of_week():
    try:
        data = request.get_json()
        day_of_week = data['day_of_week']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT DAYNAME(o.orderDate) AS day_of_week, SUM(o.total) AS total_sales
            FROM orders o
            WHERE DAYNAME(o.orderDate) = %s
            GROUP BY DAYNAME(o.orderDate)
            ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday');
        ''', (day_of_week,))
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching filtered sales by day of week data: {error}")
        return jsonify({"error": "Database error"}), 500


@app.route('/api/filter_store_performance_by_category', methods=['POST'])
def filter_store_performance_by_category():
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        category = data.get('category')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = '''
            SELECT s.storeID, p.Category, 
            SUM(o.nItems) AS total_quantity_sold
            FROM orderItems oi 
            JOIN products p ON oi.SKU = p.SKU 
            JOIN orders o ON oi.orderID = o.orderID 
            JOIN stores s ON o.storeID = s.storeID 
            WHERE 1=1
        '''
        params = []
        if store_id:
            query += ' AND s.storeID = %s'
            params.append(store_id)
        if category:
            query += ' AND p.Category = %s'
            params.append(category)
        query += ' GROUP BY s.storeID, p.Category ORDER BY total_quantity_sold DESC'
        cursor.execute(query, params)
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching filtered store performance by category data: {error}")
        return jsonify({"error": "Database error"}), 500


@app.route('/api/filter_average_order_value_over_time', methods=['POST'])
def filter_average_order_value_over_time():
    try:
        data = request.get_json()
        start_date = data['start_date']
        end_date = data['end_date']
        store_id = data.get('store_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = '''
            SELECT 
            DATE_FORMAT(o.orderDate, '%Y-%m') AS month,
            AVG(o.total) AS average_order_value
            FROM orders o
            WHERE o.orderDate BETWEEN %s AND %s
        '''
        params = [start_date, end_date]
        if store_id:
            query += ' AND o.storeID = %s'
            params.append(store_id)
        query += ' GROUP BY month ORDER BY month'
        cursor.execute(query, params)
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching filtered average order value over time data: {error}")
        return jsonify({"error": "Database error"}), 500


@app.route('/api/filter_store_performance_comparison', methods=['POST'])
def filter_store_performance_comparison():
    try:
        data = request.get_json()
        store_ids = data.get('store_ids')
        start_date = data['start_date']
        end_date = data['end_date']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = '''
            SELECT s.storeID,
            SUM(o.total) AS total_sales,
            COUNT(o.orderID) AS num_orders,
            AVG(o.total) AS average_order_size
            FROM orders o
            JOIN stores s ON o.storeID = s.storeID
            WHERE o.orderDate BETWEEN %s AND %s
        '''
        params = [start_date, end_date]
        if store_ids:
            query += ' AND s.storeID IN (' + ','.join(['%s'] * len(store_ids)) + ')'
            params.extend(store_ids)
        query += ' GROUP BY s.storeID ORDER BY total_sales DESC'
        cursor.execute(query, params)
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching filtered store performance comparison data: {error}")
        return jsonify({"error": "Database error"}), 500


@app.route('/api/filter_customer_segmentation', methods=['POST'])
def filter_customer_segmentation():
    try:
        data = request.get_json()
        state = data.get('state')
        city = data.get('city')
        zip_code = data.get('zip_code')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = '''
            SELECT c.customerID,
            SUM(o.total) AS total_spend,
            COUNT(o.orderID) AS num_orders,
            s.state_abbr AS state,
            s.city AS city,
            s.zip_code AS zip_code
            FROM orders o
            JOIN customers c ON o.customerID = c.customerID
            JOIN stores s ON o.storeID = s.storeID
            WHERE 1=1
        '''
        params = []
        if state:
            query += ' AND s.state_abbr = %s'
            params.append(state)
        if city:
            query += ' AND s.city = %s'
            params.append(city)
        if zip_code:
            query += ' AND s.zip_code = %s'
            params.append(zip_code)
        query += ' GROUP BY c.customerID, s.state_abbr, s.city, s.zip_code ORDER BY total_spend DESC'
        cursor.execute(query, params)
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching filtered customer segmentation data: {error}")
        return jsonify({"error": "Database error"}), 500


@app.route('/api/filter_inventory_turnover_rate', methods=['POST'])
def filter_inventory_turnover_rate():
    try:
        data = request.get_json()
        category = data.get('category')
        size = data.get('size')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = '''
            SELECT p.SKU, p.Category, p.Size, 
            SUM(o.nItems) AS total_quantity_sold,
            SUM(p.Price * o.nItems) AS total_revenue,
            SUM(o.nItems) AS turnover_rate
            FROM orderItems oi
            JOIN products p ON oi.SKU = p.SKU
            JOIN orders o ON oi.orderID = o.orderID
            WHERE 1=1
        '''
        params = []
        if category:
            query += ' AND p.Category = %s'
            params.append(category)
        if size:
            query += ' AND p.Size = %s'
            params.append(size)
        query += ' GROUP BY p.SKU, p.Category, p.Size ORDER BY turnover_rate DESC'
        cursor.execute(query, params)
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching filtered inventory turnover rate data: {error}")
        return jsonify({"error": "Database error"}), 500


# Analysis tool API routes

@app.route('/api/trend_analysis', methods=['POST'])
def trend_analysis():
    try:
        data = request.get_json()
        metric = data['metric']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if metric == 'sales':
            cursor.execute('''
                SELECT 
                DATE_FORMAT(o.orderDate, '%Y-%m') AS month,
                SUM(o.total) AS total_sales
                FROM orders o
                GROUP BY month
                ORDER BY month;
            ''')
        elif metric == 'orders':
            cursor.execute('''
                SELECT 
                DATE_FORMAT(o.orderDate, '%Y-%m') AS month,
                COUNT(o.orderID) AS num_orders
                FROM orders o
                GROUP BY month
                ORDER BY month;
            ''')
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching trend analysis data: {error}")
        return jsonify({"error": "Database error"}), 500


if __name__ == '__main__':
    logging.debug("Starting Flask app")
    app.run(debug=True)
