import flask
import os

# create application
app = flask.Flask(__name__)

# configure database connection
# local
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql+psycopg2://tom:fender@localhost:5432/codecolab"

# heroku
#app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]


# secret!
app.secret_key = "8d312c5f-361e-431a-b0f5-c1890444a519"

# enable debugging
app.debug = True
