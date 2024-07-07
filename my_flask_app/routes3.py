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
        logging.error(f"Error: {err}")
        return []


def process_data(orders):
    customer_order_count = {}
    for order in orders:
        customer_id = order['customerID']
        if customer_id in customer_order_count:
            customer_order_count[customer_id] += 1
        else:
            customer_order_count[customer_id] = 1

    one_time_customers = sum(1 for count in customer_order_count.values() if count == 1)
    multiple_customers = sum(1 for count in customer_order_count.values() if 2 <= count < 10)
    vip_customers = sum(1 for count in customer_order_count.values() if count >= 10)

    one_time_orders = sum(count for count in customer_order_count.values() if count == 1)
    multiple_orders = sum(count for count in customer_order_count.values() if 2 <= count < 10)
    vip_orders = sum(count for count in customer_order_count.values() if count >= 10)

    return {
        "categories": [
            {"name": "Walk-ins", "customers": one_time_customers, "orders": one_time_orders},
            {"name": "Regulars", "customers": multiple_customers, "orders": multiple_orders},
            {"name": "VIPs", "customers": vip_customers, "orders": vip_orders}
        ]
    }


def get_products_for_category(category, start_year, end_year):
    try:
        mycursor = mydb.cursor(dictionary=True)

        # Define category conditions based on the category name
        category_conditions = {
            'Walk-ins': 'HAVING order_count = 1',
            'Regulars': 'HAVING order_count BETWEEN 2 AND 9',
            'VIPs': 'HAVING order_count >= 10'
        }

        # Select the appropriate condition based on the category name
        category_condition = category_conditions.get(category, '')

        # Debugging: Print the selected category and condition
        logging.debug(f"Selected Category: {category}")
        logging.debug(f"Category Condition: {category_condition}")

        # Build the SQL query with the category condition
        query = f'''
                    SELECT products.Name, SUM(orders.nItems) as count
            FROM products
            JOIN orderitems ON products.SKU = orderitems.SKU
            JOIN orders ON orderitems.orderID = orders.orderID
            JOIN (
                SELECT customerID, COUNT(orderID) as order_count
                FROM orders
                WHERE orderDate BETWEEN %s AND %s
                GROUP BY customerID
                {category_condition}
            ) as customer_orders ON orders.customerID = customer_orders.customerID
            WHERE orders.orderDate BETWEEN %s AND %s
            GROUP BY products.Name
        '''

        # Execute the query with the start and end year as parameters
        params = (f"{start_year}-01-01", f"{end_year}-12-31", f"{start_year}-01-01", f"{end_year}-12-31")

        # Debugging: Print the query and params
        logging.debug(f"SQL Query: {query}")
        logging.debug(f"Params: {params}")

        mycursor.execute(query, params)
        products = mycursor.fetchall()
        mycursor.close()

        # Debugging: Print the fetched products
        app.logger.debug(f"Fetched Products: {products}")

        # Return the products
        return [{'Name': product['Name'], 'count': product['count']} for product in products]
    except mysql.connector.Error as err:
        logging.error(f"Error: {err}")
        return []


@app.route('/order_analysis', methods=['GET', 'POST'])
def analysis3_page():
    if request.method == 'POST':
        start_year = int(request.form.get('startYear'))
        end_year = int(request.form.get('endYear'))
        if 2020 <= start_year <= 2023 and 2020 <= end_year <= 2023:
            orders = get_order_data(start_year, end_year)
            data = process_data(orders)
            return jsonify(data)
    return render_template('order_analysis.html')


@app.route('/products_for_category', methods=['GET'])
def products_for_category():
    category = request.args.get('category')
    start_year = request.args.get('startYear')
    end_year = request.args.get('endYear')
    products = get_products_for_category(category, start_year, end_year)
    return jsonify(products)


if __name__ == '__main__':
    app.run(debug=True)
