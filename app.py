import os
import flask
import models
import bcrypt 
import pytz
import httplib2
import time
import base64
import hmac
import sha
import Image
import urllib
import re
import string
import uuid
import simplejson as json 

from StringIO import StringIO
from flask import request
from flaskext import uploads
from flaskext.markdown import Markdown
from functools import wraps
from sqlalchemy import and_
from md5 import md5 
from pidgey import Mailer 
from datetime import datetime, timedelta
from pytz import timezone
from oauth2client.client import flow_from_clientsecrets

from config import *
from helpers import (make_gravatar_url, make_gravatar_profile_url,
                     redirect_to, redirect_to_index, respond_with_json,
                     jsonize, get_luser_for_email)
import email_notify

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')       
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
S3_BUCKET = os.environ.get('S3_BUCKET')


def debug(text):
    print "DEBUG: %r" % text

activity_logger = models.ActivityLogger()

app = models.app


def round_time_up(t):
    """ 
    Rounds a 'time' object up to the nearest hour. This means,
    23:59:59.999999 will become 24.
    """
    # Avoid conditionals by using arithmetic. The same logic holds
    # true.
    if t.second + t.minute + t.microsecond > 0:
        return t.hour + 1
    else:
        # The 'time' object already satisfies the rounding criteria.
        return t.hour


app.jinja_env.filters["round_time_up"] = round_time_up 
app.jinja_env.filters["debug"] = debug
app.jinja_env.add_extension("jinja2.ext.loopcontrols")
app.jinja_env.add_extension("jinja2.ext.do")


Markdown(app)

app.debug = False if os.getenv("CODECOLAB_DEBUG", False) == False else True

PORT = 8080
files = uploads.UploadSet("files", uploads.ALL, default_dest=lambda app:"./uploads")
uploads.configure_uploads(app, (files,))


# TODO: clean this up.
def is_logged_in():
    return "email" in flask.session



###############################################################################
# Sign S3 Uploads
###############################################################################

# Used for expiration time since it is a required field.
# our files will expire on 2033-06-05, by then hopefully there
# will be a better solution than files.
FUTURE = 2001613951

@app.route('/sign_s3_upload/')
def sign_s3_put():
    """
    Provide a temporary signature so that users can upload files directly from their
    browsers to our AWS S3 bucket.
    The authorization portion is taken from Example 3 on
    http://s3.amazonaws.com/doc/s3-developer-guide/RESTAuthentication.html
    """

    # Thanks AWS. Perhaps you should fix S3. Seeing as how this bug with
    # signatures has existed since like, 2007 or something. %2B and "+"
    # both seem to break S3 uploads when present in the signature.
    while True:
        # Don't give user full control over filename - avoid ability to
        # overwrite files.
        random = base64.urlsafe_b64encode(os.urandom(2))[:-1] + "_"
        object_name = random+request.args.get('s3_object_name')

        # We don't want to sign the urlencoded version of the object name. That
        # will cause a SignatureMismatchError.
        orig_object_name = object_name

        # Make sure it works for filenames with spaces, etc.
        # But also make sure it works for filenames with dollar signs!
        object_name = urllib.quote_plus(object_name, safe="$/") 

        mime_type = request.args.get('s3_object_type')

        print "mime_type=%r" % mime_type 
        print "object_name=%r" % object_name
        
        expires = int(time.time()+300) # PUT request to S3 must start within X seconds
        amz_headers = "x-amz-acl:public-read" # set the public read permission on the uploaded file
        resource = '%s/%s' % (S3_BUCKET, object_name)
        str_to_sign = "PUT\n\n{mime_type}\n{expires}\n{amz_headers}\n/{resource}".format(
            mime_type=mime_type,
            expires=expires,
            amz_headers=amz_headers,
            resource=resource
        )

        sig = urllib.quote_plus(base64.encodestring(hmac.new(AWS_SECRET_ACCESS_KEY, str_to_sign, sha).digest()).strip())

        # The workaround. If our str_to_sign results in a hash that contains
        # any semblance of a plus sign, we need to generate a new random 
        # prefix and recompute.
        if "+" not in sig and "%2B" not in sig:
            break

    print "sig=%r" % sig

    url = 'https://%s.s3.amazonaws.com/%s' % (S3_BUCKET, object_name)
    return json.dumps({
        'signed_request':
        '{url}?AWSAccessKeyId={access_key}&Expires={expires}&Signature={sig}' \
            .format(url=url,access_key=AWS_ACCESS_KEY_ID, expires=expires, sig=sig),
        'url': url
    })


###############################################################################
# Serve static files for development
###############################################################################

file_suffix_to_mimetype = {
    '.css': 'text/css',
    '.jpg': 'image/jpeg',
    '.html': 'text/html',
    '.ico': 'image/x-icon',
    '.png': 'image/png',
    '.js': 'application/javascript'
}


@app.route("/<path:path>")
def static_file(path):
    try:
        f = open(path)
    except IOError, e:
        flask.abort(404)
        return
    root, ext = os.path.splitext(path)
    if ext in file_suffix_to_mimetype:
        return flask.Response(f.read(), mimetype=file_suffix_to_mimetype[ext])
    return f.read()


@app.route("/thumbnail/<path:path>")
def thumbnail(path):
    infile = open(path)

    size = THUMBNAIL_HEIGHT, THUMBNAIL_WIDTH

    image_buffer = StringIO()
    image = Image.open(infile)
    image.thumbnail(size, Image.ANTIALIAS)

    root, ext = os.path.splitext(path)
    image.save(image_buffer, format=FORMATS[ext.lower()])

    if ext in file_suffix_to_mimetype:
        return flask.Response(image_buffer.getvalue(), mimetype=file_suffix_to_mimetype[ext])

###############################################################################
# Custom error pages
###############################################################################

@app.errorhandler(404)
def page_not_found(e):
    return flask.render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(e):
    return flask.render_template("500.html"), 500


# 404 example page
@app.route("/404")
def error_404():
    flask.abort(404) 


# 500 example page
@app.route("/500")
def error_500():
    flask.abort(500)


###############################################################################
# Index
###############################################################################

@app.route("/", methods=["POST", "GET"])
def index():
    """
    Serves the index. Responsible for delegating to several 
    screens based on the state and type of request.
    """
   
    logged_in = is_logged_in()

    if flask.request.method == "GET" and logged_in: 
        email = flask.session["email"]

        return render_index(email, gravatar_url=make_gravatar_url(email),
                                   profile_url=make_gravatar_profile_url(email))

    if flask.request.method == "GET" and not logged_in:
        return redirect_to("beta_signup") 
    
    else:
        return redirect_to("login")


###############################################################################
## Project Selection 
###############################################################################

def get_projects_and_lusers(luser_id):
    return (models.db.session.query(models.Project, models.ProjectLuser)
                      .filter(models.ProjectLuser.luser_id==luser_id)
                      .filter(models.ProjectLuser.project_id==models.Project._id)
                      .all())


def render_project_selection(email, **kwargs):
    """
    Render a selection of projects that the user is a member of.
    
    Display the 'Manage' for projects if the user is an owner.
    """
    luser = get_luser_for_email(email)
    projects_and_lusers = get_projects_and_lusers(luser._id)

    return flask.render_template("project_selection.html", email=email,
                                 projects_and_lusers=projects_and_lusers,
                                 luser=luser, **kwargs)


def render_index(email, **kwargs):
    return render_project_selection(email, **kwargs)



###############################################################################
## Log out
###############################################################################


@app.route("/logout")
def logout():
    flask.session.pop("email", None)
    return redirect_to_index()


###############################################################################
## Log In
###############################################################################


def perform_login(email, password):
    """
    Verifies that the user exists and password is correct. If so,
    sets the 'logged_in' flag to true and redirects the user to
    the main screen.
    """
    template = "login.html"
   
    # query the luser
    luser = models.Luser.query.filter_by(email=email).first()

    # Ensure that there is a login for this luser.
    if luser is None:
        error = "Email is not registered."
        return flask.render_template(template, email_error=error)

    # If the hash is null, the user previously signed in with google.
    elif luser.pw_hash is None:
        return flask.render_template(template, password_error="Please sign-in with google.")

    # Ensure that this luser's password is correct.
    elif bcrypt.hashpw(password, luser.pw_hash) == luser.pw_hash:
        flask.session["email"] = email
        return flask.redirect(flask.url_for("index"))

    # Handle wrong passwords.
    else:
        error = "Password is incorrect."
        return flask.render_template(template, password_error=error)


def login_via_google(userinfo):
    email = userinfo["email"]

    # Match based on email so it works if your existing login is a google
    # account.
    luser = models.Luser.query.filter_by(email=email).first()

    # If the user has tried to log-in via google but has not
    # signed up yet, then do it now:
    if luser is None:
        luser = signup_via_google(userinfo)
    
    flask.session["email"] = luser.email
    return flask.redirect(flask.url_for("index"))
   

def signup_via_google(userinfo):
    """
    Comprehensive list of data available from google userinfo api:
        - id             <string>
        - email          <email>
        - verified_email <bool>
        - name           <string>
        - given_name     <string> -- this is the first name (eng)
        - family_name    <string> -- this is the last name (eng)
        - link           <url>
        - picture        <url>
        - gender         <string>
        - locale         <string>
    """
        
    luser = models.Luser(email=userinfo["email"], google_id=userinfo["id"])
    models.db.session.add(luser)
    models.db.session.commit()

    create_luser_data(luser, first_name=userinfo["given_name"],
                             last_name=userinfo["family_name"])
    return luser


###############################################################################
# Delete
###############################################################################

@app.route("/delete")
def delete():
    """
    Handles deletion of entities.
    """
    args = flask.request.args

    logged_in = is_logged_in()
    
    if logged_in and "card_id" in args and "project_name" in args:
        email = flask.session["email"]
        card_id = args.get("card_id")
        project_name = args.get("project_name")
        return perform_delete_card(email, card_id, project_name, args)

    elif logged_in and "pile_id" in args and "project_name" in args:
        email = flask.session["email"]
        pile_id = args.get("pile_id")
        project_name = args.get("project_name")
        return perform_delete_pile(email, pile_id, project_name)

    print "[EE] Insufficient parameters."
    flask.abort(400)



def perform_delete_card(email, card_id, project_name, args):
    """
    Deletes a card list item by id. Performs basic security checks
    first.

    TODO: refactor this
    """
    # Resolve the user
    luser = models.Luser.query.filter_by(email=email).first()
    if luser is None:
        print "[EE] No such user for email=%r" % email
        flask.abort(404)

    # Resolve the project
    project = models.Project.query.filter_by(name=project_name).first()
    if project is None:
        print "[EE] No such project for name=%r" % project_name
        flask.abort(404)

    # Assert that the user is a member of this project
    if luser not in project.lusers:
        print "[EE] User is not a member of this project."
        flask.abort(403)

    # Resolve the card
    card = models.Card.query.filter_by(_id=card_id).first()
    if card is None:
        print "[EE] No such card for _id=%r" % card_id
        flask.abort(404)

    # Assert that this card belongs to the resolved project
    if card.project_id != project._id:
        print "[EE] Card does not belong to the specified project."
        flask.abort(403)

    # Looks OK, lets delete it
    card = models.Card.query.filter_by(_id=card_id).first()
    models.db.session.delete(card)
    models.db.session.commit()

    if "redirect_to" in args:
        return flask.redirect("/project/%s/archives" % project.urlencoded_name)
    else:
        return redirect_to(page, name=project_name)


###############################################################################
# Add Project
###############################################################################


@app.route("/project/add", methods=["POST"])
def project_add():
    form = flask.request.form
    logged_in = is_logged_in()

    if "project_name" in form and logged_in:
        email = flask.session["email"]
        project_name = form["project_name"]
        return perform_project_add(email, project_name)

    elif not logged_in:
        print "[EE] Must be logged in."
        flask.abort(403)

    else:
        print "[EE] Missing parameters."
        flask.abort(400)


def perform_project_add(email, project_name):
    luser = get_luser_for_email(email)
    if luser is None:
        print "[EE] No user found for email=%r" % email
        flask.abort(404)

    project_name = project_name.strip()
    if len(project_name) == 0:
        print "[WW] client attempted to create project with blank name."
        return redirect_to_index()

    # Create a new project
    project = models.Project(name=project_name)
    models.db.session.add(project)
    models.db.session.flush()

    # Add the creator to this project as the project owner.
    project_luser = models.ProjectLuser(luser_id=luser._id, 
                                        project_id=project._id,
                                        is_owner=True)

    models.db.session.add(project_luser)
    models.db.session.commit()

    # Return to the project selection (Which is currently the index.)
    return redirect_to_index()


def get_luser_or_404(email):
    luser = get_luser_for_email(email)

    if luser is None:
        print "[EE] No user for email=%r" % email
        flask.abort(404)

    return luser


def get_email_or_403():
    if "email" in flask.session:
        email = flask.session["email"]
    else:
        print "[EE] Forbidden"
        flask.abort(403)

    return email


def get_project_or_404(project_name, luser_id):
    project = get_project(project_name, luser_id)

    if project is None:
        print "[EE] No project found for name=%r and luser_id=%r" % params
        flask.abort(404)

    return project


def add_to_project(callback):
    """
    Checks perms/credentials and passes off control to a callback
    which is responsible for performing the addition of an entity
    to the specified project.

    Callback must implement desired adding functionality.

    Params:
        callback    -- def callback(email, project_name, text)
    """

    logged_in = is_logged_in()
    has_all_params = True

    if "email" in flask.session:
        email = flask.session["email"]
    else:
        # do not set has_all_params to true here. We're using email
        # as a session token.
        email = None

    form = flask.request.form

    if "project_name" in form:
        project_name = form["project_name"]
    else:
        has_all_params = False
        project_name = None

    if "text" in form:
        text = form["text"]
    else:
        has_all_params = False
        text = None

    if logged_in and has_all_params:
        return callback(email, project_name, text, form=form)

    elif not logged_in and has_all_params:
        print "[EE] Requires login."
        flask.abort(403)

    else:
        print "[EE] Insufficient parameters."
        flask.abort(400)

##############################################################################
# Privilege Decorators 
#
# These functions are reusable security measures that can 'decorate'
# any view function in order to prevent unauthorized users from 
# obtaining access to them.
##############################################################################


def do_check_project_privileges(**kwargs):
    # Obtain email from session, otherwise, error 403
    email = get_email_or_403()

    # Obtain the luser, or return not found.
    luser = get_luser_or_404(email)
 
    # Do this to make sure the luser is a member of the project. 
    project = get_project_or_404(kwargs["project_name"], luser._id)

    kwargs["email"] = email
    kwargs["luser"] = luser
    kwargs["project"] = project

    return kwargs


def check_project_privileges(func):
    """
    Decorator to ensure that the user has a valid session before allowing him
    to execute the view function, and that he is a member of the target
    project.
    """
    @wraps(func)
    def wrap(**kwargs):
        kwargs = do_check_project_privileges(**kwargs)
        return func(**kwargs)
    return wrap


def check_luser_privileges(func):
    """
    Just ascertains that the user is logged in and passes the luser object
    and email to the view function.
    """
    @wraps(func)
    def wrap(**kwargs):
        email = get_email_or_403()
        luser = get_luser_or_404(email)

        kwargs["email"] = email
        kwargs["luser"] = luser

        return func(**kwargs)
    return wrap


def is_owner_or_403(luser, project):
    """
    Throws error 403 if 'luser' is not an owner of 'project'
    """
    is_owner = (models.db.session.query(models.ProjectLuser)
                      .filter(models.ProjectLuser.luser_id==luser._id)
                      .filter(models.ProjectLuser.project_id==project._id)
                      .filter(models.ProjectLuser.is_owner==True).first())

    if is_owner == None:
        flask.abort(403)
        

def check_owner_privileges(func):
    """
    Decorator to ensure that the user has administrator access before
    allowing him to execute the view function.
    """
    @wraps(func)
    def wrap(**kwargs):
        kwargs = do_check_project_privileges(**kwargs)
        is_owner_or_403(kwargs["luser"], kwargs["project"])
        return func(**kwargs)
    return wrap


##########################################################################
## Lists 
##########################################################################

@app.route("/<project_name>/list/<int:list_id>/delete")
@check_project_privileges
def list_delete(list_id=None, luser=None, **kwargs):
    """
    'Deletes' a list. Note, lists are NEVER really deleted,
    since any archived cards still related to them will require
    their existence.
    """

    # When 'deleting' a list, automatically archive all its cards.
    cards = models.Card.query.filter_by(pile_id=list_id).all()
    for card in cards:
        card.is_archived = True


    pile = models.Pile.query.filter_by(_id=list_id).first()
    pile.is_deleted = True
    models.db.session.commit()

    return respond_with_json(dict(status=True))


###############################################################################
## Invites
###############################################################################

@app.route("/project/<project_name>/members")
@check_owner_privileges
def members(project=None, **kwargs):
    # We also need to display project invites
    invites = (models.ProjectInvite.query.filter_by(project_id=project._id)
                     .all())

    return cc_render_template("invites.html", members=members, 
                              invites=invites, project=project, **kwargs)


@app.route("/project/<project_name>/members/<int:member_id>/remove")
@check_owner_privileges
def remove_member(project=None, member_id=None, **kwargs):
    
    member = (models.ProjectLuser.query.filter_by(project_id=project._id)
                                       .filter_by(luser_id=member_id)
                                       .first())
    models.db.session.delete(member)
    models.db.session.commit()
                
    return respond_with_json({ "status" : "success" })


###############################################################################
# Activity
###############################################################################
ACTIVITY_ITEMS_PER_PAGE = 50

@app.route("/project/<project_name>/activity", methods=["GET"])
@check_project_privileges
def activity(project=None, **kwargs):
    page = int(request.args.get('page', 0))
    start = page * ACTIVITY_ITEMS_PER_PAGE
    end = start + ACTIVITY_ITEMS_PER_PAGE

    total = models.Activity.query.count()
    activity = (models.Activity.query.filter_by(project_id=project._id)
                      .order_by(models.Activity.created.desc())
                      .offset(start).limit(end).all())
    is_end = end >= total
    next_page = page + 1

    return flask.render_template("activity_list.html", activity=activity,
                                 is_end=is_end, next_page=next_page,
                                 **kwargs)


##############################################################################
## Cards
##############################################################################

def render_card(template, **kwargs):
    card_id = kwargs["card_id"]
    project = kwargs["project"]

    card = query_card(card_id, project._id)

    # parameterize comment handler urls for code reuse.
    comment_delete_url = "/project/%s/comment/delete/" % project.name
    comment_edit_url = "/project/%s/comments/edit/" % project.name
    
    return flask.render_template(template, card=card, comments=card.comments,
                                 comment_delete_url=comment_delete_url,
                                 comment_edit_url=comment_edit_url, **kwargs)


@app.route("/project/<project_name>/cards/<int:card_id>/attachments", methods=["POST"])
@check_project_privileges
def card_get_attachments(card_id=None, luser=None, **kwargs):
    """
    Called via ajax to refresh attachments after an attachment is added.
    """
    url = flask.request.json["url"]
    filename = flask.request.json["filename"]

    attachment = models.CardFile(card_id=card_id, luser_id=luser._id, 
                    filename=filename, url=url)
    
    models.db.session.add(attachment)
    models.db.session.commit()

    stuff = render_card("card_attachments.html", card_id=card_id, luser=luser, **kwargs)
    print "stuff=%r" % stuff
    return stuff


@app.route("/project/<project_name>/cards/<int:card_id>/comment", methods=["POST"])
@check_project_privileges
def cards_comment(project_name=None, luser=None, project=None, card_id=None,
                  **kwargs):
    """
    Update the database when a user posts a comment.
    """

    text = request.form["text"].encode("UTF-8").strip()

    comment = models.CardComment(card_id=card_id, luser_id=luser._id, 
                                 text=text)
    models.db.session.add(comment)
    models.db.session.commit()

    comments = (models.CardComment.query.filter_by(card_id=card_id)
                      .order_by(models.CardComment.created.desc())
                      .all())

    comment_delete_url = "/project/%s/comment/delete/" % project.name
    comment_edit_url = "/project/%s/comments/edit/" % project.name

    activity_logger.log(luser._id, project._id, card_id, "card_comment")
  
    email_notify.send_card_comment_email(project.recipients, 
        luser.profile.username, comment.text, comment.card.text)

    return flask.render_template("comments.html", 
                comments=comments, luser=luser,
                comment_delete_url=comment_delete_url,
                comment_edit_url=comment_edit_url)


@app.route("/project/<project_name>/report/edit/<int:report_id>",
    methods=["GET", "POST"])
@check_project_privileges
def report_edit(report_id, luser=None, **kwargs):
    report = (models.MemberReport.query
                    .filter_by(_id=report_id,luser_id=luser._id)
                    .first())
    if request.method == "POST":
        report.text = request.form.get("text", "").strip()
        models.db.session.commit()

        resp = flask.render_template_string("{{ text|markdown }}",
                                            text=report.text)
        print resp
        return resp
    else:
        return report.text


@app.route("/project/<project_name>/reports/<int:report_id>/comment",
    methods=["POST"])
@check_project_privileges
def reports_comment(project_name=None, project=None, luser=None, 
    report_id=None, **kwargs):

    text = request.form["text"].encode("UTF-8").strip()

    comment = models.ReportComment(report_id=report_id, luser_id=luser._id,
                                   text=text)
    models.db.session.add(comment)
    models.db.session.commit()

    comment_delete_url = "/project/%s/report-comments/delete/" % project_name
    comment_edit_url = "/project/%s/report-comments/edit/" % project_name

    comments = (models.ReportComment.query.filter_by(report_id=report_id)
                      .order_by(models.ReportComment.created.desc())
                      .all())

    email_notify.send_report_comment_email(project.recipients,
         luser.profile.username, comment.text, comment.report.subject)
                                    
    return flask.render_template("comments.html", luser=luser,
                                 comment_delete_url=comment_delete_url,
                                 comment_edit_url=comment_edit_url,
                                 comments=comments) 

## TODO: refactor/modularize this

def delete_comment(Comment, comment_id):
    comment = Comment.query.filter_by(_id=comment_id).first()
    models.db.session.delete(comment)
    models.db.session.commit()
    return comment


@app.route("/project/<project_name>/comment/delete/<int:comment_id>",
           methods=["POST"])
@check_project_privileges
def delete_card_comment(project=None, luser=None, project_name=None,
                   comment_id=None, **kwargs):
    """
    Delete a comment.
    """
    comment = delete_comment(models.CardComment, comment_id)
    card_id = comment.card._id
    activity_logger.log(luser._id, project._id, card_id, "card_comment_delete")
    return respond_with_json({ "status" : "success" })


@app.route("/project/<project_name>/report-comments/delete/<int:comment_id>",
           methods=["POST"])
@check_project_privileges
def delete_report_comment(project=None, luser=None, project_name=None,
                   comment_id=None, **kwargs):
    """
    Delete a comment.
    """
    delete_comment(models.ReportComment, comment_id)
    return respond_with_json({ "status" : "success" })



@app.route("/project/<project_name>/card/<int:card_id>/archive")
@check_project_privileges
def archive(luser=None, project=None, card_id=None, **kwargs):
    """
    Handles archival of cards.
    """
    card = models.Card.query.filter_by(_id=card_id).first()
    card.is_archived = True
    models.db.session.commit()
   
    activity_logger.log(luser._id, project._id, card_id, "card_archive")

    return respond_with_json({ "status" : "success",
                               "card_id" : card._id,
                               "message" : "Archived card %d" % card._id })


@app.route("/project/<project_name>/cards/<int:card_id>/restore",
            methods=["GET"])
@check_project_privileges
def restore_card(project=None, card_id=None, **kwargs):
    """
    Handles restoration of cards to their state before archiving.

    (Really just needs to flip a boolean)
    """
    card = models.Card.query.filter_by(_id=card_id).first()
    card.is_archived = False
    card.pile.is_deleted = False
    models.db.session.commit()

    return flask.redirect("/project/%s/archives" % project.urlencoded_name)


def card_set_attributes(project=None, card_id=None, **kwargs):
    """
    Generically mutate the values of a card based on what keys 
    and values are passed in the payload json object.
    """
    card = models.Card.query.filter_by(_id=card_id).first()
    json = flask.request.json

    for k in json.keys():
        print k, json[k]
        setattr(card, k, json[k])
    
    models.db.session.commit()
    return respond_with_json({ "status" : "success" })


@app.route("/project/<project_name>/cards/<int:card_id>/select_milestone",
            methods=["POST"])
@check_project_privileges
def card_select_milestone(project=None, card_id=None, **kwargs):
    return card_set_attributes(project=project, card_id=card_id, **kwargs)   


@app.route("/project/<project_name>/cards/<int:card_id>/assign_to",
            methods=["POST"])
@check_project_privileges
def card_assign_to(project=None, card_id=None, **kwargs):
    return card_set_attributes(project=project, card_id=card_id, **kwargs)   


@app.route("/project/<project_name>/cards/edit/<int:card_id>", methods=["POST"])
@check_project_privileges
def card_edit(project=None, luser=None, project_name=None,card_id=None,
              **kwargs):
    """
    Allow editing of card properties from within the modal.
    """
    # Here we enumerate properties that can possibly be edited. Only
    # one is sent at a time.
    if "text" in request.form:
        value = request.form["text"].strip()
        params = dict(text=value)
    elif "description" in request.form:
        value = request.form["description"].strip()
        params = dict(description=value)
    else:
        flask.abort(400)

    (models.Card.query.filter(and_(models.Card._id==card_id,
                                   models.Card.project_id==project._id))
                     .update(params))
    models.db.session.commit()
    activity_logger.log(luser._id, project._id, card_id, "card_edit")
    return value


def edit_comment(Comment, luser, comment_id):
    value = request.form.get("text", "").strip()

    comment = (Comment.query.filter(and_(Comment._id==comment_id,
                                        Comment.luser_id==luser._id))
                .first())
    comment.text = value
    models.db.session.commit()
    return comment


@app.route("/project/<project_name>/comments/edit/<int:comment_id>", methods=["POST"])
@check_project_privileges
def edit_card_comment(project=None, luser=None, project_name=None, 
                        comment_id=None, **kwargs):

    comment = edit_comment(models.CardComment, luser, comment_id)
    activity_logger.log(luser._id, project._id, comment.card_id, 
                        "edit_comment")
    return comment.text


@app.route("/project/<project_name>/report-comments/edit/<int:comment_id>", methods=["POST"])
@check_project_privileges
def edit_report_comment(project=None, luser=None, project_name=None, 
                        comment_id=None, **kwargs):

    comment = edit_comment(models.ReportComment, luser, comment_id)
    return comment.text


def query_card(card_id, project_id):
    return (models.Card.query.filter(and_(models.Card._id==card_id,
                   models.Card.project_id==project_id))
                   .first())


@app.route("/project/<project_name>/cards/<int:card_id>", methods=["GET"])
@check_project_privileges
def cards_get(**kwargs):
    """
    Used to render a card in a modal dialog.
    """

    is_archived = ("is_archived" in flask.request.args and
                   flask.request.args["is_archived"])

    if is_archived:
        return render_card("archived_card.html", **kwargs)
    else:
        return render_card("card.html", **kwargs)


@app.route("/project/<project_name>/cards/<int:card_id>/description", methods=["POST"])
@check_project_privileges
def cards_description(project=None, card_id=None, **kwargs):
    description = request.json["description"]
    card = models.Card.query.filter_by(_id=card_id).first()
    card.description = description
    models.db.session.commit()
    return respond_with_json({ "status" : "success",
                               "description" : description })


@app.route("/project/<project_name>/cards/<int:card_id>/score", methods=["POST"])
@check_project_privileges
def card_score(project_name=None, card_id=None, project=None, **kwargs):
    
    card = query_card(card_id, project._id)
    
    score = flask.request.json["score"]

    if score is not None: 
        score = int(score)

    print "score = %r" % score
    card.score = score
    
    models.db.session.commit()
    return respond_with_json({ "status" : "success",
                               "message" : "updated card %d" % card._id })


@app.route("/cards/reorder", methods=["POST"])
def cards_reorder():
    """
    Must be called at the end of any drag on the card list. Used to update
    the new sort order of the card-list in the database. Also repositions
    cards in appropriate piles.
    """

    print "%r" % flask.request.json
    for update in flask.request.json["updates"]:
        _id = int(update["_id"])
        number = int(update["number"])
        pile_id = int(update["pile_id"])
        print "[DD] update=%r" % update
        models.Card.query.filter_by(_id=_id).update(dict(number=number, 
                                                         pile_id=pile_id))
    
    models.db.session.commit()
    return respond_with_json({"status" : "success" })


@app.route("/project/<project_name>/archives", methods=["GET", "POST"])
@check_project_privileges
def archives(**kwargs):
    return cc_render_template("archived_cards.html", **kwargs)


@app.route("/project/<project_name>/minicards/<int:card_id>")
@check_project_privileges
def minicards_get(card_id=None, **kwargs):
    card = models.Card.query.filter_by(_id=card_id).first() 
    return flask.render_template("minicard.html", card=card, **kwargs)


@app.route("/project/<project_name>/cards/add", methods=["POST"])
@check_project_privileges
def cards_add(project=None, luser=None, **kwargs):
    card = models.Card.create(project, request.form["pile_id"], request.form["text"])
    activity_logger.log(luser._id, project._id, card._id, "card_created")
    return flask.render_template("minicard.html", card=card, luser=luser,
                                 project=project, **kwargs)


@app.route("/project/<project_name>/cards/<int:card_id>/complete",
            methods=["POST"])
@check_project_privileges
def card_toggle_is_completed(project=None, card_id=None, luser=None,
                             **kwargs):
    """
    Facilitate the toggling of the Card's "is_completed" state.
    """
    state = flask.request.json["state"]

    print "state=%r" % state

    # Update the is_complete boolean
    card = models.Card.query.filter_by(_id=card_id).first()
    card.is_completed = not state
    models.db.session.flush()

    # Also insert or delete a CardCompletion object, for the charts.
    card_completion = (models.CardCompletions.query.filter_by(card_id=card_id) 
                                                  .first())

    # If the card is complete, and there is no entry in the card
    # completion table, then make one now:
    if card.is_completed and card_completion is None:
        card_completion = models.CardCompletions(card_id=card._id,
                                                luser_id=luser._id)
        models.db.session.add(card_completion)

    # If the card is not complete, and an entry exists in the card
    # completion table, then remove it.
    elif not card.is_completed and card_completion is not None:
        models.db.session.delete(card_completion)

    if card.is_completed:
        type = "card_finished"
    else:
        type = "card_incomplete"

    models.db.session.commit()

    activity_logger.log(luser._id, project._id, card_id, type)

    return respond_with_json(dict(state=card.is_completed))

############################################################################
# Piles
############################################################################

@app.route("/piles/reorder", methods=["POST"])
def piles_reorder():
    """
    Must be called after piles are moved to update order.
    """
    for update in flask.request.json["updates"]:
        _id = int(update["_id"])
        number = int(update["number"])
        models.Pile.query.filter_by(_id=_id).update(dict(number=number))
    
    models.db.session.commit()
    return respond_with_json({"status" : "success" })


############################################################################
## Milestones
############################################################################

@app.route("/project/<project_name>/milestones/add", methods=["POST"])
@check_project_privileges
def milestones_add(project=None, **kwargs):
    """
    Adds a new milestone. Confirms that user is an owner of this project,
    first.
    """
    if project is None:
        raise ValueError("project required.")

    name = flask.request.form["name"]
    milestone = models.Milestone(name=name, project_id=project._id)
    models.db.session.add(milestone)
    models.db.session.commit()
    
    return redirect_to("project_progress", **kwargs)


@app.route("/project/<project_name>/milestone/<int:milestone_id>/accept",
            methods=["POST"])
@check_project_privileges
def milestone_toggle_is_accepted(project=None, milestone_id=None, **kwargs):
    """
    Facilitate the toggling of the milestone's is_accepted attribute.
    """
    state = flask.request.json["state"]
    print "state=%r" % state

    milestone = models.Milestone.query.filter_by(_id=milestone_id).first()

    milestone.is_approved = not state

    models.db.session.commit()

    return respond_with_json(dict(state=milestone.is_approved))


##########################################################################
# Piles
##########################################################################

def add_pile(project, name="Unnamed List"):
    pile = models.Pile(project_id=project._id, name=name)
    models.db.session.add(pile)
    models.db.session.commit()
    return pile


@app.route("/<project_name>/piles/add", methods=["POST"])
@check_project_privileges
def pile_add(project=None, luser=None, **kwargs):
    pile = add_pile(project, request.form["text"])
    return cc_render_template("list.html", project=project,
                              luser=luser, pile=pile, **kwargs)


@app.route("/project/<name>/piles/edit/<int:pile_id>", methods=["POST"])
def pile_edit(name,pile_id):
    # Resolve the project
    project = models.Project.query.filter_by(name=name).first()
    if project is None:
        print "[EE] No such project for name=%r" % project_name
        flask.abort(404)

    # Obtain email from session, otherwise, error 403
    email = get_email_or_403()

    # Obtain the luser, or return not found.
    luser = get_luser_or_404(email)
 
    # Do this to make sure the luser is a member of the project. 
    project = get_project_or_404(name, luser._id)
 
    name = flask.request.form["value"].strip()

    params = dict(name=name)
    print "pile_id = %d" % pile_id

    (models.Pile.query.filter(and_(models.Pile._id==pile_id,
                 models.Pile.project_id==project._id))
                .update(params))

    models.db.session.commit()

    return name

       
###############################################################################
## Projects
###############################################################################

def get_project(project_name, luser_id):
    """
    Obtains a project if and only if the name matches, and the luser is a
    member.
    """
    query = models.Project.query

    return  (query.filter(and_(models.Project.name==str(project_name),
                 models.ProjectLuser.luser_id==luser_id,
                 models.ProjectLuser.project_id==models.Project._id))
                 .first())


def cc_render_template(filename, email=None, **kwargs):
    """ 
    Wraps flask's render_template function to inject values common
    to most screens.
    """

    if email is None:
        raise ValueError("email required.")

    gravatar_url = make_gravatar_url(email)
    profile_url = make_gravatar_profile_url(email)

    return flask.render_template(filename, email=email,
                                 gravatar_url=gravatar_url,
                                 profile_url=profile_url,
                                 **kwargs)


def render_project(project_name, email):
    """
    Obtain necessary data for showing the user a project and bind it
    with the 'project.html' template.

    Responds to user with rendered project output.
    """

    luser = get_luser_for_email(email)
    if luser is None:
        print "[EE] No user found for email=%r" % email
        flask.abort(404)

    project = get_project(project_name, luser._id)
    if project is None:
        params = (project_name, luser._id)
        print "[EE] No project found for name=%r and luser_id=%r" % params
        flask.abort(404)


    json_pile_ids = json.dumps([p.pile_uuid for p in project.piles])

    return cc_render_template("project.html", email=email, project=project,
                              json_pile_ids=json_pile_ids, luser=luser) 


@app.route("/project/<name>")
def project(name):
    if is_logged_in():        
        email = flask.session["email"]
        return render_project(name, email)
    else:
        print "[EE] Must be logged in."
        flask.abort(403)


@app.route("/project/<project_name>/progress")
@check_owner_privileges
def project_progress(project_name=None, luser=None,  project=None, **kwargs):
    """
    Renders the project management view. 

    This view should allow project owners to create milestones, and
    view progress.
    """
    member = models.ProjectLuser.query.filter_by(luser_id=luser._id).first()

    # Calculate the team cadence.
    now = datetime.utcnow().date()
    week_ago = now - timedelta(days=14)
    print "%r" % now
    completions = (models.CardCompletions.query
                   .filter(models.CardCompletions.card_id==models.Card._id)
                   .filter(models.Card.project_id==project._id)
                   .filter(models.CardCompletions.created > week_ago)
                   .filter(models.CardCompletions.created < now).all())

    team_cadence_data = []
    team_cadence_map = {}

    for i in range(15):
        date = week_ago + timedelta(days=i)

        formatted_date = date.strftime("%b %d")

        team_cadence_data.append([0, formatted_date])
        team_cadence_map[date] = i

    for c in completions:
        date = c.created.date()
        team_cadence_data[team_cadence_map[date]][0] += 1
   
    return cc_render_template("project_progress.html", luser=luser,
                               is_owner=member.is_owner, project=project,
                               team_cadence_data=team_cadence_data,
                               **kwargs)



@app.route("/project/<project_name>/luser/<int:luser_id>/is_owner",
            methods=["POST"])
@check_owner_privileges
def toggle_owner_permission(project_name=None, luser_id=None, project=None,
                            luser=None, **kwargs):
    """
    Handles clicks on the project management screen administrator checkbox.
    """
    member = (models.ProjectLuser.query.filter_by(luser_id=luser_id,
                 project_id=project._id).first())
                                                 
    member.is_owner = not member.is_owner 
    models.db.session.commit()

    return respond_with_json({"is_owner" : member.is_owner,
                              "luser_id" : luser_id })


@app.route("/project/<project_name>/add_member", methods=["POST"])
@check_owner_privileges
def project_add_member(project=None, luser=None, **kwargs):
    """
    If user is already a codecolab member, add them to the project.
    Otherwise, send an email invite to CodeColab and create an
    entry in the ProjectInvite table. This will later be read back when the
    user signs up and used to add them to any projects they have been invited
    to, which still exist at the time.
    """
    email = flask.request.form["email"].strip()
    member = models.Luser.query.filter_by(email=email).first()

    # If the user is not yet signed up
    if member is None:
        existing_invite = models.ProjectInvite.query.filter_by(email=email).first()
        if existing_invite is None:
            # Create an invite that will be checked when the user 
            # signs up and used to add them to any projects they
            # have been invited to.
            invite = models.ProjectInvite(luser_id=luser._id,
                                          project_id=project._id,
                                          email=email)
            models.db.session.add(invite)

            # Also create a BetaSignup and activate it so that the user
            # doesn't get stuck at the beta wall.
            beta = models.BetaSignup(email=email, is_activated=True)
            models.db.session.add(beta)
            models.db.session.commit()
            
            flask.flash("Invited %s to the project." % email)
        else: 
            flask.flash("%s was already invited to this project. Re-sending "
                        " email." % email)
        
        try:
            email_notify.project_invite(project, email)
        except:
            flask.flash("Failed to send email. Is %s added to amazon SES?" % email)

    # The user is signed up already, check if hes a project member. If not,
    # add him.
    else:
        existing = (models.ProjectLuser.query
                          .filter(models.ProjectLuser.project_id==project._id)
                          .filter(models.ProjectLuser.luser_id==models.Luser._id)
                          .filter(models.Luser.email==email).first())

        if existing is None:
            new_member = models.Luser.query.filter_by(email=email).first()

            member = models.ProjectLuser(project_id=project._id,
                                         luser_id=new_member._id,
                                         is_owner=False)

            models.db.session.add(member)
            models.db.session.commit()
            flask.flash("Added %s to the project." % email)
        else:
            flask.flash("%s is already a member of this project." % email)
        
    return flask.redirect("/project/%s/members" % project.name)


###############################################################################
## Member Office Hours 
###############################################################################

@app.route("/project/<project_name>/office_hours/update", methods=["POST"])
@check_project_privileges
def update_office_hours(project=None, luser=None, **kwargs):
    weekday = request.json["weekday"]
    hours = request.json["hours"]

    # Drop all the existing time ranges for this day,
    # we are going to update them.
    schedule = (models.MemberSchedule.query
                      .filter_by(project_id=project._id)
                      .filter_by(luser_id=luser._id).first())

    day = models.Day.query.filter_by(ordinal=weekday).first()

    ranges = (models.MemberScheduleTimeRanges.query
                    .filter_by(day_id=day._id)
                    .filter_by(schedule_id=schedule._id)
                    .all())
        
    for r in ranges:
        models.db.session.delete(r)

    start_time = None
    end_time = None

    hours_len = len(hours)


    # State machine converts discrete hour units to continuous
    # time ranges.
    # TODO: Figure out where you overwrote the 'range' ref.
    for i in __builtins__.range(hours_len):
        
        if start_time is None:
            start_time = datetime.time(hour=hours[i])

        # IF: The next hour is present 
        #   AND: The next hour is more than one more than the current
        #        one.
        # THEN: We should mark the current hour as the end time, 
        #       save this time range, and begin a new time range 
        #       on the next iteration. 
        if ((i + 1 < hours_len and hours[i + 1] > hours[i] + 1) or
            (i + 1 == hours_len and start_time != None)):     

            # Calculate end_time.
            end_hour = hours[i] + 1 
           
            # The last hour will have to be encoded using lim->24 precision,
            # as rolling over to the next day to encode it is not possible the
            # way our ranges are implemented.
            if end_hour == 24:
                end_time = datetime.time(hour=23, minute=59, second=59, microsecond=999999)
            else:
                end_time = datetime.time(hour=end_hour)

            
            # Save new time range.  
            params = dict(schedule_id=schedule._id, day_id=day._id,    
                          start_time=start_time, end_time=end_time)
            range = models.MemberScheduleTimeRanges(**params)
            models.db.session.add(range)
           
            # Reset state.
            start_time = end_time = None             

    models.db.session.commit()
    return respond_with_json({ "status" : "success" })


@app.route("/project/<project_name>/office_hours", methods=["GET","POST"])
@check_project_privileges
def member_schedule(luser=None, project=None, **kwargs):
    """
    Defines a schedule per-user per-project.
    """
    # we need this every time
    day_collection = models.Days()
    days = day_collection.days

    # Check for the existence of a schedule. If it does not exist,
    # create it.
    schedule = (models.MemberSchedule.query
                      .filter_by(luser_id=luser._id, project_id=project._id)
                      .first())

    if schedule is None:
        schedule = create_default_schedule(luser, project, day_collection)
   
    if request.method == "POST":
        # IF the user clicked the "Add Day" button, add a day to their
        # schedule.
        if "add_day" in request.form:
            print "add day!"
            time_range = models.MemberScheduleTimeRanges(schedule_id=schedule._id)
            models.db.session.add(time_range)
            models.db.session.commit()

        # IF the user clicked the "Remove" button, remove that time 
        # range from their schedule.
        elif "remove" in request.form:
            range_id = int(request.form["range_id"])
            time_range = (models.MemberScheduleTimeRanges.query
                            .filter_by(_id=range_id).first())
            models.db.session.delete(time_range)
            models.db.session.commit()

        else: 
        # Otherwise, we must be updating days or times,
        # as it was the programmatic submit from change()
            range_ids = request.form.getlist("range_id")
            day_updates = request.form.getlist("day")
            start_time_updates = request.form.getlist("start_time")
            end_time_updates = request.form.getlist("end_time")
            zipped = zip(range_ids, day_updates, start_time_updates, end_time_updates)

            format = "%I:%M%p"
            convert = lambda t: datetime.strptime(t, format).time()

            for (_id, day, start_time, end_time) in zipped:
                time_range = (models.MemberScheduleTimeRanges.query
                                .filter_by(_id=int(_id)).first())

                time_range.day_id = day
                time_range.start_time = convert(start_time)
                time_range.end_time = convert(end_time)
        
            models.db.session.commit()


    # Sort members circularly by timezone offset, starting with the
    # luser who is requesting the page, then ordering the closest 
    # to him first, in the positive direction.

    # First, sort by timezone.
    key = lambda k : k.luser.profile.tz_utc_offset_seconds
    project.members.sort(key=key)
   
    # Next, find the user who is requesting this:
    i = 0
    for other in project.members:
        if luser._id == other.luser._id:
            break
        i += 1

    # Now, reorder circularly from that index:
    sorted_members = project.members[i:] + project.members[:i]
    
    # Calculate relative hours for each member, relative to the
    # viewers hours 
    member_hours = {} 
    hours = range(24)
    for m in sorted_members:
        # don't convert our own
        if m.luser_id == luser._id:
            member_hours[luser._id] = hours
            continue

        hours_offset = m.luser.profile.tz_utc_offset_hours
        relative_offset = luser.profile.tz_utc_offset_hours - hours_offset
        print "%r" % relative_offset
        relative_hours = hours[relative_offset:] + hours[:relative_offset]
        member_hours[m.luser_id] = relative_hours

    if "weekday" in request.args:
        weekday = int(request.args["weekday"])
    else:
        weekday = datetime.now(timezone(luser.profile.timezone)).weekday()
   
    weekday_id = models.Day.query.filter_by(ordinal=weekday).first()._id

    return cc_render_template("member_schedule.html", days=days, luser=luser,
                              project=project, schedule=schedule, 
                              sorted_members=sorted_members,
                              hours=hours, member_hours=member_hours,
                              weekday=weekday, weekday_id=weekday_id,
                              **kwargs)


def create_default_schedule(luser, project, day_collection):
    " creates default 9-5 schedule"
    days = day_collection.days
    day_map = day_collection.day_map

    schedule = models.MemberSchedule(project_id=project._id, luser_id=luser._id)
    models.db.session.add(schedule)
    models.db.session.flush()

    for d in days:
        r = models.MemberScheduleTimeRanges(schedule_id=schedule._id,   
                                                day_id=day_map[d.name])
        models.db.session.add(r)
    
    models.db.session.commit()
    
    return schedule


###############################################################################
## Reports
###############################################################################

REPORTS_PER_PAGE = 10
@app.route("/project/<project_name>/reports", methods=["GET", "POST"])
@check_project_privileges
def member_reports(luser=None, project=None, **kwargs):
    
    if request.method == "POST":
        text = request.form["text"]
        subject = request.form["subject"]

        report = models.MemberReport(text=text, subject=subject,
                                     luser_id=luser._id, project_id=project._id)
        models.db.session.add(report)
        models.db.session.commit()

        email_notify.member_report(project.recipients, reports, subject)

    
    total = models.MemberReport.query.count()

    # TODO: refactor using class based views to avoid duplication
    report_edit_url = "/project/%s/report/edit/" % project.name
    comment_delete_url = "/project/%s/report-comments/delete/" % project.name
    comment_edit_url = "/project/%s/report-comments/edit/" % project.name

    return cc_render_template("reports.html", luser=luser, project=project,
                              report_edit_url=report_edit_url,
                              reports=project.reports[:REPORTS_PER_PAGE],
                              has_next=total > REPORTS_PER_PAGE,
                              comment_delete_url=comment_delete_url,
                              comment_edit_url=comment_edit_url,
                              next_page=1, **kwargs)


@app.route("/project/<project_name>/team_reports")
@check_project_privileges
def team_reports(luser=None, project=None, **kwargs):
    page = int(request.args.get('page', 0))
    start = page * REPORTS_PER_PAGE 
    end = start + REPORTS_PER_PAGE 

    total = models.MemberReport.query.count()
    reports = (models.MemberReport.query.filter_by(project_id=project._id)
                      .order_by(models.MemberReport.created.desc())
                      .offset(start).limit(end).all())

    has_next = total > end
    next_page = page + 1

    return flask.render_template("team_reports_loop.html", reports=reports,
                                 has_next=has_next, next_page=next_page,
                                 project=project, luser=luser,**kwargs)


@app.route("/project/<project_name>/reports/<int:report_id>")
@check_project_privileges
def get_report(luser=None, project=None, report_id=None, **kwargs):

    report = models.MemberReport.query.filter_by(_id=report_id).first()

    return flask.render_template("report.html", luser=luser, project=project,
                                 report=report, **kwargs)


###############################################################################
## User Profile
###############################################################################

@app.route("/profile/<int:luser_id>", methods=["GET", "POST"])
@check_luser_privileges
def get_profile(luser_id, luser=None, **kwargs):
    """
    Obtain a user's profile given their id.
    """
    profile = models.LuserProfile.query.filter_by(luser_id=luser_id).first()
   
    themes = ["light", "dark"]

    if flask.request.method == "GET":
        if profile is None:
            return flask.abort(404)

        # If this request does not originate from the owner of the profile
        if luser._id != luser_id:
            # Then serve them a read-only profile:
            return cc_render_template("profile_readonly.html", luser=luser, 
                                      profile=profile, **kwargs)
        else:
            # Otherwise, let them edit their profile:
            return cc_render_template("profile.html", luser=luser, 
                                      profile=profile,
                                      timezones=pytz.all_timezones,
                                      themes=themes,
                                      **kwargs)

    else:
        # Don't allow users to edit the profiles of others.
        if luser._id != luser_id:
            return flask.abort(403)

        profile.first_name = flask.request.form["first_name"]
        profile.last_name = flask.request.form["last_name"]
        profile.username = flask.request.form["username"]
        profile.timezone = flask.request.form["timezone"]
        profile.theme = flask.request.form["theme"]

        models.db.session.commit()

        flask.flash("Profile updated.")
        return cc_render_template("profile.html", luser=luser, 
                                  profile=profile,
                                  timezones=pytz.all_timezones,
                                  themes=themes,
                                  **kwargs)


###############################################################################
## Password Recovery
###############################################################################

@app.route("/reset/<uuid>", methods=["POST", "GET"])
def password_reset(uuid):
    """
    Password reset controller.

        * POST checks the user's reset uuid (from URL) and if it's OK allows
          the user to reset his password.

        * GET serves the password reset page.
    """
    request = models.ForgottenPasswordRequest.query.filter_by(uuid=uuid).first()
    
    if flask.request.method == "POST":
        password = flask.request.form["password"].strip()
        confirm = flask.request.form["confirm"].strip()
       
        if len(password) < 8:
            password_error = "Password must be at least 8 characters."

            return flask.render_template("reset.html", reset_token=uuid,
                                         password_error=password_error)

        if password != confirm:
            return flask.render_template("reset.html", reset_token=uuid,
                                         password_error="Passwords do not match.")
       
        # Success, update the user's password. 
        user = models.Luser.query.filter_by(_id=request.luser_id).first()
        user.pw_hash = bcrypt.hashpw(password, bcrypt.gensalt())
        models.db.session.commit()
    
        # Delete the password request.
        models.db.session.delete(request)
        models.db.session.commit()
 
        flask.flash("Your password has been reset. You may now log in.")
        return redirect_to("login")

    else:
        
        if request is None:
            flask.flash("Invalid password reset token.")
            return redirect_to_index()

        if request.expiration < datetime.utcnow():
            flask.flash("Expired password reset token.")
            return redirect_to_index()

        return flask.render_template("reset.html", reset_token=uuid)


@app.route("/forgot", methods=["POST", "GET"])
def forgot_password():
    """
    Forgot password controller. 

        * POST handles forgotten password request by sending an email. 
        * GET serves forgot password page.
    """
    if flask.request.method == "POST":
        email = flask.request.form["email"].strip()
        
        luser = models.Luser.query.filter_by(email=email).first()

        # It's less secure to let our users query who is and is not
        # a user, by abusing the password recovery feature. However,
        # it's also more user friendly, because, someone might forget
        # which email they used to sign up, and this message will 
        # help them. Lets err on the side of user friendly.
        if luser is None:
#            flash("No account exists for: %s" % email)
            return flask.render_template("forgot.html", email_error="Email not found.")
      
        request = models.ForgottenPasswordRequest(luser._id)
        models.db.session.add(request)
        models.db.session.commit()
 
        link = BASE_URL + "reset/%s" % request.uuid

        email_notify.forgot_password(email, link)

        flask.flash("A password recovery email has been sent to: %s" % email)
        return redirect_to_index()
    else:
        return flask.render_template("forgot.html")


###############################################################################
# Login
###############################################################################

@app.route("/login", methods=["POST", "GET"])
def login():

    if flask.request.method == "POST":
        # obtain form parameters
        email = flask.request.form["email"]
        password = flask.request.form["password"]
        
        return perform_login(email, password)
    else:
        return flask.render_template("login.html")


###############################################################################
# Google oAuth2 (does automatic signup when account is unknown, login
# otherwise) 
###############################################################################

@app.route("/oauth2login")
def oauth2login():
    # We'll need their profile and email.
    auth_scopes = ["https://www.googleapis.com/auth/userinfo.profile",
                   "https://www.googleapis.com/auth/userinfo.email"]

    flow = flow_from_clientsecrets("client_secrets.json", auth_scopes,
        redirect_uri=BASE_URL + "oauth2callback")

    # Save a reference to the flow, since we need it when the user
    # is returned.
    flask.session["flow"] = flow 

    # Begin the oauth authorization process.
    auth_uri = flow.step1_get_authorize_url()
    return flask.redirect(auth_uri)


@app.route("/oauth2callback")
def oauth2callback():
    # The authorization code will be passed to the callback uri.
    auth_code = flask.request.args["code"]

    # get the stored flow.
    flow = flask.session["flow"]

    # Exchange the code for credentials
    credentials = flow.step2_exchange(auth_code)

    # Authorize an httplib2 instance to get user's data
    http = httplib2.Http()
    http = credentials.authorize(http)

    # request from the userinfo api:
    resp, content = http.request("https://www.googleapis.com/oauth2/v1/userinfo?alt=json")
    
    userinfo = json.loads(content)

    return login_via_google(userinfo)


###############################################################################
## Signup
###############################################################################

@app.route("/signup", methods=["POST", "GET"])
def signup():
    """
    Signup controller. Delegates POST to perform_signup handler,
    serves signup page on GET.
    """
    template = "sign-up.html"    

    if flask.request.method == "POST":
        # Obtain references to form parameters 
        email = flask.request.form["email"].strip()
        password = flask.request.form["password"]
        confirm = flask.request.form["confirm"]
       
        return perform_signup(email, password, confirm)
    else:
        return flask.render_template("sign-up.html") 




def perform_signup(email, password, confirm):
    """
    Handles a signup request. 
    
    Basic checks on password and confirm fields. Creates user account and
    stores salted password hash.
    """
    template = "sign-up.html"

    # Ensure that no log-in already exists for this email.
    existing = models.Luser.query.filter_by(email=email).first()
    if existing is not None:
        return flask.render_template(template,
                    email_error="Email already registered.") 
 
    # Ensure that the user is on our beta list and is activated.
    is_activated = (models.BetaSignup.query
                    .filter_by(email=email, is_activated=True).first())

    if is_activated is None:   
        flask.flash("Please sign up for the beta and we'll ping you when it's"
                    " ready.")
        return redirect_to_index()


    # Ensure that password is not absolutely stupid
    if len(password) < 8:
        return flask.render_template(template, 
            password_error="Password must be at least 8 characters")
    
    
    # Ensure that the password and confirm values match
    if password != confirm:
        return flask.render_template(template, 
            password_error="Passwords do not match.")
   
    
    # So far, so good. Create a user.
    pw_hash = bcrypt.hashpw(password, bcrypt.gensalt())
    luser = models.Luser(email=email, pw_hash=pw_hash)
    models.db.session.add(luser)
    models.db.session.flush()

    # Create all dependent data (this includes the user's sample project)
    create_luser_data(luser)

    # Welcome the user via email:
    email_notify.send_welcome_email(luser)

    # If signup was successful, just log the user in.
    return perform_login(email, password)


def create_sample_project_for_luser(luser):
    """
    Creates a simple sample project for a user.
    """

    sample = models.Project(name="Sample")
    models.db.session.add(sample)
    models.db.session.flush()

    # default the creator of a project into updates as well as admin
    assoc = models.ProjectLuser(luser_id=luser._id, project_id=sample._id,
                                is_owner=True, is_interested=True)

    models.db.session.add(assoc)
    models.db.session.flush()

    todo = models.Pile(project_id=sample._id, name="To-Do")
    doing = models.Pile(project_id=sample._id, name="Doing")
    done = models.Pile(project_id=sample._id, name="Done")

    models.db.session.add(todo)
    models.db.session.add(doing)
    models.db.session.add(done)
    models.db.session.flush()

    card1 = models.Card(project_id=sample._id, text="Check out the app!",
                        pile_id=todo._id, score=1)

    card2 = models.Card(project_id=sample._id, text="Make some cards...",
                        pile_id=todo._id, score=1)

    card3 = models.Card(project_id=sample._id, text="Have fun!", 
                        pile_id=todo._id, score=0)

    models.db.session.add(card1)
    models.db.session.add(card2)
    models.db.session.add(card3)
    
    models.db.session.commit()


def create_luser_data(luser, first_name="Unknown", last_name="Unknown"):
    """
    Creates any data that must exist for each user after signup.

    Includes:
        * Profile
        * Associations to projects with pending invites for user.
        * Sample project.
    """
    email = luser.email

    # Must also create a profile for that user. Default the username
    # to the name part of the email.
    profile = models.LuserProfile(luser_id=luser._id, first_name=first_name,
                                  last_name=last_name, username=email.split("@")[0])

    models.db.session.add(profile)


    # Must also add the user to any projects he has been invited to:
    invites = models.ProjectInvite.query.filter_by(email=email).all()
    for invite in invites:
        membership = models.ProjectLuser(project_id=invite.project_id,
                            luser_id=luser._id)
        models.db.session.add(membership)
        invite.is_pending = False

    # every user should start out with a sample project
    create_sample_project_for_luser(luser)

    # Keep these changes.
    models.db.session.commit()


###############################################################################
## Beta Signup
###############################################################################

@app.route("/beta-signup", methods=["POST", "GET"])
def beta_signup():
    if flask.request.method == "GET":
        # Render the beta signup form.
        return flask.render_template("beta-signup.html")

    elif flask.request.method == "POST":
        # Receive the POST from the signup form.
        
        # Create a beta signup row for this prospective tester..
        email = flask.request.form["email"]
        beta_signup = models.BetaSignup(email=email)
        models.db.session.add(beta_signup)
        models.db.session.commit()

        # Show the user a message on the same page.
        flask.flash("Thanks! We'll ping you when it's ready.")
        # TODO: redirect to blog instead after DNS is changed.
        return redirect_to("index")

    else:
        # Bad request.
        flask.abort(400)


##############################################################################


if __name__ == '__main__':
    port = int(os.environ.get('PORT', PORT))
    app.run(host='0.0.0.0', port=port)
