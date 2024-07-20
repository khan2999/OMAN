import json
import re
from collections import defaultdict
from decimal import Decimal
from math import radians, cos, sin, asin, sqrt
import mysql.connector
import plotly.graph_objects as go
import plotly.io as pio
from flask import jsonify
from flask import render_template, request
from my_flask_app import app
from my_flask_app.db import get_db_connection
import logging

logging.basicConfig(level=logging.DEBUG)

# Database connection
mydb = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    passwd="DBml##%%98",
    database="omanpl"
)


# Execute a query against the database
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


# Convert decimal values in data to float
def decimal_to_float(data):
    if data is None:
        return []
    if isinstance(data, list):
        return [[round(float(item), 2) if isinstance(item, Decimal) else item for item in row] for row in data]
    elif isinstance(data, Decimal):
        return float(data)
    return data


# Predefined SQL queries for the first 7 charts
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
    'customer_growth': """
            SELECT DATE_FORMAT(orderDate, '%Y-%m') AS month, COUNT(DISTINCT customerID) AS total_customers
            FROM orders o
            JOIN stores s ON o.storeID = s.storeID
            {filter_clause}
            GROUP BY month;
        """,
    'average_order_value': """
            SELECT AVG(total) AS average_order_value
            FROM orders o
            JOIN stores s ON o.storeID = s.storeID
            {filter_clause};
        """,
    'product_details': """
    SELECT p.SKU, p.Name, p.Price, p.Category, p.Size, p.Ingredients, p.Launch
    FROM products p
    {filter_clause}
    """,

}


# Endpoint to fetch drill-down data based on query parameters
@app.route('/drilldown', methods=['GET'])
def drilldown_data():
    try:
        # Determine drill-down type based on query parameters
        category = request.args.get('category')
        product_name = request.args.get('product_name')
        store_id = request.args.get('store_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        customer_id = request.args.get('customer_id')
        region = request.args.get('region')

        if category:
            # Drill down by category
            query = """
            SELECT p.Name, SUM(o.nItems) AS total_quantity_sold
            FROM orderItems oi
            JOIN products p ON oi.SKU = p.SKU
            JOIN orders o ON oi.orderID = o.orderID
            WHERE p.Category = %s
            GROUP BY p.Name
            ORDER BY total_quantity_sold DESC;
            """
            params = (category,)
        elif product_name:
            # Drill down to product details
            query = """
            SELECT SKU, Name, Price, Category, Size, Ingredients, Launch
            FROM products
            WHERE Name = %s;
            """
            params = (product_name,)
        elif store_id:
            # Drill down by store
            query = """
            SELECT p.Name, SUM(o.nItems) AS total_quantity_sold, SUM(o.total) AS total_sales
            FROM orderItems oi
            JOIN products p ON oi.SKU = p.SKU
            JOIN orders o ON oi.orderID = o.orderID
            WHERE o.storeID = %s
            GROUP BY p.Name
            ORDER BY total_sales DESC;
            """
            params = (store_id,)
        elif start_date and end_date:
            # Drill down by date range
            query = """
            SELECT p.Name, SUM(o.nItems) AS total_quantity_sold, SUM(o.total) AS total_sales
            FROM orderItems oi
            JOIN products p ON oi.SKU = p.SKU
            JOIN orders o ON oi.orderID = o.orderID
            WHERE o.orderDate BETWEEN %s AND %s
            GROUP BY p.Name
            ORDER BY total_sales DESC;
            """
            params = (start_date, end_date)
        elif customer_id:
            # Drill down by customer
            query = """
            SELECT p.Name, SUM(o.nItems) AS total_quantity_sold, SUM(o.total) AS total_spent
            FROM orderItems oi
            JOIN products p ON oi.SKU = p.SKU
            JOIN orders o ON oi.orderID = o.orderID
            WHERE o.customerID = %s
            GROUP BY p.Name
            ORDER BY total_spent DESC;
            """
            params = (customer_id,)
        elif region:
            # Drill down by region
            query = """
            SELECT p.Name, SUM(o.nItems) AS total_quantity_sold, SUM(o.total) AS total_sales
            FROM orderItems oi
            JOIN products p ON oi.SKU = p.SKU
            JOIN orders o ON oi.orderID = o.orderID
            JOIN stores s ON o.storeID = s.storeID
            WHERE s.region = %s
            GROUP BY p.Name
            ORDER BY total_sales DESC;
            """
            params = (region,)
        else:
            logging.debug("Invalid drill-down parameters")
            return jsonify({"error": "Invalid drill-down parameters"}), 400

        # Log the query and params
        logging.debug("Executing query: %s with params: %s", query, params)

        # Execute query and fetch results
        data = execute_query(query, params)

        # Log the raw data
        logging.debug("Raw data fetched: %s", data)

        # Convert decimals to floats
        formatted_data = decimal_to_float(data)

        # Log the formatted data
        logging.debug("Formatted data: %s", formatted_data)

        # Return results in JSON format
        return jsonify(formatted_data)

    except Exception as e:
        logging.error("Error in drilldown_data: %s", e)
        return jsonify({"error": str(e)}), 500


# Fetch data from the database and return columns and results
def fetch_data(query):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    columns = [column[0] for column in cursor.description]
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return columns, results


# Render the KPI report page
@app.route('/Kpi_Report')
def index2():
    return render_template('Kpi_Report.html')


# Endpoint for new vs. returning customers pie chart
@app.route('/api/new_vs_returning_customers')
def new_vs_returning_customers():
    try:
        columns, results = fetch_data(
            """
            SELECT SUM(is_new_customer) AS new_customers, SUM(NOT is_new_customer) AS returning_customers
            FROM (
                SELECT customers.customerID, MAX(CASE WHEN orders.orderID IS NULL THEN 1 ELSE 0 END) AS is_new_customer
                FROM customers
                LEFT JOIN orders ON customers.customerID = orders.customerID
                GROUP BY customers.customerID
            ) AS customer_status;
            """
        )
        labels = [columns[0], columns[1]]
        values = [results[0][0], results[0][1]]
        fig = go.Figure(data=[go.Pie(labels=labels, values=values)])
        fig.update_layout(title="New vs. Returning Customers")
        return jsonify(pio.to_json(fig, pretty=True))
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching new vs returning customers data: {error}")
        return jsonify({"error": "Database error"}), 500


# Endpoint for popular Products
@app.route('/api/popular_products')
def popular_products():
    try:
        columns, results = fetch_data(
            """
            SELECT products.Name, COUNT(orderitems.SKU) AS frequency
            FROM orderitems
            JOIN products ON orderitems.SKU = products.SKU
            GROUP BY products.Name
            ORDER BY frequency DESC;
            """
        )
        x_values = [row[0] for row in results]
        y_values = [row[1] for row in results]
        fig = go.Figure(data=[go.Bar(x=x_values, y=y_values)])
        fig.update_layout(xaxis_title=columns[0], yaxis_title=columns[1], title='Popular Products')
        return jsonify(pio.to_json(fig, pretty=True))
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching popular products data: {error}")
        return jsonify({"error": "Database error"}), 500


# Endpoint to fetch and visualize revenue growth over time
@app.route('/api/revenue_growth')
def revenue_growth():
    try:
        columns, results = fetch_data(
            """
            SELECT DATE_FORMAT(orderDate, '%Y-%m') AS month,
                   SUM(total) AS total_revenue,
                   (SUM(total) - LAG(SUM(total), 1, 0) OVER (ORDER BY DATE_FORMAT(orderDate, '%Y-%m'))) /
                   LAG(SUM(total), 1, 0) OVER (ORDER BY DATE_FORMAT(orderDate, '%Y-%m')) * 100 AS revenue_growth
            FROM orders
            GROUP BY DATE_FORMAT(orderDate, '%Y-%m');
            """
        )
        x_values = [row[0] for row in results]
        y_values_revenue = [row[1] for row in results]
        y_values_growth = [row[2] for row in results]

        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_values, y=y_values_revenue, name='Total Revenue'))
        fig.add_trace(go.Scatter(x=x_values, y=y_values_growth, name='Revenue Growth %'))
        fig.update_layout(title='Revenue Growth Over Time',
                          yaxis2=dict(title='Revenue Growth %', overlaying='y', side='right'))
        return jsonify(pio.to_json(fig, pretty=True))
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching revenue growth data: {error}")
        return jsonify({"error": "Database error"}), 500


# Endpoint to calculate and return conversion rate
@app.route('/api/conversion_rate')
def conversion_rate():
    try:
        columns, results = fetch_data(
            """
            SELECT COUNT(DISTINCT orders.customerID) / COUNT(DISTINCT customers.customerID) * 100 AS conversion_rate
            FROM customers
            LEFT JOIN orders ON customers.customerID = orders.customerID;
            """
        )
        value = results[0][0]  # Get the conversion rate from the results
        data = [{"date": "Current", "conversion_rate": value}]  # Return a single data point
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching conversion rate data: {error}")
        return jsonify({"error": "Database error"}), 500


# Endpoint to get order frequency for top 10 customers
@app.route('/api/order_frequency')
def order_frequency():
    try:
        columns, results = fetch_data(
            """
            SELECT customerID, COUNT(orderID) AS order_frequency
            FROM orders
            GROUP BY customerID
            ORDER BY order_frequency DESC
            LIMIT 10;
            """
        )
        x_values = [row[0] for row in results]
        y_values = [row[1] for row in results]
        fig = go.Figure(data=[go.Bar(x=x_values, y=y_values)])
        fig.update_layout(xaxis_title=columns[0], yaxis_title=columns[1], title='Top 10 Customers by Order Frequency')
        return jsonify(pio.to_json(fig, pretty=True))
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching order frequency data: {error}")
        return jsonify({"error": "Database error"}), 500


# Endpoint to render analysis page
@app.route('/analysis1', methods=['GET', 'POST'])
def analysis1_page():
    charts_data = {}

    for chart, query in queries.items():
        data = execute_query(query)
        charts_data[chart] = decimal_to_float(data)

    return render_template('melle.html', charts_data=json.dumps(charts_data))


# Endpoint to get list of states
@app.route('/states', methods=['GET'])
def get_states():
    query = "SELECT DISTINCT state FROM stores;"
    states = execute_query(query)
    states = [s[0] for s in states if s[0]]  # Extract state names from the result set

    return jsonify(states)


# Utility function to validate date format
def validate_date(date_str):
    """Validate date format (YYYY-MM-DD)."""
    return re.match(r'^\d{4}-\d{2}-\d{2}$', date_str) is not None


# Endpoint to filter data based on multiple criteria
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


# Endpoint to render charts page (sales insight Dashboard)
@app.route('/charts')
def charts_page():
    return render_template('extra_charts.html')


# Endpoint to get sales data by day of week
@app.route('/api/sales_by_day_of_week')
def sales_by_day_of_week():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT DAYNAME(o.orderDate) AS day_of_week, SUM(o.total) AS total_sales
            FROM orders o
            GROUP BY day_of_week
            ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday');
        ''')
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching sales by day of week data: {error}")
        return jsonify({"error": "Database error"}), 500


# Endpoint to get product size sales data
@app.route('/api/product_size_sales')
def product_size_sales():
    try:
        conn = get_db_connection()  # Replace with your DB connection function
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
           SELECT p.Size, SUM(o.nItems) AS total_quantity_sold 
            FROM Orders o
            JOIN OrderItems oi ON o.orderID = oi.orderID 
            JOIN Products p ON oi.SKU = p.SKU
            GROUP BY p.Size;
        ''')
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:  # Adjust error handling to your connector
        app.logger.error(f"Error fetching product size sales data: {error}")
        return jsonify({"error": "Database error"}), 500


# Utility function to calculate Haversine distance between two geographical points
def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the Haversine distance between two geographical points.
    Args:
        lat1, lon1: Latitude and Longitude of the first point.
        lat2, lon2: Latitude and Longitude of the second point.
    Returns:
        Distance between the two points in kilometers.
    """
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r


# Endpoint to perform distance analysis between stores and customers
@app.route('/api/distance_analysis')
def distance_analysis():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT 
                o.customerID, 
                SUM(o.total) AS total_sales,
                COUNT(o.orderID) AS order_frequency,
                ANY_VALUE(s.latitude) AS store_lat,  
                ANY_VALUE(s.longitude) AS store_lon,
                ANY_VALUE(c.latitude) AS customer_lat, 
                ANY_VALUE(c.longitude) AS customer_lon
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
                'order_frequency': row['order_frequency'],
                'total_sales': row['total_sales']
            })

        # Define bins for distance ranges
        distance_bins = [i for i in range(0, 55, 5)]
        binned_data = defaultdict(lambda: {'order_frequency': [], 'total_sales': []})

        # Bin the data based on distance ranges
        for d in data:
            for i in range(len(distance_bins) - 1):
                if distance_bins[i] <= d['distance'] < distance_bins[i + 1]:
                    bin_key = f"{distance_bins[i]}-{distance_bins[i + 1]}"
                    binned_data[bin_key]['order_frequency'].append(d['order_frequency'])
                    binned_data[bin_key]['total_sales'].append(d['total_sales'])
                    break

        # Calculate mean and standard deviation for each bin
        aggregate_data = []
        for bin_key, bin_data in binned_data.items():
            order_frequency_mean = sum(bin_data['order_frequency']) / len(bin_data['order_frequency'])
            order_frequency_std = sqrt(sum((x - order_frequency_mean) ** 2 for x in bin_data['order_frequency']) / len(
                bin_data['order_frequency']))
            total_sales_mean = sum(bin_data['total_sales']) / len(bin_data['total_sales'])
            total_sales_std = sqrt(
                sum((x - total_sales_mean) ** 2 for x in bin_data['total_sales']) / len(bin_data['total_sales']))
            aggregate_data.append({
                'distance_bin': bin_key,
                'order_frequency_mean': order_frequency_mean,
                'order_frequency_std': order_frequency_std,
                'total_sales_mean': total_sales_mean,
                'total_sales_std': total_sales_std
            })

        cursor.close()
        conn.close()
        return jsonify(aggregate_data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching distance analysis data: {error}")
        return jsonify({"error": "Database error"}), 500


# Endpoint to get the performance of stores by product category
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


# Endpoint to compare performance of stores
@app.route('/api/store_performance_comparison')
def store_performance_comparison():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT s.storeID,
            SUM(o.total) AS total_sales,
            COUNT(o.orderID) AS num_orders,
            AVG(o.total) AS average_order_value
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


# Endpoint to segment customers based on their spending and order frequency
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
            FROM Orders o
            JOIN Customers c ON o.customerID = c.customerID
            JOIN Stores s ON o.storeID = s.storeID
            GROUP BY c.customerID, s.state_abbr, s.city
            ORDER BY total_spend DESC;
        ''')
        data = cursor.fetchall()
        cursor.close()
        conn.close()

        for entry in data:
            entry['spend_per_order'] = entry['total_spend'] / entry['num_orders'] if entry['num_orders'] else 0

        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error fetching customer segmentation data: {error}")
        return jsonify({"error": "Database error"}), 500


# Endpoint to calculate inventory turnover rate
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


# Endpoint to filter store performance by category
@app.route('/api/filter_store_performance_by_category', methods=['GET', 'POST'])
def filter_store_performance_by_category():
    try:
        if request.method == 'POST':
            data = request.get_json()
            store_id = data.get('store_id')
            category = data.get('category')
        else:
            store_id = request.args.get('store_id')
            category = request.args.get('category')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = '''
            SELECT s.storeID, p.Category, 
            SUM(o.nItems) AS total_quantity_sold
            FROM OrderItems oi 
            JOIN Products p ON oi.SKU = p.SKU 
            JOIN Orders o ON oi.orderID = o.orderID 
            JOIN Stores s ON o.storeID = s.storeID
            WHERE 1=1
        '''
        params = []
        if store_id:
            query += ' AND s.storeID = %s'
            params.append(store_id)
        if category:
            query += ' AND p.Category = %s'
            params.append(category)
        query += ' GROUP BY s.storeID, p.Category ORDER BY total_quantity_sold DESC;'

        cursor.execute(query, params)
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as error:
        app.logger.error(f"Error filtering store performance by category data: {error}")
        return jsonify({"error": "Database error"}), 500


# Main entry point for the application
if __name__ == '__main__':
    logging.debug("Starting Flask app")
    app.run(debug=True)
