from context import app
from sqlalchemy import func
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.schema import UniqueConstraint
from flask.ext.sqlalchemy import SQLAlchemy

from datetime import datetime, timedelta, time
from pytz import timezone 
from delorean import Delorean

from urllib2 import quote
from md5 import md5
from uuid import uuid4

from config import FORMATS, BASE_URL
import os

db = SQLAlchemy(app)

DEFAULT_AVATAR_24 = "%sassets/lolvatar_24.png" % BASE_URL
DEFAULT_AVATAR_32 = "%sassets/lolvatar_32.png" % BASE_URL
DEFAULT_AVATAR_48 = "%sassets/lolvatar_48.png" % BASE_URL
DEFAULT_AVATAR_64 = "%sassets/lolvatar_64.png" % BASE_URL
DEFAULT_AVATAR_96 = "%sassets/lolvatar_96.png" % BASE_URL
DEFAULT_AVATAR_128 = "%sassets/lolvatar_128.png" % BASE_URL 

from collections import OrderedDict 


class DictSerializable(object):
    """
    Packs the model into a dict so it can easily be serialized to 
    JSON.
    """
    def _asdict(self):
        result = OrderedDict()
        for key in self.__mapper__.c.keys():
            result[key] = getattr(self, key)
        return result


class FluxCapacitor(object):
    """
    Converts from naive to localized time & formats output
    """        
    
    def created_as_timezone(self, timezone_desc):
        d = Delorean(datetime=self.created, timezone="UTC")
        d.shift(timezone_desc)
        return d.datetime.strftime("%b. %d, %Y at %I:%M %p")

    def timestamp_as_timezone(self, timezone_desc):
        d = Delorean(datetime=self.timestamp, timezone="UTC")
        d.shift(timezone_desc)
        return d.datetime.strftime("%b. %d, %Y at %I:%M %p")

class ProjectLuser(db.Model, DictSerializable):
    """    
    Many-Many: Project & Luser (remember: db.Model extends Base)
    """

    __table__ = db.Table("project_lusers", db.Model.metadata,
        db.Column("project_id", db.Integer,  db.ForeignKey("project._id"), primary_key=True),
        db.Column("luser_id", db.Integer, db.ForeignKey("luser._id"), primary_key=True),
        db.Column("is_owner", db.Boolean, default=False),
        # Setting to true means you're interested in all updates about the
        # project. Keeping it simple for MVP. For now, this will mainly be used
        # for receiving "update" emails from developers.
        db.Column("is_interested", db.Boolean, default=False))

    luser   = db.relationship("Luser")
    project = db.relationship("Project")

    schedule = db.relationship("MemberSchedule", 
primaryjoin="""and_(ProjectLuser.luser_id==MemberSchedule.luser_id,
                  ProjectLuser.project_id==MemberSchedule.project_id)""",
foreign_keys=[__table__.columns.luser_id, __table__.columns.project_id])



class ProjectInvite(db.Model, DictSerializable, FluxCapacitor):
    """
    Defines an invitation to a project. This is a relationship between
    the host's user id, the project id, and the future user's email.

    This is only used when the user is not yet a member. Existing users
    will be added to the project automatically and if they don't like it,
    they can simply opt out by removing themselves.
    """

    __tablename__ = "project_invite"

    luser_id   = db.Column(db.Integer, db.ForeignKey("luser._id"), primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project._id"), primary_key=True)
    email      = db.Column(db.String, nullable=False, primary_key=True)
    is_pending = db.Column(db.Boolean, default=True)
    created    = db.Column(db.DateTime, default=func.now())

    inviter    = db.relationship("Luser")

    @property
    def status(self):
        if self.is_pending:
            return "Pending"
        else:
            return "Accepted"


class Luser(db.Model, DictSerializable):
    """
    Defines user table and model
    """

    __tablename__ = "luser"

    _id     = db.Column(db.Integer, primary_key=True)
    email   = db.Column(db.String, unique=True)
    pw_hash = db.Column(db.String, default=None)
    google_id = db.Column(db.String, default=None)
    created = db.Column(db.DateTime, default=func.now())
    last_project_id = db.Column(db.Integer, default=None)
    is_active = db.Column(db.Boolean, default=True)

    has_github_token = db.Column(db.Boolean, default=False)
    github_token = db.Column(db.String, default=None)

    projects = db.relationship("Project", secondary=ProjectLuser.__table__)
    profile = db.relationship("LuserProfile", uselist=False)
    activity = db.relationship("Activity")
    reports = db.relationship("MemberReport",
                              order_by="MemberReport.created.desc()")

    notification_preferences = db.relationship("NotificationPreferences",
                                                uselist=False)
    schedules = db.relationship("MemberSchedule")
    card_assignments = db.relationship("CardAssignments")


    def get_checked_notifications(self):
        return notification_preferences.to_checkboxes()


    def is_assigned_to(self, card_id):
        for assignment in self.card_assignments:
            if card_id == assignment.card_id:
                return True
        return False


    @property
    def recent_activity(self):
        """ 
        Gets only activity that was generated after the most recent
        report.
        """
        if len(self.reports) == 0:
            return self.activity
        else:
            cutoff_time = self.reports[0].created
            return [a for a in self.activity if a.created > cutoff_time]


    @property
    def gravatar_url(self):
        email_hash = md5(self.email.strip().lower()).hexdigest()
        return "http://gravatar.com/avatar/%s?s=128&d=%s" % (email_hash,
            DEFAULT_AVATAR_128)

    
    @property
    def small_gravatar_url(self):
        email_hash = md5(self.email.strip().lower()).hexdigest()
        return "http://gravatar.com/avatar/%s?s=64&d=%s" % (email_hash,
            DEFAULT_AVATAR_64)


    @property
    def gravatar_url_48(self):
        email_hash = md5(self.email.strip().lower()).hexdigest()
        return "http://gravatar.com/avatar/%s?s=48&d=%s" % (email_hash,
            DEFAULT_AVATAR_48)

    @property
    def gravatar_url_96(self):
        email_hash = md5(self.email.strip().lower()).hexdigest()
        return "http://gravatar.com/avatar/%s?s=96&d=%s" % (email_hash,
            DEFAULT_AVATAR_96)


    @property
    def tiny_gravatar_url(self):
        email_hash = md5(self.email.strip().lower()).hexdigest()
        return "http://gravatar.com/avatar/%s?s=32&d=%s" % (email_hash,
            DEFAULT_AVATAR_32)


    @property
    def gravatar_url_24(self):
        email_hash = md5(self.email.strip().lower()).hexdigest()
        return "http://gravatar.com/avatar/%s?s=24&d=%s" % (email_hash,
            DEFAULT_AVATAR_24)


    @property
    def gravatar_profile_url(self):
        email_hash = md5(self.email.strip().lower()).hexdigest()
        return "http://gravatar.com/%s" % email_hash



class NotificationPreferences(db.Model, DictSerializable):
    
    __tablename__ = "notification_preferences"

    _id = db.Column(db.Integer, primary_key=True)
    luser_id = db.Column(db.Integer, db.ForeignKey(Luser._id), nullable=False) 
    on_subscribed_only = db.Column(db.Boolean, default=True)
    on_card_text_change = db.Column(db.Boolean, default=False)
    on_card_comment = db.Column(db.Boolean, default=True)
    on_card_attachment = db.Column(db.Boolean, default=True)
    on_card_completion = db.Column(db.Boolean, default=True)
    on_card_archived = db.Column(db.Boolean, default=False)

    
    def to_checkboxes(self):
        n = {}

        # emit the text 'checked' if the preference is turned on.
        c = lambda o,a: "checked" if getattr(o,a) else ""

        n['on_subscribed_only'] = c(self, 'on_subscribed_only')
        n['on_card_text_change'] = c(self, 'on_card_text_change')
        n['on_card_comment'] = c(self, 'on_card_comment')
        n['on_card_attachment'] = c(self, 'on_card_attachment')
        n['on_card_completion'] = c(self, 'on_card_completion')
        n['on_card_archived'] = c(self, 'on_card_archived')

        return n


class LuserProfile(db.Model, DictSerializable):
    """
    Defines a users profile: first name, last name, username, timezone.
    """
    
    __tablename__ = "luser_profile"

    _id         = db.Column(db.Integer, primary_key=True)
    luser_id    = db.Column(db.Integer, db.ForeignKey(Luser._id), nullable=False) 
    first_name  = db.Column(db.String)
    last_name   = db.Column(db.String)
    username    = db.Column(db.String, nullable=False)
    timezone    = db.Column(db.String, default="Zulu")
    theme       = db.Column(db.String, default="light")
    luser       = db.relationship("Luser")
   

    @property
    def tz_utc_offset_seconds(self):
        """
        The distance of the user's timezone from UTC
        in seconds.
        """
        return (datetime.now(timezone(self.timezone))
                        .utcoffset().total_seconds())
   

    @property
    def tz_utc_offset_hours(self):
        return int(self.tz_utc_offset_seconds / 3600)


    @property 
    def tz_utc_offset_human(self):
        if self.tz_utc_offset_hours == 0:
            return "UTC"
        elif self.tz_utc_offset_hours > 0:
            return "UTC +%d" % self.tz_utc_offset_hours
        else:
            return "UTC %d" % self.tz_utc_offset_hours


class Project(db.Model, DictSerializable):
    """
    Defines a project. A project is a collection of users and tasks.
    """

    __tablename__ = "project"

    _id         = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String, nullable=False)
    created     = db.Column(db.DateTime, default=func.now())
    is_archived = db.Column(db.Boolean, default=False)

    has_github_repo = db.Column(db.Boolean, default=False)
    github_repo = db.Column(db.String, default=None)
    github_repo_hook_id = db.Column(db.Integer, default=None)

    milestones  = db.relationship("Milestone", order_by=lambda: Milestone.created)
    lusers      = db.relationship("Luser", secondary=ProjectLuser.__table__,
                                           order_by=lambda: Luser.created)

    plusers     = db.relationship("ProjectLuser")

    cards       = db.relationship("Card", order_by=lambda: Card.number.desc())

    archived_cards = db.relationship("Card", order_by=lambda: Card.archived_at.desc())

    piles       = db.relationship("Pile", order_by=lambda: Pile.number)    
    members     = db.relationship("ProjectLuser")
    activity    = db.relationship("Activity", order_by=lambda: Activity.created.desc())
   
    reports     = db.relationship("MemberReport", order_by=lambda:
                                  MemberReport.created.desc())

    def recipients(self, required_preference=None):
        recipients = []
        for pluser in self.plusers:
            if pluser.is_interested and (required_preference is None or 
                getattr(pluser.notification_preferences, required_preference)):
                recipients.append(pluser.luser)
       
        return recipients


    def is_owner(self, luser_id):
        for member in self.members:
            if member.luser_id == luser_id and member.is_owner:
                return True
        return False


    @property
    def urlencoded_name(self):
        return quote(self.name)


class Day(db.Model):
    
    __tablename__ = "day"
   
    _id     = db.Column(db.Integer, primary_key=True)
    name    = db.Column(db.String, nullable=False, unique=True)
    abbrev  = db.Column(db.String, nullable=False, unique=True)
    ordinal = db.Column(db.Integer)


class Days(object):
    def __init__(self):
        self.days = Day.query.order_by(Day.ordinal.asc()).all()
        self.day_map = {}

        for day in self.days:
            self.day_map[day.name] = day._id
            

class MemberSchedule(db.Model, DictSerializable):
    """
    Defines a collection of hours for a per-project, per-user schedule.
    """

    __tablename__ = "member_schedule"

    # composite primary key to enforce uniqueness
    _id         = db.Column(db.Integer, primary_key=True)
    luser_id    = db.Column(db.Integer, db.ForeignKey(Luser._id), nullable=False)
    project_id  = db.Column(db.Integer, db.ForeignKey(Project._id), nullable=False)
    created     = db.Column(db.DateTime, default=func.now())

    ranges      = db.relationship("MemberScheduleTimeRanges",
                    order_by="MemberScheduleTimeRanges.day_id")
    project     = db.relationship("Project")

    __table_args__ = ( db.UniqueConstraint("luser_id", "project_id"), )


class MemberScheduleTimeRanges(db.Model, DictSerializable):
    """
    Defines the actual hours of the schedule.
    """

    __tablename__ = "member_schedule_time_ranges"

    _id         = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey(MemberSchedule._id))
    day_id      = db.Column(db.Integer, db.ForeignKey(Day._id))
    start_time  = db.Column(db.Time, default=time(hour=9))
    end_time    = db.Column(db.Time, default=time(hour=17))
    created     = db.Column(db.DateTime, default=func.now())

    day         = db.relationship("Day")


class MemberReport(db.Model, DictSerializable, FluxCapacitor):
    
    __tablename__ = "member_report"

    _id                 = db.Column(db.Integer, primary_key=True)
    
    luser_id            = db.Column(db.Integer, db.ForeignKey(Luser._id))
    project_id          = db.Column(db.Integer, db.ForeignKey(Project._id))
    username            = db.Column(db.String)
    subject             = db.Column(db.String, default="No Subject")
    text                = db.Column(db.String)
    report_date         = db.Column(db.DateTime, default=func.now(), nullable=False)
    created             = db.Column(db.DateTime, default=func.now(), nullable=False)
    is_user_submitted   = db.Column(db.Boolean, default=False)

    luser               = db.relationship("Luser")
    project             = db.relationship("Project")

    tags                = db.relationship('ReportTag')

    comments = db.relationship("ReportComment", 
                                order_by="ReportComment.created.desc()")

    def timestamp(self, tz):
        return self.created_as_timezone(tz)


    def describe_with_time(self, tz):
        timestamp = self.timestamp(tz)
        return '"%s" on %s' % (self.subject, timestamp)


class Tag(db.Model):
    
    __tablename__ = "tag"

    _id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)


class ReportTag(db.Model):

    __tablename__ = "report_tag"
    
    _id = db.Column(db.Integer, primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey(Tag._id), nullable=False)
    report_id = db.Column(db.Integer, db.ForeignKey(MemberReport._id),
                          nullable=False)
    
    tag = db.relationship('Tag')

    __table_args__ = (UniqueConstraint('tag_id', 'report_id', 
                        name='_report_tag_uc'), )


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

        for card in self.cards:
            if card.is_completed:
                complete_cards += 1
                complete_score += card.score
            else:
                incomplete_cards += 1
                incomplete_score += card.score
            
            total_score += card.score

        if total_score == 0:
            progress = 0
        else:
            progress = float(complete_score) / float(total_score)
        
        progress = "%d%%" % (round(progress, 2) * 100)


        if total_cards == 0:
            card_completion = 0
        else:
            card_completion = complete_cards / float(total_cards)

        if total_score == 0:
            point_completion = 0
        else:
            point_completion = complete_score / float(total_score)

        return dict(name=self.name, card_completion=card_completion, 
                    point_completion=point_completion)

    @property
    def stat_names(self):
        return ["Milestone", "Progress", "Card Completion",
                "Point Completion", "Rating Coverage"]


    @property
    def stat_tooltips(self):
        return ["Name of goal",
                "Percentage of completed points.",
                "Ratio of cards that have been finished to unfinished.",
                "Ratio of points that have been finished to unfinished.",
                "Ratio of cards that have been rated to unrated."]


class Pile(db.Model, DictSerializable):
    """
    Piles are containers for cards. A card can only be on
    one pile at a time.
    """
    
    __tablename__ = "pile"

    _id         = db.Column(db.Integer, primary_key=True)
    number      = db.Column(db.Integer, default=func.currval("pile__id_seq"))
    project_id  = db.Column(db.Integer, db.ForeignKey(Project._id), nullable=False)
    is_deleted  = db.Column(db.Boolean, default=False)
    name        = db.Column(db.String, nullable=False, default="Unnamed Pile")
    created     = db.Column(db.DateTime, default=func.now())

    cards       = db.relationship("Card", order_by=lambda: Card.number)
    @property
    def pile_uuid(self):
        return "pile_" + md5(str(self._id) + self.name + str(self.created)).hexdigest()


class Card(db.Model, DictSerializable, FluxCapacitor):
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
    due_datetime    = db.Column(db.DateTime, default=None, nullable=True)
    comment_count   = db.Column(db.Integer, default=0)
    attachment_count = db.Column(db.Integer, default=0)
    project_id      = db.Column(db.Integer, db.ForeignKey(Project._id), nullable=False)
    pile_id         = db.Column(db.Integer, db.ForeignKey(Pile._id))
    luser_id        = db.Column(db.Integer, db.ForeignKey(Luser._id))
    milestone_id    = db.Column(db.Integer, db.ForeignKey(Milestone._id))
    assign_to_id    = db.Column(db.Integer, db.ForeignKey(Luser._id))
    is_archived     = db.Column(db.Boolean, default=False)
    archived_at     = db.Column(db.DateTime)
    text            = db.Column(db.String)
    score           = db.Column(db.Integer, default=0)
    description     = db.Column(db.String, default="Please enter a description...")
    is_completed    = db.Column(db.Boolean, default=False)

    # Default this to current value of 'id' column, but we'll change it later
    # to adjust the order of the list.
    number = db.Column(db.Integer, default=func.currval("card__id_seq"))
    created = db.Column(db.DateTime, default=func.now())

    comments = db.relationship("CardComment", cascade="all,delete",
                                order_by=lambda: CardComment.created)
    attachments = db.relationship("CardFile", cascade="all,delete",
                                  order_by=lambda: CardFile.created.desc())
    subscriptions = db.relationship("CardSubscription", cascade="all,delete")
    tags = db.relationship("CardTag", cascade="all,delete")
    assigned = db.relationship("CardAssignments", cascade="all,delete")

    milestone = db.relationship("Milestone")
    project = db.relationship("Project")
    pile = db.relationship("Pile")


    def is_luser_subscribed(self, luser_id):
        for sub in self.subscriptions:
            if luser_id == sub.luser_id:
                return True
        return False


    @property
    def due_time(self):
        if self.due_datetime is not None:
            return self.due_datetime.strftime("%I:%M%p")
        else:
            return ""


    @property
    def due_date(self):
        """ uses the format expected for parameters to a javascript
            date() function i.e. year, month, day """
        if self.due_datetime is not None:
            dt = self.due_datetime
            return "%d, %d, %d" % (dt.year, dt.month -1, dt.day)
        else:
            return ""


    @property
    def title(self):
        return self.text[:50] + "..."


    @property
    def card_uuid(self):
        return "card_" + md5(str(self._id) + self.text + str(self.created)).hexdigest()


    @property
    def created_human(self):
        return self.created.strftime("%d, %Y at %I:%M %p")


    @staticmethod
    def create(luser_id, project, pile_id, text):
        """
        Adds a card to a specific pile of a project, with the specified
        text.
        """
        card = Card(luser_id=luser_id, project_id=project._id, 
                    pile_id=pile_id, text=text)

        db.session.add(card)
        db.session.flush()

        # creator must be subscribed by default
        sub = CardSubscription(luser_id=luser_id, card_id=card._id)
        db.session.add(sub)
        db.session.commit()
        
        return card


    def subscribers(self, required_preference=None):
        subscribers = []
        for sub in self.subscriptions:

            if (required_preference is None or 
                getattr(sub.luser.notification_preferences, 
                            required_preference)):

                subscribers.append(sub.luser.email)

        return subscribers


class CardSubscription(db.Model):
    
    __tablename__ = 'card_subscription'

    _id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey(Card._id), nullable=False)
    luser_id = db.Column(db.Integer, db.ForeignKey(Luser._id), nullable=False)

    luser = db.relationship('Luser')
    card = db.relationship('Card')

    __table_args__ = (UniqueConstraint('card_id', 'luser_id', 
                        name='_card_sub_uc'),)


class CardTag(db.Model):
    
    __tablename__ = "card_tag"

    _id = db.Column(db.Integer, primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey(Tag._id), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey(Card._id), nullable=False)

    tag = db.relationship("Tag")

    __table_args__ = (UniqueConstraint('tag_id', 'card_id',
                      name='_card_tag_uc'),)


class CardAssignments(db.Model):
    __tablename__ = 'card_assignments'

    _id = db.Column(db.Integer, primary_key=True, nullable=False)
    luser_id = db.Column(db.Integer,db.ForeignKey(Luser._id), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey(Card._id), nullable=False)
    
    card = db.relationship("Card")
    luser = db.relationship("Luser")


class CardCompletions(db.Model):
    __tablename__ = "card_completions"

    _id         = db.Column(db.Integer, primary_key=True)
    card_id     = db.Column(db.Integer, db.ForeignKey(Card._id), 
                            nullable=False)
    luser_id    = db.Column(db.Integer, db.ForeignKey(Luser._id), 
                            nullable=False)
    created     = db.Column(db.DateTime, default=datetime.utcnow)

    card = db.relationship("Card")


class Commit(db.Model, FluxCapacitor):
    __tablename__ = "commit"

    _id = db.Column(db.Integer, primary_key=True)
    commit_id = db.Column(db.String)
    committer = db.Column(db.String)
    committer_email = db.Column(db.String)
    message = db.Column(db.String)
    url = db.Column(db.String)
    diff = db.Column(db.String)
    timestamp = db.Column(db.DateTime)
    removed = db.Column(db.String)
    added = db.Column(db.String)
    project_id = db.Column(db.Integer)

    @property
    def gravatar_url(self):
        email_hash = md5(self.committer_email.strip().lower()).hexdigest()
        return "http://gravatar.com/avatar/%s?s=48&d=%s" % (email_hash,
            DEFAULT_AVATAR_48)


class BaseComment(DictSerializable, FluxCapacitor):
    _id         = db.Column(db.Integer, primary_key=True)
    created     = db.Column(db.DateTime, default=func.now())
    text        = db.Column(db.String)


    @declared_attr
    def luser_id(cls):
        return db.Column(db.Integer, db.ForeignKey(Luser._id), nullable=False)


    @declared_attr
    def luser(cls):
        return db.relationship("Luser")


    @property
    def created_human(self):
        return self.created.strftime("%d, %Y at %I:%M %p")


    @property
    def email(self):
        return self.luser.email


class CardComment(db.Model, BaseComment):
    __tablename__ = "card_comment"

    card_id     = db.Column(db.Integer, db.ForeignKey(Card._id), nullable=False)
    card        = db.relationship("Card")


class ReportComment(db.Model, BaseComment):
    __tablename__ = "report_comment"

    report_id   = db.Column(db.Integer, db.ForeignKey(MemberReport._id),
                            nullable=False)
    report      = db.relationship("MemberReport")


# TODO: refactor, use mixin for 'created'
class CardFile(db.Model, DictSerializable):

    __tablename__ = "card_file"

    _id         = db.Column(db.Integer, primary_key=True)
    created     = db.Column(db.DateTime, default=func.now())
    luser_id    = db.Column(db.Integer, db.ForeignKey(Luser._id), nullable=False)
    card_id     = db.Column(db.Integer, db.ForeignKey(Card._id), nullable=False)
    filename    = db.Column(db.String, nullable=False)
    url         = db.Column(db.String, nullable=False)

    card        = db.relationship("Card")
    luser       = db.relationship("Luser")


    @property
    def is_image(self):
        root, ext = os.path.splitext(self.filename)
        return ext.lower() in FORMATS


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


class ForgottenPasswordRequest(db.Model, DictSerializable):
    """
    Defines a forgotten password request that will expire in one day
    if not acted upon.
    """
    __tablename__ = "forgotten_password_request"

    _id         = db.Column(db.Integer, primary_key=True)
    luser_id     = db.Column(db.Integer, db.ForeignKey(Luser._id), nullable=False)
    uuid        = db.Column(db.String, nullable=False)
    expiration  = db.Column(db.DateTime, nullable=False)

    def __init__(self, user_id):
        self.luser_id = int(user_id)
        self.uuid = str(uuid4())
        self.expiration = datetime.utcnow() + timedelta(days=1)


class ActivityType(db.Model, DictSerializable):

    __tablename__ = "activity_type"

    _id             = db.Column(db.Integer, primary_key=True)
    type            = db.Column(db.String, nullable=False, unique=True)
    format          = db.Column(db.String, nullable=False)
    text_format     = db.Column(db.String, nullable=False)


class Activity(db.Model, DictSerializable, FluxCapacitor):
    
    __tablename__ = "activity"

    _id             = db.Column(db.Integer, primary_key=True)
    luser_id        = db.Column(db.Integer, db.ForeignKey(Luser._id))
    project_id      = db.Column(db.Integer, db.ForeignKey(Project._id))
    type_id         = db.Column(db.Integer, db.ForeignKey(ActivityType._id))
    card_id         = db.Column(db.Integer, db.ForeignKey(Card._id, ondelete="CASCADE"))
    created         = db.Column(db.DateTime, default=func.now())

    type            = db.relationship("ActivityType")
    luser           = db.relationship("Luser")
    card            = db.relationship("Card")

   
    def describe(self, username):
        return self.type.format % { "user_id" : self.luser_id,
                                    "username" : self.luser.profile.username,
                                    "project_name" : self.card.project.name,
                                    "card_id" : self.card._id,
                                    "card_text" : self.card.text }


    def describe_with_time(self, username, tz):
        return self.type.text_format % { "card_text" : self.card.text,
                                "username" : self.luser.profile.username }


    def __str__(self):
        return self.describe(self.luser.profile.username)


class ActivityLogger(object):
    
    def __init__(self):
        activity_types = ActivityType.query.all()
        self.type_map = {}

        for type in activity_types:
            self.type_map[type.type] = type._id


    def log(self, luser_id, project_id, card_id, type):
        type_id = self.type_map[type]

        activity = Activity(luser_id=luser_id, project_id=project_id,
                            card_id=card_id, type_id=type_id)
        db.session.add(activity)
        db.session.commit()


##############################################################################
# Maintenance code
##############################################################################

def insert_or_update_activity_type(fmt, text_fmt, type):
    activity_type = ActivityType.query.filter_by(type=type).first()
    
    if activity_type is not None:
        activity_type.type = type
        activity_type.format = fmt
        activity_type.text_format = text_fmt
    else:
        activity_type = ActivityType(type=type, format=fmt,
                                    text_format=text_fmt)
        db.session.add(activity_type)


if __name__ == "__main__":

    import sys

    if sys.argv[1] == "create":
        db.create_all()

    if sys.argv[1] == "create_weekdays":
        day = Day(name="Monday", abbrev="Mon")
        db.session.add(day)

        day = Day(name="Tuesday", abbrev="Tue")
        db.session.add(day)

        day = Day(name="Wednesday", abbrev="Wed")
        db.session.add(day)

        day = Day(name="Thursday", abbrev="Thu")
        db.session.add(day)

        day = Day(name="Friday", abbrev="Fri")
        db.session.add(day)

        day = Day(name="Saturday", abbrev="Sat")
        db.session.add(day)

        day = Day(name="Sunday", abbrev="Sun")
        db.session.add(day)

        db.session.commit()

    if sys.argv[1] == "create_activity_types":
        
        base_fmt = """
<a class="activity_username" href="/profile/%%(user_id)d">@%%(username)s</a>

<span class="activity_action">%s</span>

<a data-id="%%(card_id)d" class="activity_card" href="/project/%%(project_name)s/cards/%%(card_id)d">%%(card_text)s</a>
"""

        base_text_fmt = "%s %%(card_text)s"

        fmt = base_fmt % "created card"
        text_fmt = base_text_fmt % "created card"
        insert_or_update_activity_type(fmt, text_fmt, "card_created")

        fmt = base_fmt % "completed card"
        text_fmt = base_text_fmt % "completed card"
        insert_or_update_activity_type(fmt, text_fmt, "card_finished")

        fmt = base_fmt % "marked card as incomplete"
        text_fmt = base_text_fmt % "marked card as incomplete"
        insert_or_update_activity_type(fmt, text_fmt, "card_incomplete")

        fmt = base_fmt % "commented on card"
        text_fmt = base_text_fmt % "commented on card"
        insert_or_update_activity_type(fmt, text_fmt, "card_comment")

        fmt = base_fmt % "deleted comment on card"
        text_fmt = base_text_fmt % "deleted comment on card"
        insert_or_update_activity_type(fmt, text_fmt, "card_comment_delete")
        
        fmt = base_fmt % "edited card"
        text_fmt = base_text_fmt % "edited card"
        insert_or_update_activity_type(fmt, text_fmt, "card_edit")

        fmt = base_fmt % "changed card"
        text_fmt = base_text_fmt % "changed card"
        insert_or_update_activity_type(fmt, text_fmt, "card_change")
        
        fmt = base_fmt % "deleted card"
        text_fmt = base_text_fmt % "deleted card"
        insert_or_update_activity_type(fmt, text_fmt, "card_delete")

        fmt = base_fmt % "archived card"
        text_fmt = base_text_fmt % "archived card"
        insert_or_update_activity_type(fmt, text_fmt, "card_archive")
        
        fmt = base_fmt % "edit comment"
        text_fmt = base_text_fmt % "edit comment"
        insert_or_update_activity_type(fmt, text_fmt, "edit_comment")


        db.session.commit()

    elif sys.argv[1] == "drop":
        db.drop_all()
