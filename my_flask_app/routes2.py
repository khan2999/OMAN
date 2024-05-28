import flask

from flask import Flask, render_template, jsonify, request
from my_flask_app.db import get_db_connection
from my_flask_app import app
import pandas as pd
import mysql.connector
import logging




# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Database connection
mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    passwd="password",
    database="Pizza"
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

@app.route('/product_portfolio', methods=['GET', 'POST'])
def product_portfolio():
    try:
        year = request.args.get('year', type=int)
        quarter = request.args.get('quarter', type=int)

        logging.debug(f"Parameters - Year: {year}, Quarter: {quarter}")

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

        logging.debug(f"Executing SQL: {sql}")
        df = get_data_from_db(sql)
        logging.debug(f"DataFrame: {df}")
        if df.empty:
            logging.debug("No data found.")
        columns = df.columns.values
        data = df.values.tolist()
        logging.debug(f"Product Portfolio Data: {data}")
        table_html = render_template('product_portfolio.html', columns=columns, data=data)
        return table_html
    except Exception as e:
        logging.error(f"Error fetching product portfolio: {e}")
        return jsonify({'error': 'An error occurred while fetching the product portfolio.'}), 500

if __name__ == '__main__':
    logging.debug("Starting Flask app")
    app.run(debug=True)
