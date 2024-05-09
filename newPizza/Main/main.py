from flask import Flask, render_template, request
import mysql.connector

app = Flask(__name__)

# Route to render the index.html template
@app.route('/', methods=['GET', 'POST'])
def index():
    data = None  # Initialize data variable

    if request.method == 'POST':
        # Handle POST request to fetch data based on user selections
        selected_table = request.form['table']
        selected_column = request.form['column']

        try:
            # Connect to MySQL database
            mydb = mysql.connector.connect(
                host="localhost",
                user="root",
                passwd="password",
                database="Pizza"
            )

            # Create a cursor object to execute SQL queries
            cursor = mydb.cursor()

            # Check if the selected column exists in the selected table
            cursor.execute(f"SHOW COLUMNS FROM {selected_table} LIKE %s", (selected_column,))
            if cursor.fetchone():  # Column exists
                if selected_column == '*':
                    query = f"SELECT * FROM {selected_table};"
                    cursor.execute(query)

                else:
                    query = f"SELECT {selected_column} FROM {selected_table};"

                # Execute SQL query
                cursor.execute(query)
                data = cursor.fetchall()  # Fetch all rows

            # Close cursor and database connection
            cursor.close()
            mydb.close()

        except mysql.connector.Error as error:
            return f"Error connecting to MySQL database: {error}"

    # Render the HTML template with the form and data (if available)
    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
