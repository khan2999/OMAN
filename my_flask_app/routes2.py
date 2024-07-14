import json
import logging
import time
import mysql.connector
import plotly as pd
from flask import render_template, jsonify, request

from my_flask_app import app
from my_flask_app.db import get_db_connection

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Database connection
mydb = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    passwd="DBml##%%98",
    database="omanpl"
)


def get_data_from_db(query, params=None):
    try:
        mycursor = mydb.cursor()
        mycursor.execute(query, params)
        result = mycursor.fetchall()
        columns = mycursor.column_names
        mycursor.close()
        return pd.DataFrame(result, columns=columns)
    except mysql.connector.Error as err:
        logging.error(f"Error: {err}")
        return pd.DataFrame()


@app.route('/analysis2', methods=['GET', 'POST'])
def index():
    logging.debug("Rendering Pizza.html")
    return render_template('Pizza.html')


@app.route('/revenue', methods=['GET'])
def revenue():
    try:
        start_year = int(request.args.get('start_year', 2021))
        end_year = int(request.args.get('end_year', 2023))
        quarter = request.args.get('quarter', 'all')

        logging.debug(f"Parameters - Start Year: {start_year}, End Year: {end_year}, Quarter: {quarter}")

        if quarter == 'all':
            sql = """
            SELECT 
                YEAR(orderDate) AS year, 
                QUARTER(orderDate) AS quarter, 
                SUM(total) AS total_revenue
            FROM orders
            WHERE YEAR(orderDate) BETWEEN %s AND %s
            GROUP BY YEAR(orderDate), QUARTER(orderDate)
            ORDER BY YEAR(orderDate), QUARTER(orderDate);
            """
            params = (start_year, end_year)
        else:
            quarter = int(quarter)
            sql = """
            SELECT 
                YEAR(orderDate) AS year, 
                QUARTER(orderDate) AS quarter, 
                SUM(total) AS total_revenue
            FROM orders
            WHERE YEAR(orderDate) BETWEEN %s AND %s AND QUARTER(orderDate) = %s
            GROUP BY YEAR(orderDate), QUARTER(orderDate)
            ORDER BY YEAR(orderDate), QUARTER(orderDate);
            """
            params = (start_year, end_year, quarter)

        logging.debug(f"Executing SQL: {sql} with params: {params}")
        df = get_data_from_db(sql, params)
        revenue_data = df.to_dict(orient='records')
        logging.debug(f"Revenue Data: {revenue_data}")
        return jsonify(revenue_data)
    except Exception as e:
        logging.error(f"Error fetching revenue: {e}")
        return jsonify({'error': 'An error occurred while fetching the revenue.'}), 500


@app.route('/product_portfolio', methods=['GET'])
def product_portfolio():
    try:
        year = request.args.get('year', type=int)
        quarter = request.args.get('quarter', type=int)

        if year:
            if quarter:
                sql = f"""
                SELECT oi.SKU, p.Name AS product_name, COUNT(*) AS total_quantity_sold
                FROM orderitems oi
                JOIN products p ON oi.SKU = p.SKU
                JOIN orders o ON oi.orderID = o.orderID
                WHERE YEAR(o.orderDate) = {year} AND QUARTER(o.orderDate) = {quarter}
                GROUP BY oi.SKU, p.Name
                ORDER BY total_quantity_sold DESC
                LIMIT 10;
                """
            else:
                sql = f"""
                SELECT oi.SKU, p.Name AS product_name, COUNT(*) AS total_quantity_sold
                FROM orderitems oi
                JOIN products p ON oi.SKU = p.SKU
                JOIN orders o ON oi.orderID = o.orderID
                WHERE YEAR(o.orderDate) = {year}
                GROUP BY oi.SKU, p.Name
                ORDER BY total_quantity_sold DESC
                LIMIT 10;
                """
        else:
            sql = """
            SELECT oi.SKU, p.Name AS product_name, COUNT(*) AS total_quantity_sold
            FROM orderitems oi
            JOIN products p ON oi.SKU = p.SKU
            JOIN orders o ON oi.orderID = o.orderID
            WHERE YEAR(o.orderDate) >= YEAR(CURDATE()) - 2
            GROUP BY oi.SKU, p.Name
            ORDER BY total_quantity_sold DESC
            LIMIT 10;
            """

        df = get_data_from_db(sql)

        if df.empty:
            return jsonify({'error': 'No data found.'}), 404

        # Prepare data for charts
        labels = df['product_name'].tolist()
        data = df['total_quantity_sold'].tolist()

        return jsonify({
            'labels': labels,
            'data': data
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/product_sales_distribution', methods=['GET'])
def product_sales_distribution():
    try:
        product_name = request.args.get('product_name')
        if not product_name:
            return jsonify({'error': 'Product name is required'}), 400

        sql = """
        SELECT s.city, s.state, SUM(o.total) as total_sales
        FROM orderitems oi
        JOIN products p ON oi.SKU = p.SKU
        JOIN orders o ON oi.orderID = o.orderID
        JOIN stores s ON o.storeID = s.storeID
        WHERE p.Name = %s
        GROUP BY s.city, s.state
        ORDER BY total_sales DESC;
        """
        params = (product_name,)
        df = get_data_from_db(sql, params)

        if df.empty:
            return jsonify({'error': 'No data found.'}), 404

        sales_data = df.to_dict(orient='records')
        return jsonify(sales_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500



#show data after launch time

from datetime import datetime
from collections import defaultdict
@app.route('/sales_trends', methods=['GET'])
def sales_trends():
    try:
        cursor = mydb.cursor(dictionary=True)
        query = """
        SELECT
            p.Name AS product_name,
            YEAR(o.orderDate) AS year,
            MONTH(o.orderDate) AS month,
            SUM(o.total) AS total_sales
        FROM
            orders o
            JOIN orderitems oi ON o.orderID = oi.orderID
            JOIN products p ON oi.SKU = p.SKU
        WHERE
            o.orderDate >= p.Launch
        GROUP BY
            p.Name,
            YEAR(o.orderDate),
            MONTH(o.orderDate)
        ORDER BY
            p.Name,
            YEAR(o.orderDate),
            MONTH(o.orderDate);
        """

        cursor.execute(query)
        data = cursor.fetchall()

        # Prepare data for Chart.js
        labels = []
        datasets = []

        # Define a list of colors for the datasets
        colors = [
            'rgba(75, 192, 192, 1)', 'rgba(54, 162, 235, 1)', 'rgba(255, 99, 132, 1)',
            'rgba(255, 206, 86, 1)', 'rgba(153, 102, 255, 1)', 'rgba(255, 159, 64, 1)',
            'rgba(75, 192, 192, 0.5)', 'rgba(54, 162, 235, 0.5)', 'rgba(255, 99, 132, 0.5)'
        ]

        # Structure data for Chart.js datasets
        color_index = 0
        for product in data:
            label = f"{product['year']}-{product['month']:02}"
            if label not in labels:
                labels.append(label)

            # Find existing dataset or create a new one
            found = False
            for dataset in datasets:
                if dataset['label'] == product['product_name']:
                    dataset['data'].append(product['total_sales'])
                    found = True
                    break

            if not found:
                datasets.append({
                    'label': product['product_name'],
                    'data': [product['total_sales']],
                    'borderColor': colors[color_index % len(colors)],  # Assign color based on index
                    'backgroundColor': colors[color_index % len(colors)],
                    'borderWidth': 1,
                    'fill': False
                })
                color_index += 1

        # Pad data for missing months
        for dataset in datasets:
            data_length = len(dataset['data'])
            while data_length < len(labels):
                dataset['data'].insert(data_length, 0)
                data_length += 1

        # Prepare data for JSON response
        chart_data = {
            'labels': labels,
            'datasets': datasets
        }

        return jsonify(chart_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/order_fulfillment', methods=['GET'])
def order_fulfillment():
    try:
        cursor = mydb.cursor(dictionary=True)
        query = """
        SELECT
            o.orderID,
            o.customerID,
            o.storeID,
            o.orderDate,
            s.city,
            s.state
        FROM
            orders o
            JOIN stores s ON o.storeID = s.storeID;
        """
        cursor.execute(query)
        data = cursor.fetchall()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/delivery_optimization', methods=['GET'])
def delivery_optimization():
    try:
        cursor = mydb.cursor(dictionary=True)
        query = """
        SELECT
            o.orderID,
            o.orderDate,
            c.latitude AS customer_latitude,
            c.longitude AS customer_longitude,
            s.latitude AS store_latitude,
            s.longitude AS store_longitude
        FROM
            orders o
            JOIN customers c ON o.customerID = c.customerID
            JOIN stores s ON o.storeID = s.storeID;
        """
        cursor.execute(query)
        data = cursor.fetchall()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/pizza_types')
def pizza_types():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT DISTINCT Name FROM products")
        result = cursor.fetchall()
        cursor.close()
        connection.close()
        return jsonify([row[0] for row in result])
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/sales_per_cost')
def sales_per_cost():
    pizza_type = request.args.get('pizza_type')
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        query = """SELECT p.size AS size, COUNT(oi.SKU) AS total_quantity
        FROM orderitems oi
        JOIN products p ON oi.SKU = p.SKU
        WHERE p.Name = %s
        GROUP BY p.size
        ORDER BY FIELD(p.size, 'Small', 'Medium', 'Large', 'Extra Large')
        """
        cursor.execute(query, (pizza_type,))
        result = cursor.fetchall()
        cursor.close()
        connection.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/product_popularity')
def product_popularity():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    query = """
    SELECT p.Name AS product_name, COUNT(oi.SKU) AS total_quantity
    FROM orderitems oi
    JOIN products p ON oi.SKU = p.SKU
    GROUP BY p.Name
    ORDER BY total_quantity DESC
    """
    cursor.execute(query)
    result = cursor.fetchall()

    # Assign star ratings based on rank and
    max_rank = len(result)
    for i, row in enumerate(result):
        if max_rank > 1:
            row['popularity'] = round(1 + 4 * (max_rank - i - 1) / (max_rank - 1))
        else:
            row['popularity'] = 5

    cursor.close()
    connection.close()
    return jsonify(result)


if __name__ == '__main__':
    logging.debug("Starting Flask app")
    app.run(debug=True)
