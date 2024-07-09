import locale
from flask import render_template, request, jsonify, send_from_directory
from my_flask_app import app
from my_flask_app.db import get_db_connection,  execute_query
import mysql.connector
import logging
import os
import geopy.distance
import psycopg2


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/analysis', methods=['GET', 'POST'])
def analysis_page():
    data = None

    if request.method == 'POST':
        selected_table = request.form['table']
        selected_column = request.form['column']

        query = f"SELECT {selected_column} FROM {selected_table};"
        data = execute_query(query)

    return render_template('index.html', data=data)

@app.route('/stores', methods=['GET'])
def get_stores():
    query = """
        SELECT 
            s.storeID, 
            s.latitude, 
            s.longitude, 
            s.city, 
            s.state, 
            YEAR(o.orderDate) as year, 
            MONTH(o.orderDate) as month,
            COALESCE(ROUND(SUM(o.total), 2), 0) as total
        FROM stores s
        LEFT JOIN orders o ON s.storeID = o.storeID
        GROUP BY s.storeID, s.latitude, s.longitude, s.city, s.state, YEAR(o.orderDate), MONTH(o.orderDate)
        ORDER BY s.storeID, year, month
    """
    stores = execute_query(query)
    return jsonify(stores if stores else {"error": "Error fetching stores data"})

@app.route('/customers/<storeID>', methods=['GET'])
def get_customer_counts(storeID):
    query = """
        SELECT 
            YEAR(o.orderDate) as year, 
            MONTH(o.orderDate) as month,
            COUNT(DISTINCT o.customerID) as customer_count
        FROM orders o
        WHERE o.storeID = %s
        GROUP BY YEAR(o.orderDate), MONTH(o.orderDate)
        ORDER BY year, month
    """
    customer_counts = execute_query(query, (storeID,))
    return jsonify(customer_counts if customer_counts else {"error": "Error fetching customer counts data"})

@app.route('/orders/monthly/<storeID>', methods=['GET'])
def get_monthly_order_counts(storeID):
    query = """
        SELECT 
            YEAR(o.orderDate) as year, 
            MONTH(o.orderDate) as month,
            COUNT(o.orderID) as order_count
        FROM orders o
        WHERE o.storeID = %s
        GROUP BY YEAR(o.orderDate), MONTH(o.orderDate)
        ORDER BY year, month
    """
    order_counts = execute_query(query, (storeID,))
    return jsonify(order_counts if order_counts else {"error": "Error fetching monthly order counts data"})

@app.route('/orders/yearly/<storeID>', methods=['GET'])
def get_yearly_order_counts(storeID):
    query = """
        WITH yearly_counts AS (
            SELECT 
                YEAR(o.orderDate) AS year, 
                COUNT(o.orderID) AS order_count
            FROM orders o
            WHERE o.storeID = %s
            GROUP BY YEAR(o.orderDate)
            ORDER BY YEAR(o.orderDate)
        )
        SELECT 
            year,
            order_count,
            COALESCE(order_count - LAG(order_count) OVER (ORDER BY year), 0) AS delta
        FROM yearly_counts;
    """
    order_counts = execute_query(query, (storeID,))
    return jsonify(order_counts if order_counts else {"error": "Error fetching yearly order counts data"})

@app.route('/average_spending/<storeID>', methods=['GET'])
def get_average_spending(storeID):
    query = """
        SELECT 
            YEAR(o.orderDate) as year, 
            MONTH(o.orderDate) as month,
            SUM(o.total) / COUNT(DISTINCT o.customerID) as avg_spending
        FROM orders o
        WHERE o.storeID = %s
        GROUP BY YEAR(o.orderDate), MONTH(o.orderDate)
        ORDER BY year, month
    """
    avg_spending = execute_query(query, (storeID,))
    return jsonify(avg_spending if avg_spending else {"error": "Error fetching average spending data"})

@app.route('/customers_by_distance', methods=['POST'])
def get_customers_by_distance():
    stores = request.json.get('stores', [])
    selected_year = request.json.get('year', None)

    distances = {}

    for storeID in stores:
        query = """
            WITH CustomerDistances AS (
                SELECT 
                    c.customerID,
                    c.latitude AS customer_latitude,
                    c.longitude AS customer_longitude,
                    o.storeID,
                    YEAR(o.orderDate) AS year,
                    COUNT(o.orderID) AS order_count
                FROM customers c
                JOIN orders o ON c.customerID = o.customerID
                WHERE o.storeID = %s
                GROUP BY c.customerID, c.latitude, c.longitude, o.storeID, YEAR(o.orderDate)
            ),
            Distances AS (
                SELECT 
                    cd.storeID,
                    cd.year,
                    cd.order_count,
                    cd.customer_latitude,
                    cd.customer_longitude,
                    st.latitude AS store_latitude,
                    st.longitude AS store_longitude,
                    (6371 * acos(
                        cos(radians(st.latitude)) * cos(radians(cd.customer_latitude)) * 
                        cos(radians(cd.customer_longitude) - radians(st.longitude)) + 
                        sin(radians(st.latitude)) * sin(radians(cd.customer_latitude))
                    )) AS distance_km
                FROM CustomerDistances cd
                JOIN stores st ON cd.storeID = st.storeID
            )
            SELECT 
                year,
                SUM(CASE WHEN distance_km <= 4 THEN order_count ELSE 0 END) AS '0-2 km',
                SUM(CASE WHEN distance_km > 4 AND distance_km <= 10 THEN order_count ELSE 0 END) AS '2-5 km',
                SUM(CASE WHEN distance_km > 10 THEN order_count ELSE 0 END) AS '>5 km'
            FROM Distances
            WHERE year = %s
            GROUP BY year
            ORDER BY year;
        """
        customer_distances = execute_query(query, (storeID, selected_year))

        if not customer_distances:
            continue

        distances[storeID] = customer_distances[0]

    print(f"Distances data: {distances}")  # Debugging
    return jsonify(distances)

@app.route('/cross_sell_analysis/<storeID>', methods=['GET'])
def get_cross_sell_analysis(storeID):
    year = request.args.get('year')
    query = """
    WITH ProductPairs AS (
        SELECT 
            o.storeID,
            YEAR(o.orderDate) AS year,
            p1.Name AS product1_name,
            p2.Name AS product2_name,
            COUNT(*) AS count
        FROM orders o
        JOIN orderItems oi1 ON o.orderID = oi1.orderID
        JOIN orderItems oi2 ON o.orderID = oi2.orderID AND oi1.SKU < oi2.SKU
        JOIN products p1 ON oi1.SKU = p1.SKU
        JOIN products p2 ON oi2.SKU = p2.SKU
        WHERE o.storeID = %s
        """ + (" AND YEAR(o.orderDate) = %s" if year else "") + """
        GROUP BY o.storeID, YEAR(o.orderDate), p1.Name, p2.Name
    ),
    RankedProductPairs AS (
        SELECT 
            *,
            ROW_NUMBER() OVER (PARTITION BY product1_name, year ORDER BY count DESC) AS product_rank
        FROM ProductPairs
    )
    SELECT 
        storeID,
        year,
        product1_name,
        product2_name,
        count
    FROM RankedProductPairs
    WHERE product_rank = 1
    ORDER BY storeID, year, count DESC;
    """
    params = (storeID, year) if year else (storeID,)
    try:
        cross_sell_data = execute_query(query, params)
        if cross_sell_data:
            return jsonify(cross_sell_data)
        else:
            return jsonify({"error": "No data found"})
    except Exception as e:
        print(f"Error fetching cross sell analysis data for Store {storeID} and Year {year}: {e}")
        return jsonify({"error": "Error fetching cross sell analysis data"})


@app.route('/customerscount/<storeID>', methods=['GET'])
def get_customers(storeID):
    year = request.args.get('year')
    query = """
    SELECT storeID, YEAR(orderDate) AS year, COUNT(DISTINCT customerID) AS customer_count
    FROM orders
    WHERE storeID = %s
    """ + (" AND YEAR(orderDate) = %s" if year else "") + """
    GROUP BY storeID, YEAR(orderDate)
    """
    params = (storeID, year) if year else (storeID,)
    customer_data = execute_query(query, params)

    print(f"Customer data für Store {storeID} und Jahr {year}: {customer_data}")

    return jsonify(customer_data if customer_data else {"error": "Error fetching customer data"})


@app.route('/orderscount/<storeID>', methods=['GET'])
def get_orders(storeID):
    year = request.args.get('year')
    query = """
    SELECT storeID, YEAR(orderDate) AS year, COUNT(*) AS order_count
    FROM orders
    WHERE storeID = %s
    """ + (" AND YEAR(orderDate) = %s" if year else "") + """
    GROUP BY storeID, YEAR(orderDate)
    """
    params = (storeID, year) if year else (storeID,)
    order_data = execute_query(query, params)

    print(f"Order data für Store {storeID} und Jahr {year}: {order_data}")

    return jsonify(order_data if order_data else {"error": "Error fetching order data"})
