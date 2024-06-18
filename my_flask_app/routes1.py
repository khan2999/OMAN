import re
from flask import render_template, request, jsonify, logging, send_file
from my_flask_app import app
from my_flask_app.db import get_db_connection
import mysql.connector
import json
from decimal import Decimal
import logging
import plotly.graph_objects as go
import plotly.io as pio


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

    # Average Order Value
    avg_order_value_query = """
        SELECT AVG(total) AS average_order_value
        FROM orders;
    """
    avg_order_value = execute_query(avg_order_value_query)
    kpis['average_order_value'] = decimal_to_float(avg_order_value)

    # Customer Retention Rate
    customer_retention_query = """
        SELECT ROUND((COUNT(DISTINCT customerID) - COUNT(DISTINCT CASE WHEN DATEDIFF(CURDATE(), orderDate) <= 30 THEN customerID ELSE NULL END)) / COUNT(DISTINCT customerID) * 100, 2) AS retention_rate
        FROM orders;
    """
    customer_retention_rate = execute_query(customer_retention_query)
    kpis['customer_retention_rate'] = decimal_to_float(customer_retention_rate)

    # Order Frequency
    order_frequency_query = """
        SELECT ROUND(AVG(order_count), 2) AS average_order_frequency
        FROM (
            SELECT customerID, COUNT(orderID) AS order_count
            FROM orders
            GROUP BY customerID
        ) AS subquery;
    """
    order_frequency = execute_query(order_frequency_query)
    kpis['order_frequency'] = decimal_to_float(order_frequency)

    # Conversion Rate
    conversion_rate_query = """
        SELECT ROUND((COUNT(orderID) / COUNT(DISTINCT customerID)) * 100, 2) AS conversion_rate
        FROM orders;
    """
    conversion_rate = execute_query(conversion_rate_query)
    kpis['conversion_rate'] = decimal_to_float(conversion_rate)

    # Customer Segmentation
    customer_segmentation_query = """
        SELECT 
            c.customerID, 
            SUM(o.total) AS total_spend, 
            COUNT(o.orderID) AS order_frequency, 
            s.state_abbr AS state
        FROM customers c
        JOIN orders o ON c.customerID = o.customerID
        JOIN stores s ON o.storeID = s.storeID
        GROUP BY c.customerID, s.state_abbr
        ORDER BY total_spend DESC;
    """
    customer_segmentation_data = execute_query(customer_segmentation_query)
    kpis['customer_segmentation'] = customer_segmentation_data  # Return the entire dataset for customer segmentation

    return jsonify(kpis)


@app.route('/kpi_reports', methods=['GET', 'POST'])
def kpi_reports():
    kpi_data = {}

    for kpi, query in queries.items():
        if '{filter_clause}' in query:
            query = query.format(filter_clause="")
        data = execute_query(query)
        # Top Selling Products
    top_selling_products_query = queries['top_selling_products']
    top_selling_products_data = execute_query(top_selling_products_query)
    kpi_data['top_selling_products'] = decimal_to_float(top_selling_products_data)

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
            JOIN products p ON oi.SKU = p.SKU
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


@app.route('/drilldown_city', methods=['GET'])
def drilldown_city_data():
    state = request.args.get('state')
    query = """
            SELECT s.city, COUNT(s.storeID) AS store_count
            FROM stores s
            WHERE s.state = %s
            GROUP BY s.city;
        """
    data = execute_query(query, (state,))
    return jsonify(decimal_to_float(data))


if __name__ == '__main__':
    logging.debug("Starting Flask app")
    app.run(debug=True)
