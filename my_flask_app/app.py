from flask import Flask, render_template
app = Flask(__name__)
@app.route('/home', methods=['GET', 'POST'])
def pizza_table():
    return render_template('Pizza.html')
if __name__ == '__main__':
    app.run()