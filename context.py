import flask

# create application
app = flask.Flask(__name__)

# configure database connection
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql+psycopg2://tom:fender@localhost:5432/codecolab"

# secret!
app.secret_key = "8d312c5f-361e-431a-b0f5-c1890444a519"

# enable debugging
app.debug = True
