from context import app

from sqlalchemy import func
from flask.ext.sqlalchemy import SQLAlchemy

from datetime import datetime
from urllib2 import quote

db = SQLAlchemy(app)
   

class ProjectLuser(db.Model):
    """    
    Many-Many: Project & Luser (remember: db.Model extends Base)
    """

    __table__ = db.Table("project_lusers", db.Model.metadata,
                    db.Column("project_id", db.Integer,  db.ForeignKey("project._id"), primary_key=True),
                    db.Column("luser_id", db.Integer, db.ForeignKey("luser._id"), primary_key=True),
                    db.Column("is_owner", db.Boolean, default=False))

class Luser(db.Model):
    """
    Defines user table and model
    """

    __tablename__ = "luser"

    _id     = db.Column(db.Integer, primary_key=True)
    email   = db.Column(db.String, unique=True)
    pw_hash = db.Column(db.String, nullable=False)    
    created = db.Column(db.DateTime, default=func.now())

    projects = db.relationship("Project", secondary=ProjectLuser.__table__)


class Project(db.Model):
    """
    Defines a project. A project is a collection of users and tasks.
    """

    __tablename__ = "project"

    _id     = db.Column(db.Integer, primary_key=True)
    name    = db.Column(db.String, nullable=False)
    created = db.Column(db.DateTime, default=func.now())

    lusers  = db.relationship("Luser", secondary=ProjectLuser.__table__)

    @property
    def urlencoded_name(self):
        return quote(self.name)


class Card(db.Model):
    """
    Cards:
        * May belong to at most one project.
        * May be positioned in only one lane at a time.
        * May be assigned to any number of project members.
    """

    __tablename__ = "card"

    _id         = db.Column(db.Integer, primary_key=True)
    project_id  = db.Column(db.Integer, db.ForeignKey(Project._id), nullable=False) 
    luser_id    = db.Column(db.Integer, db.ForeignKey(Luser._id), nullable=False)
    text        = db.Column(db.String)

    # Default this to current value of 'id' column, but we'll change it later
    # to adjust the order of the list.
    number = db.Column(db.Integer, default=func.currval("luser_todo__id_seq"), 
                       unique=True)
    created = db.Column(db.DateTime, default=func.now())

    @property
    def created_human(self):
        return self.created.strftime("%A, %b. %d, %Y - %I:%M %p")


class BetaSignup(db.Model):
    """
    Defines a list of beta signups and keeps a flag of whether
    they are enabled.
    """

    __tablename__ = "beta_signup"
    
    _id             = db.Column(db.Integer, primary_key=True)
    email           = db.Column(db.String, nullable=False)
    is_activated    = db.Column(db.Boolean, default=False)
    created         = db.Column(db.DateTime, default=func.now())


if __name__ == "__main__":

    import sys

    if sys.argv[1] == "create":
        db.create_all()
    elif sys.argv[1] == "drop":
        db.drop_all()


