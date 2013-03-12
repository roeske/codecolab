from context import app
from sqlalchemy import func
from flask.ext.sqlalchemy import SQLAlchemy
from datetime import datetime
from urllib2 import quote
from md5 import md5

db = SQLAlchemy(app)

# Easily serialize to dict for json conversion # See: http://piotr.banaszkiewicz.org/blog/2012/06/30/serialize-sqlalchemy-results-into-json/

from collections import OrderedDict

class DictSerializable(object):
    def _asdict(self):
        result = OrderedDict()
        for key in self.__mapper__.c.keys():
            result[key] = getattr(self, key)
        return result


class ProjectLuser(db.Model, DictSerializable):
    """    
    Many-Many: Project & Luser (remember: db.Model extends Base)
    """

    __table__ = db.Table("project_lusers", db.Model.metadata,
        db.Column("project_id", db.Integer,  db.ForeignKey("project._id"), primary_key=True),
        db.Column("luser_id", db.Integer, db.ForeignKey("luser._id"), primary_key=True),
        db.Column("is_owner", db.Boolean, default=False))


class Luser(db.Model, DictSerializable):
    """
    Defines user table and model
    """

    __tablename__ = "luser"

    _id     = db.Column(db.Integer, primary_key=True)
    email   = db.Column(db.String, unique=True)
    pw_hash = db.Column(db.String, nullable=False)    
    created = db.Column(db.DateTime, default=func.now())

    projects = db.relationship("Project", secondary=ProjectLuser.__table__)


class Project(db.Model, DictSerializable):
    """
    Defines a project. A project is a collection of users and tasks.
    """

    __tablename__ = "project"

    _id         = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String, nullable=False)
    created     = db.Column(db.DateTime, default=func.now())

    milestones  = db.relationship("Milestone", order_by=lambda: Milestone.created)
    lusers      = db.relationship("Luser", secondary=ProjectLuser.__table__)
    cards       = db.relationship("Card", order_by=lambda: Card.number)
    piles       = db.relationship("Pile", order_by=lambda: Pile.number)    

    @property
    def urlencoded_name(self):
        return quote(self.name)


class Milestone(db.Model, DictSerializable):
    """
    Defines a goal within a project.
    """

    __tablename__ = "milestone"

    _id         = db.Column(db.Integer, primary_key=True)
    project_id  = db.Column(db.Integer, db.ForeignKey(Project._id))
    name        = db.Column(db.String)
    is_approved = db.Column(db.Boolean, default=False) 
    created     = db.Column(db.DateTime, default=func.now())
    cards       = db.relationship("Card", order_by=lambda: Card.number)


    @property
    def stats(self):
        """
        Gather some basic metrics on what has been done. 

        * 'progress' -- This is the percentage of completed points.
                        Unrated cards are not included in the score.
                        
                        Additionally, cards not associated with a milestone,
                        cannot be included in the score. So, negligence in
                        associating your cards with milestones will effect
                        the usefulness of this metric. 

                        Best practice will be to associate all your cards
                        with a milestone.
        
        * 'incomplete_cards' -- Count of cards that have not been marked
                                as complete for this milestone.

        * 'incomplete_score' -- Total amount of points assigned to incomplete
                                cards. Again, unrated cards cannot be included.

        * 'complete_cards'   -- Count of cards that have been marked as
                                complete for this milestone.

        * 'complete_score'   -- Of cards that have been marked complete, the
                                total of all 'score' values. Again, unscored
                                cards are not included (They're 0 by default,
                                which in our system means 'unrated')

        * 'total_cards'      -- Total # of cards assigned to this milestone.

        * 'total_score'      -- Total # of points from assigned cards. Unscored
                                counts for 0.

        * 'rated_cards'      -- Count of cards that have been rated.

        * 'unrated_cards'    -- Count of cards that have not been rated.
        """

        progress = 0
        incomplete_cards = 0
        incomplete_score = 0
        complete_cards = 0
        complete_score = 0
        total_cards = len(self.cards)
        total_score = 0
        rated_cards = 0
        unrated_cards = 0

        for card in self.cards:
            if card.is_completed:
                complete_cards += 1
                complete_score += card.score
            else:
                incomplete_cards += 1
                incomplete_score += card.score
            
            if card.score == 0:
                unrated_cards += 1
            else:
                rated_cards += 1
            
            total_score += card.score

        if total_score == 0:
            progress = 0
        else:
            progress = float(complete_score) / float(total_score)
        
        progress = "%d%%" % (round(progress, 2) * 100)

        return [self.name, progress, incomplete_cards, incomplete_score,
                complete_cards, complete_score, total_cards, total_score,
                rated_cards, unrated_cards]

    @property
    def stat_names(self):
        return ["Milestone", "Progress", "Incomplete Cards",
                "Incomplete Score", "Complete Cards", "Complete Score",
                "Total Cards", "Total Score", "Rated Cards", "Unrated Cards"]

    @property
    def stat_tooltips(self):
        return ["Name of goal",
                "Percentage of completed points.",
                "# of cards that have not been marked as complete",
                "Total points of cards not marked complete",
                "# of cards marked complete",
                "Total points of all cards marked complete",
                "Total # of cards assigned to this milestone.",
                "Total number of points for all assigned cards",
                "# of cards that have been rated",
                "# of cards that have not been rated."]


class Pile(db.Model, DictSerializable):
    """
    Piles are containers for cards. A card can only be on
    one pile at a time.
    """
    
    __tablename__ = "pile"

    _id         = db.Column(db.Integer, primary_key=True)
    number      = db.Column(db.Integer, default=func.currval("pile__id_seq"))
    project_id  = db.Column(db.Integer, db.ForeignKey(Project._id), nullable=False)
    name        = db.Column(db.String, nullable=False, default="Unnamed Pile")
    created     = db.Column(db.DateTime, default=func.now())
    cards       = db.relationship("Card", order_by=lambda: Card.number)

    @property
    def pile_uuid(self):
        return "pile_" + md5(str(self._id) + self.name + str(self.created)).hexdigest()


class Card(db.Model, DictSerializable):
    """
    Cards:
        * May belong to at most one project.
        * May be positioned in only one lane at a time.
        * May be assigned to any number of project members.
    """

    # Scores 
    DIFFICULTY_SCORE_NONE = 0 # 0 for none, so it renders correct in a plugin
                        # which requires the number to be an integer if
                        # required.
    DIFFICULTY_SCORE_EASY = 1
    DIFFICULTY_SCORE_MEDIUM = 2
    DIFFICULTY_SCORE_HARD = 3


    __tablename__ = "card"

    _id             = db.Column(db.Integer, primary_key=True)

    project_id      = db.Column(db.Integer, db.ForeignKey(Project._id), nullable=False) 
    pile_id         = db.Column(db.Integer, db.ForeignKey(Pile._id))
    milestone_id    = db.Column(db.Integer, db.ForeignKey(Milestone._id))

    text            = db.Column(db.String)
    score           = db.Column(db.Integer, default=DIFFICULTY_SCORE_NONE)
    description     = db.Column(db.String, default="Please enter a description...")
    is_completed    = db.Column(db.Boolean, default=False)

    # Default this to current value of 'id' column, but we'll change it later
    # to adjust the order of the list.
    number = db.Column(db.Integer, default=func.currval("card__id_seq"))
    created = db.Column(db.DateTime, default=func.now())

    comments = db.relationship("CardComment", order_by=lambda: CardComment.created)
    attachments = db.relationship("CardFile", order_by=lambda: CardFile.created)
    milestone = db.relationship("Milestone")


    @property
    def title(self):
        return self.text[:50] + "..."


    @property
    def card_uuid(self):
        return "card_" + md5(str(self._id) + self.text + str(self.created)).hexdigest()


    @property
    def created_human(self):
        return self.created.strftime("%A, %b. %d, %Y - %I:%M %p")


# TODO: refactor, use mixin for 'created'
class CardComment(db.Model, DictSerializable):

    __tablename__ = "card_comment"

    _id         = db.Column(db.Integer, primary_key=True)
    created     = db.Column(db.DateTime, default=func.now())
    luser_id    = db.Column(db.Integer, db.ForeignKey(Luser._id), nullable=False)
    card_id     = db.Column(db.Integer, db.ForeignKey(Card._id), nullable=False)
    text        = db.Column(db.String)
   
    luser       = db.relationship("Luser")


    @property
    def email(self):
        return self.luser.email


    @property
    def created_human(self):
        return self.created.strftime("%A, %b. %d, %Y - %I:%M %p")


# TODO: refactor, use mixin for 'created'
class CardFile(db.Model, DictSerializable):

    __tablename__ = "card_file"

    _id         = db.Column(db.Integer, primary_key=True)
    created     = db.Column(db.DateTime, default=func.now())
    luser_id    = db.Column(db.Integer, db.ForeignKey(Luser._id), nullable=False)
    card_id     = db.Column(db.Integer, db.ForeignKey(Card._id), nullable=False)
    filename    = db.Column(db.String, nullable=False)
   
    luser       = db.relationship("Luser")


class BetaSignup(db.Model, DictSerializable):
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
