import flask
import os

# create application
app = flask.Flask(__name__)

# heroku
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]

# secret!
app.secret_key = "8d312c5f-361e-431a-b0f5-c1890444a519"

# enable debugging
app.debug = True
