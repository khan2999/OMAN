from flask import render_template, request, jsonify, logging
from my_flask_app import app
from my_flask_app.db import get_db_connection
import mysql.connector
import json
from decimal import Decimal
import logging


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
                {filter_clause}
                GROUP BY YEAR(orderDate), MONTH(orderDate)
                ORDER BY YEAR(orderDate), MONTH(orderDate);
                """,

    'top_selling_products': """
            SELECT p.Name, SUM(o.nItems) AS total_quantity_sold
                FROM orderItems oi
                JOIN products p ON oi.SKU = p.SKU
                JOIN orders o ON oi.orderID = o.orderID
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
           GROUP BY o.customerID
           ORDER BY order_frequency ASC;
       """,
    'customer_growth': """
            SELECT DATE_FORMAT(orderDate, '%Y-%m') AS month, COUNT(DISTINCT customerID) AS total_customers
            FROM orders o
            JOIN stores s ON o.storeID = s.storeID
            GROUP BY month;
        """,
    'order_frequency': """
          SELECT ROUND(AVG(order_count), 2) AS average_order_frequency
          FROM (
              SELECT customerID, COUNT(orderID) AS order_count
              FROM orders
              GROUP BY customerID
          ) AS subquery;
      """,
    'average_order_value': """
            SELECT AVG(total) AS average_order_value
            FROM orders;
        """,
    'store_performance_by_category': """
            SELECT s.storeID, p.Category, 
            SUM(oi.nItems) AS total_quantity_sold
            FROM orderItems oi 
            JOIN products p ON oi.SKU = p.SKU 
            JOIN orders o ON oi.orderID = o.orderID 
            JOIN stores s ON o.storeID = s.storeID 
            GROUP BY s.storeID, p.Category 
            ORDER BY s.storeID, total_quantity_sold DESC;
        """,

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

    customer_retention_rate = """
                       SELECT 
                           ROUND((COUNT(DISTINCT customerID) - COUNT(DISTINCT CASE WHEN DATEDIFF(CURDATE(), orderDate) <= 30 THEN customerID ELSE NULL END)) / COUNT(DISTINCT customerID) * 100, 2) AS retention_rate
                       FROM orders;
                   """
    customer_retention_rate = execute_query(customer_retention_rate)
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
    # Customer Growth
    customer_growth = """
                       SELECT 
                           DATE_FORMAT(orderDate, '%Y-%m') AS month, 
                           COUNT(DISTINCT customerID) AS total_customers
                       FROM orders
                       GROUP BY month;
                   """
    customer_growth = execute_query(customer_growth)
    kpis['CustomerGrowth'] = decimal_to_float(customer_growth)
    # Conversion Rate
    conversion_rate_query = """
            SELECT ROUND((COUNT(orderID) / COUNT(DISTINCT customerID)) * 100, 2) AS conversion_rate
            FROM orders;
        """
    conversion_rate = execute_query(conversion_rate_query)
    kpis['conversion_rate'] = decimal_to_float(conversion_rate)

    return jsonify(kpis)


@app.route('/kpi_reports', methods=['GET', 'POST'])
def kpi_reports():
    kpi_data = {}

    queries = {
        'average_order_value': """
                SELECT AVG(total) AS average_order_value
                FROM orders;
            """,
        'customer_retention_rate': """
                SELECT ROUND((COUNT(DISTINCT customerID) - COUNT(DISTINCT CASE WHEN DATEDIFF(CURDATE(), orderDate) <= 30 THEN customerID ELSE NULL END)) / COUNT(DISTINCT customerID) * 100, 2) AS retention_rate
                FROM orders;
            """,
        'order_frequency': """
                SELECT ROUND(AVG(order_count), 2) AS average_order_frequency
                FROM (
                    SELECT customerID, COUNT(orderID) AS order_count
                    FROM orders
                    GROUP BY customerID
                ) AS subquery;
            """,
        'conversion_rate': """
                SELECT ROUND((COUNT(orderID) / COUNT(DISTINCT customerID)) * 100, 2) AS conversion_rate
                FROM orders;
            """,
        'customer_growth': """
                           SELECT 
                               DATE_FORMAT(orderDate, '%Y-%m') AS month, 
                               COUNT(DISTINCT customerID) AS total_customers
                           FROM orders
                           GROUP BY month;
                       """

    }

    for kpi, query in queries.items():
        data = execute_query(query)
        kpi_data[kpi] = decimal_to_float(data)

    return render_template('kpi_reports.html', kpi_data=json.dumps(kpi_data))


@app.route('/analysis1', methods=['GET', 'POST'])
def analysis1_page():
    charts_data = {}

    for chart, query in queries.items():
        data = execute_query(query)
        charts_data[chart] = decimal_to_float(data)

    return render_template('melle.html', charts_data=json.dumps(charts_data))


@app.route('/states', methods=['GET'])
def get_states():
    query = "SELECT DISTINCT state FROM stores;"
    states = execute_query(query)
    states = [s[0] for s in states if s[0]]
    return jsonify(states)


@app.route('/filter', methods=['GET'])
def filter_data():
    chart = request.args.get('chart')
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')
    category = request.args.get('category')
    region = request.args.get('region')
    state = request.args.get('state')

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
        filters.append("s.state_abbr = %s")
        params.append(region)
    if state:
        filters.append("s.state = %s")
        params.append(state)

    filter_clause = " AND ".join(filters)
    if filter_clause:
        filter_clause = " WHERE " + filter_clause

    query_template = queries.get(chart)
    query = query_template.format(filter_clause=filter_clause)
    data = execute_query(query, params)
    return jsonify(decimal_to_float(data))


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
