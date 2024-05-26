from flask import Flask

app = Flask(__name__)

from my_flask_app import routes
from my_flask_app import routes1