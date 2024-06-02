import logging
import mysql.connector
from flask import render_template, request, jsonify
from my_flask_app import app

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Database connection
mydb = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    passwd="password",
    database="pizza"
)


def get_order_data(start_year, end_year):
    try:
        mycursor = mydb.cursor(dictionary=True)
        query = "SELECT * FROM orders WHERE orderDate BETWEEN %s AND %s"
        params = (f"{start_year}-01-01", f"{end_year}-12-31")
        mycursor.execute(query, params)
        orders = mycursor.fetchall()
        mycursor.close()
        return orders
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return []


def process_data(orders):
    unique_customers = set()
    multiple_customers = set()
    for order in orders:
        customer_id = order['customerID']
        if customer_id in unique_customers:
            multiple_customers.add(customer_id)
        else:
            unique_customers.add(customer_id)
    one_time_customers = unique_customers - multiple_customers
    return len(one_time_customers), len(multiple_customers)


@app.route('/order_analysis', methods=['GET', 'POST'])
def analysis3_page():
    data = []  # Initialize data to an empty list for GET requests
    if request.method == 'POST':
        start_year = int(request.form.get('startYear'))
        end_year = int(request.form.get('endYear'))
        if 2020 <= start_year <= 2023 and 2020 <= end_year <= 2023:
            orders = get_order_data(start_year, end_year)
            one_time_customers_count, multiple_customers_count = process_data(orders)
            data = [
                {'value': one_time_customers_count, 'name': 'Einmalige Bestellungen'},
                {'value': multiple_customers_count, 'name': 'Mehrfache Bestellungen'}
            ]
            return jsonify(data)
    return render_template('order_analysis.html', data=data)


if __name__ == '__main__':
    app.run(debug=True)
