from context import app

from sqlalchemy import func
from flask.ext.sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy(app)
    
class Luser(db.Model):
    __tablename__ = "luser"

    _id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True)
    pw_hash = db.Column(db.String, nullable=False)    
    created = db.Column(db.DateTime, default=datetime.utcnow())


class LuserTodo(db.Model):
    __tablename__ = "luser_todo"

    _id = db.Column(db.Integer, primary_key=True)
    luser_id = db.Column(db.Integer, db.ForeignKey(Luser._id), nullable=False)
    text = db.Column(db.String)
    number = db.Column(db.Integer, default=0)
    created = db.Column(db.DateTime, default=func.now())

    @property
    def created_human(self):
        return self.created.strftime("%A, %b. %d, %Y - %I:%M %p")

if __name__ == "__main__":

    import sys

    if sys.argv[1] == "create":
        db.create_all()
    elif sys.argv[1] == "drop":
        db.drop_all()


