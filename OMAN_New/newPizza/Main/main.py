from flask import Flask, render_template, request
import mysql.connector
import json
from decimal import Decimal

app = Flask(__name__)

def execute_query(query):
    try:
        # Connect to MySQL database
        mydb = mysql.connector.connect(
            host="localhost",
            user="root",
            password="DBml##%%98",
            database="omanpl"
        )

        # Create a cursor object to execute SQL queries
        cursor = mydb.cursor()

        # Execute SQL query
        cursor.execute(query)
        data = cursor.fetchall()  # Fetch all rows

        # Close cursor and database connection
        cursor.close()
        mydb.close()

        return data

    except mysql.connector.Error as error:
        print(f"Error connecting to MySQL database: {error}")
        return None

def decimal_to_float(data):
    if data is None:
        return []
    return [[round(float(item), 3) if isinstance(item, Decimal) else item for item in row] for row in data]

@app.route('/', methods=['GET', 'POST'])
def index():
    charts_data = {}

    # Fetch data for each chart
    queries = {
        'total_sales_by_category': """
            SELECT p.Category, SUM(p.Price * o.nItems) AS total_sales
            FROM orderItems oi
            JOIN products p ON oi.SKU = p.SKU
            JOIN orders o ON oi.orderID = o.orderID
            GROUP BY p.Category;
        """,
        'sales_trends_over_time': """
            SELECT YEAR(orderDate) AS year, MONTH(orderDate) AS month, SUM(total) AS total_sales
            FROM orders
            GROUP BY YEAR(orderDate), MONTH(orderDate)
            ORDER BY YEAR(orderDate), MONTH(orderDate);
        """,
        'top_selling_products': """
            SELECT p.Name, SUM(o.nItems) AS total_quantity_sold
            FROM orderItems oi
            JOIN products p ON oi.SKU = p.SKU
            JOIN orders o ON oi.orderID = o.orderID
            GROUP BY p.Name
            ORDER BY total_quantity_sold DESC
            LIMIT 10;
        """,
        'customer_distribution': """
            SELECT s.state_abbr, COUNT(c.customerID) AS customer_count
            FROM customers c
            JOIN orders o ON c.customerID = o.customerID
            JOIN stores s ON o.storeID = s.storeID
            GROUP BY s.state_abbr;
        """,
        'average_order_value': """
            SELECT AVG(total) AS average_order_value
            FROM orders;
        """
    }

    for chart, query in queries.items():
        data = execute_query(query)
        charts_data[chart] = decimal_to_float(data)

    return render_template('index.html', charts_data=json.dumps(charts_data))

if __name__ == '__main__':
    app.run(debug=True)
