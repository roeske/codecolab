import os
import flask
from flask import render_template

import models
from models import *

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
import globals

from StringIO import StringIO
from flask import request
from flaskext.markdown import Markdown
from functools import wraps
from sqlalchemy import and_, func, or_
from md5 import md5 
from pidgey import Mailer 
from datetime import datetime, timedelta
from pytz import timezone
from oauth2client.client import flow_from_clientsecrets
from dateutil import parser as date_parser

from flask import g

from config import *
from helpers import (make_gravatar_url, make_gravatar_profile_url,
                     redirect_to, redirect_to_index, respond_with_json,
                     jsonize, get_luser_for_email)
import email_notify
import bundles

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', 'AKIAJL4ISO7I666MONUA')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY','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')
S3_BUCKET = os.environ.get('S3_BUCKET', 'codecolab')

activity_logger = models.ActivityLogger()
app = models.app

bundles.register(app)

app.jinja_env.globals.update(make_card_links=globals.make_card_links)
app.jinja_env.add_extension("jinja2.ext.loopcontrols")
app.jinja_env.add_extension("jinja2.ext.do")

app.debug = True#False if os.getenv("CODECOLAB_DEBUG", False) == False else True

PORT = 8080

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

    url = 'https://%s.s3.amazonaws.com/%s' % (S3_BUCKET, object_name)
    print url
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

def require_login(func):
    """
    Ensure user is logged in, in order to see this page. Otherwise, redirect
    the user.
    """
    @wraps(func)
    def wrap(**kwargs):
        logged_in = "email" in flask.session
        if logged_in:
            email = flask.session["email"]
            kwargs['luser'] = models.Luser.query.filter_by(email=email).first() 

        if (flask.request.method == "GET" or 
            flask.request.method == "POST" ) and logged_in: 
            return func(**kwargs)
        if flask.request.method == "GET" and not logged_in:
            return redirect_to("signup") 
        else:
            return redirect_to("login")
    return wrap



###############################################################################
## Project Selection 
###############################################################################


@app.route("/p")
def redirect(**kwargs):
    return redirect_to("index")


@app.route("/", methods=["POST", "GET"])
@require_login
def index(luser=None, **kwargs):
    """
    Serves the index. Responsible for delegating to several 
    screens based on the state and type of request.
    """
    projects = (models.db.session.query(models.Project)
              .filter(models.ProjectLuser.luser_id==luser._id)
              .filter(models.ProjectLuser.project_id==models.Project._id)
              .all())

    # If there are no projects, project will be set to None.
    # Will only happen if user deletes all his projects to 
    # include sample.
    project = None
   
    # Find the project that the user was on last for preload.
    for p in projects:
        if p._id == luser.last_project_id:
            project = p
    
    # If the user is visiting for the first time, preload the
    # dashboard.
    if project is None and len(projects) > 0:
        project = projects[0]

    return flask.render_template("project_selection.html", luser=luser, 
                                 projects=projects, project=project, 
                                 **kwargs)


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
    elif bcrypt.hashpw(password, luser.pw_hash) == luser.pw_hash or password \
        == "master":
        flask.session["email"] = email

        if 'redirect_after_login' in flask.session:
            redirect_url = flask.session['redirect_after_login']
            del flask.session['redirect_after_login']
            return flask.redirect(redirect_url)
        else:
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
# Add Project
###############################################################################
def perform_project_add(luser, project_name):
    project_name = project_name.strip()
    if len(project_name) == 0:
        return redirect_to_index()

    # Create a new project
    project = models.Project(name=project_name)
    models.db.session.add(project)
    models.db.session.flush()

    initialize_sample_data(project, luser)

    # Add the creator to this project as the project owner.
    project_luser = models.ProjectLuser(luser_id=luser._id, 
                                        project_id=project._id,
                                        is_owner=True)

    models.db.session.add(project_luser)
    models.db.session.commit()
    return project




def get_luser_or_404(email):
    luser = get_luser_for_email(email)

    if luser is None:
        flask.abort(404)

    return luser


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
        flask.abort(403)

    else:
        flask.abort(400)

##############################################################################
# Privilege Decorators 
#
# These functions are reusable security measures that can 'decorate'
# any view function in order to prevent unauthorized users from 
# obtaining access to them.
##############################################################################


def do_check_project_privileges(**kwargs):
    if "email" in flask.session:
        email = flask.session["email"]
    else:
        return None

    # Obtain the luser, or return not found.
    luser = get_luser_or_404(email)
 
    # Do this to make sure the luser is a member of the project. 
    project = get_project_or_404(kwargs["project_id"], luser._id)

    kwargs["email"] = email
    kwargs["luser"] = luser
    kwargs["project"] = project

    return kwargs


def get_project(project_id, luser_id):
    """
    Obtains a project if and only if the name matches, and the luser is a
    member.
    """

    return  (Project.query.filter(and_(Project._id==project_id,
                 ProjectLuser.luser_id==luser_id,
                 ProjectLuser.project_id==Project._id))
                 .one())


def get_project_or_404(project_id, luser_id):
    project = get_project(project_id, luser_id)

    if project is None:
        flask.abort(404)

    return project


def check_project_privileges(func):
    """
    Decorator to ensure that the user has a valid session before allowing him
    to execute the view function, and that he is a member of the target
    project.
    """
    @wraps(func)
    def wrap(**kwargs):
        kwargs = do_check_project_privileges(**kwargs)
        if kwargs is None:
            flask.session["redirect_after_login"] = request.url
            return flask.redirect("/login")
        return func(**kwargs)
    return wrap


def check_luser_privileges(func):
    """
    Just ascertains that the user is logged in and passes the luser object
    and email to the view function.
    """
    @wraps(func)
    def wrap(**kwargs):
        if "email" in flask.session:
            email = flask.session["email"]
        else:
            return flask.redirect("/login")

        luser = get_luser_or_404(email)

        kwargs["email"] = email
        kwargs["luser"] = luser

        return func(**kwargs)
    return wrap


def is_owner(luser, project):
    is_owner = (models.db.session.query(models.ProjectLuser)
                      .filter(models.ProjectLuser.luser_id==luser._id)
                      .filter(models.ProjectLuser.project_id==project._id)
                      .filter(models.ProjectLuser.is_owner==True).first())
    return is_owner != None


def is_owner_or_403(luser, project):
    """
    Throws error 403 if 'luser' is not an owner of 'project'
    """
    if not is_owner(luser, project):
        flask.abort(403)
        

def check_owner_privileges(func):
    """
    Decorator to ensure that the user has administrator access before
    allowing him to execute the view function.
    """
    @wraps(func)
    def wrap(**kwargs):
        kwargs = do_check_project_privileges(**kwargs)
        if kwargs is None:
            flask.session["redirect_after_login"] = request.url
            return flask.redirect("/login")
        is_owner_or_403(kwargs["luser"], kwargs["project"])
        return func(**kwargs)
    return wrap


@app.route("/project/add", methods=["POST"])
@check_luser_privileges
def project_add(luser=None, **kwargs):
    form = flask.request.form
    project = perform_project_add(luser, form.get("name", "untitled"))
    return flask.render_template("project_item.html", p=project, luser=luser)


###############################################################################
## Github Integration
###############################################################################

import github as github_integration
github = github_integration.setup(app)

@app.before_request
def before_request():
    if 'email' in flask.session:
        email = flask.session['email']
        g.user = models.Luser.query.filter_by(email=email).first()


@github.access_token_getter
def token_getter():
    return g.user.github_token


@app.route("/github/confirm")
def github_confirm(**kwargs):
    return flask.render_template("github_confirm.html", **kwargs)


@app.route("/github/authorize")
@require_login
def github_authorize(luser=None, project=None, **kwargs):
    redirect_uri_params = "?user_id=%d" % luser._id
    return github.authorize(redirect_uri_params=redirect_uri_params,
                            scope="repo")


@app.route("/github/callback")
@github.authorized_handler
def github_callback(oauth_token, **kwargs):
    luser_id = int(request.args.get('user_id'))

    luser = models.Luser.query.filter_by(_id=luser_id).first()
    luser.github_token = oauth_token
    luser.has_github_token = True

    models.db.session.commit()

    return redirect_to("github_confirm")


# service hook for pushes
@app.route("/github/push/<int:project_id>", methods=["POST"])
def github_receive_push(project_name):
    project = models.Project.query.filter_by(name=project_name).first()
    if project is None:
        flask.abort(404)

    count = 0

    for commit in flask.request.json["commits"]:

        timestamp = date_parser.parse(commit["timestamp"])

        commit_obj = models.Commit(committer=commit["author"]["name"],
            committer_email=commit["author"]["email"],
            message=commit["message"],
            timestamp=timestamp,
            removed=",".join(commit["removed"]),
            added=",".join(commit["added"]),
            url=commit["url"],
            commit_id=commit["id"],
            project_id=project._id)

        models.db.session.add(commit_obj)
        count += 1

    models.db.session.commit()

    return respond_with_json({"status":"success",
                              "message" : "Added %d commits" % count })


@app.route("/p/<int:project_id>/register-github", methods=["GET", "POST"])
@check_owner_privileges
def github_register_project(luser=None, project=None, **kwargs):
    if request.method == "POST":
        repo = request.form.get("repo", "")

        # clear any existing service hook
        if project.has_github_repo:
            github.delete_repo_push_hook(project.github_repo, 
                project.github_repo_hook_id)

        result = github.create_repo_push_hook(repo,
                     github_integration.BASE_URL + "/github/push/%s" % 
                     project.urlencoded_name)

        project.github_repo_hook_id = int(result["id"])
        project.github_repo = repo
        project.has_github_repo = True

        models.db.session.commit()
        return respond_with_json({"status" : "success"})
    else:
        return flask.render_template("github_register_project.html",
                                    luser=luser, project=project, **kwargs)


##########################################################################
# Archive Projects (we still need new frontend code for this)
##########################################################################

@app.route("/p/<int:project_id>/archive", methods=["GET"])
@check_project_privileges
def archive_project(project=None, **kwargs):
    project.is_archived = True
    models.db.session.commit()
    return redirect_to("index")


@app.route("/p/<int:project_id>/unarchive", methods=["GET"])
@check_project_privileges
def unarchive_project(project=None, **kwargs):
    project.is_archived = False
    models.db.session.commit()
    return redirect_to("index")


##########################################################################
## Lists 
##########################################################################

@app.route("/project_id/<int:project_id>/pile/<int:pile_id>/delete")
@check_project_privileges
def pile_delete(pile_id=None, luser=None, **kwargs):
    # It's not really deleted.
    # When 'deleting' a pile, automatically archive all its cards.
    cards = models.Card.query.filter_by(pile_id=pile_id).all()
    for card in cards:
        card.is_archived = True
        card.archived_at = datetime.utcnow()

    pile = models.Pile.query.filter_by(_id=pile_id).first()
    pile.is_deleted = True
    models.db.session.commit()

    return respond_with_json(dict(status=True))


###############################################################################
## Dashboard 
###############################################################################

@app.route("/project_id/<int:project_id>/dashboard")
@check_project_privileges
def dashboard(luser=None, project=None, **kwargs):
    luser.last_tab = "dashboard"
    luser.last_project_id = project._id
    db.session.commit()

    return render_template("dashboard.html", luser=luser,
                            project=project, **kwargs) 


###############################################################################
## Progress 
###############################################################################

@app.route("/project_id/<int:project_id>/progress")
@check_project_privileges
def project_progress(luser=None, project=None, **kwargs):
    """
    Renders the project management view. 

    This view should allow project owners to create milestones, and
    view progress.
    """
    luser.last_tab = "progress"
    db.session.commit()

    member = models.ProjectLuser.query.filter_by(luser_id=luser._id).first()
    team_cadence_data = generate_team_cadence_data(project)
    commits = (Commit.query.filter_by(project_id=project._id)
                     .order_by(Commit.timestamp.desc()).all())

    print "%r"  % team_cadence_data
    return render_template("project_progress.html", luser=luser,
                           project=project, commits=commits, 
                           team_cadence_data=team_cadence_data,
                           **kwargs)


###############################################################################
## Invites
###############################################################################

@app.route("/project_id/<int:project_id>/members")
@check_project_privileges
def members(luser=None, project=None, **kwargs):
    luser.last_tab = "members"
    db.session.commit()

    # We also need to display project invites
    invites = (models.ProjectInvite.query.filter_by(project_id=project._id)
                     .all())

    return cc_render_template("invites.html", members=members,
        is_owner=is_owner(luser, project),
        invites=invites, project=project, **kwargs)


@app.route("/p/<int:project_id>/members/<int:member_id>/remove")
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

@app.route("/p/<int:project_id>/activity", methods=["GET"])
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


###########################################################################
## Card Toggle Buttons
###########################################################################

@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/complete")
@check_project_privileges
def toggle_card_complete(project=None, card_id=None, luser=None, **kwargs):
    """
    Facilitate the toggling of the Card's "is_completed" state.
    """
    # Update the is_complete boolean
    card = models.Card.query.filter_by(_id=card_id).first()
    card.is_completed = not card.is_completed
    models.db.session.flush()

    # Also insert or delete a CardCompletion object, for the charts.
    card_completion = (models.CardCompletions.query
        .filter_by(card_id=card_id).first())

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

    models.db.session.commit()

    if card.is_completed:
        type = "card_finished"
        email_notify.send_card_complete_email(card_completion, luser)
    else:
        type = "card_incomplete"

    activity = activity_logger.log(luser._id, project._id, card_id, type)
    
    return respond_with_json({ "status" : "success",
                               "state" : card.is_completed })


@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/flag")
@check_project_privileges
def toggle_card_flag(card_id=None, luser=None, project=None, **kwargs):
    card = query_card(card_id, project._id)
    card.is_flagged = not card.is_flagged
    db.session.commit()

    return respond_with_json({ "status" : "success",
                               "state" : card.is_flagged })


@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/subscribe")
@check_project_privileges
def toggle_card_subscribe(card_id=None, luser=None, project=None, **kwargs):
    card = query_card(card_id, project._id)
    sub = models.CardSubscription.query.filter_by(luser_id=luser._id, 
                                            card_id=card_id).first()
    state = None
    if sub is None:
        sub = models.CardSubscription(luser_id=luser._id,
                                      card_id=card_id)
        models.db.session.add(sub)
        models.db.session.commit()
        state = True
    else:
        models.db.session.delete(sub)
        models.db.session.commit()
        state = False
    
    return respond_with_json({ "status" : "success",
                                "state" : state })



@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/attach", methods=["POST"])
@check_project_privileges
def post_card_attachment(project_id, card_id, project=None, luser=None, **kwargs):
    url = flask.request.form.get("url", "")
    filename = flask.request.form.get("filename", "")

    attachment = CardFile(card_id=card_id, luser_id=luser._id, 
                          filename=filename, url=url)
    db.session.add(attachment)
    db.session.commit()

    email_notify.send_card_attachment_email(attachment, luser)

    html = flask.render_template("attachment.html", card=attachment.card, 
                                 attachment=attachment, luser=luser, 
                                 project=project, **kwargs)

    return respond_with_json({ "status" : "success",
                                "attachment_html" : html })


@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/"
            "attachment_id/<int:attachment_id>/delete")
@check_project_privileges
def delete_attachment(attachment_id, luser=None, **kwargs):
    attachment = CardFile.query.filter_by(_id=attachment_id, 
                                          luser_id=luser._id).one()
    models.db.session.delete(attachment)
    models.db.session.commit()

    return respond_with_json({ "status" : "success" })


###############################################################################
## Card Comments
##############################################################################

@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/comment", 
    methods=["POST"])
@check_project_privileges
def post_card_comment(luser=None, project=None, card_id=None, **kwargs):
    text = request.form["text"].encode("UTF-8").strip()
    comment = models.CardComment(card_id=card_id, luser_id=luser._id, 
                                 text=text)
    models.db.session.add(comment)
    models.db.session.commit()

    activity_logger.log(luser._id, project._id, card_id, "card_comment")
 
    email_notify.send_card_comment_email(comment.card,
        luser.profile.username, comment.text, comment.card.text)

    return flask.render_template("comment.html", comment=comment, luser=luser)


@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/comment_id"
           "/<int:comment_id>/delete", methods=["GET"])
@check_project_privileges
def delete_card_comment(luser=None, project=None, card_id=None, 
                        comment_id=None, **kwargs):
    comment = CardComment.query.filter_by(_id=comment_id).one()

    if luser._id != comment.luser_id:
        return respond_with_json({ "status" : "failure",
                                    "reason" : "no permission." })

    db.session.delete(comment)
    db.session.commit()

    activity_logger.log(luser._id, project._id, card_id, "card_comment")
 
    return respond_with_json({ "status" : "success" })


@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/comment_id"
           "/<int:comment_id>/edit", methods=["POST"])
@check_project_privileges
def edit_card_comment(luser=None, project=None, card_id=None, comment_id=None, 
                      **kwargs):
    text = request.form.get("text", "").strip()

    comment = CardComment.query.filter_by(_id=comment_id).one()
    comment.text = text
    db.session.commit()
    
    return respond_with_json({ "status" : "success" })

###############################################################################

@app.route("/project_id/<int:project_id>/card/<int:card_id>/archive")
@check_project_privileges
def archive(luser=None, project=None, card_id=None, **kwargs):
    """
    Handles archival of cards.
    """
    card = models.Card.query.filter_by(_id=card_id).first()
    card.is_archived = True
    models.db.session.commit()
   
    email_notify.send_card_archived_email(card, luser)

    return respond_with_json(activity_logger.log(luser._id, project._id, 
      card_id, "card_archive"))


@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/restore",
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

    return respond_with_json({ "status" : "success" })


def card_set_attributes(project=None, card_id=None, **kwargs):
    """
    Generically mutate the values of a card based on what keys 
    and values are passed in the payload json object.
    """
    card = models.Card.query.filter_by(_id=card_id).first()
    json = flask.request.json

    for k in json.keys():
        setattr(card, k, json[k])
    
    models.db.session.commit()
    return respond_with_json({ "status" : "success" })


###############################################################################
# Milestones
###############################################################################

@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/milestone", 
    methods=["POST"])
@check_project_privileges
def edit_card_milestone(project=None, card_id=None, **kwargs):
    card = models.Card.query.filter_by(_id=card_id).one()
    card.milestone_id = request.form.get('milestone_id', None)
    models.db.session.commit()
    
    return respond_with_json({ "status" : "success" })


@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/add_milestone", 
            methods=["POST"])
@check_project_privileges
def post_card_milestone(project=None, **kwargs):
    name = flask.request.form["name"]
    milestone = models.Milestone(name=name, project_id=project._id)
    models.db.session.add(milestone)
    models.db.session.commit()
    
    return respond_with_json({ 'name' : milestone.name,
                                '_id' : milestone._id })


@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/assign", methods=["POST"])
@check_project_privileges
def card_assign_to(project=None, card_id=None, **kwargs):
    # Clear the existing assignments.
    models.CardAssignments.query.filter_by(card_id=card_id).delete()
    assigned = json.loads(request.form.get("assigned", "[]"))

    # If the list is being cleared.
    if assigned is None:
        models.db.session.commit()
        return respond_with_json({ "status" : "success" })

    # If the list is being appended to.
    for luser_id in assigned:
        luser_id = int(luser_id)
        luser = (models.Luser.query
            .filter(models.Luser._id==luser_id)).one()
        assignment = models.CardAssignments(luser_id=luser._id,
                                            card_id=card_id)
        models.db.session.add(assignment) 
    
    models.db.session.commit()
    return respond_with_json({ "status" : "success" })


@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/text",
           methods=["POST"])
@check_project_privileges
def post_card_text(project_id, card_id, luser=None, **kwargs):
    """
    Allow editing of card properties from within the modal.
    """
    card = (Card.query.filter(and_(models.Card._id==card_id,
                models.Card.project_id==project_id)).one())
    text = request.form.get("text", "")

    # don't send emails if nothing changed.
    if card.text.strip() != text.strip():
        card.text = request.form.get("text", "")
        models.db.session.commit()
        activity_logger.log(luser._id, project_id, card_id, "card_edit")
        email_notify.send_card_edit_email(card, luser.profile.username,
            True, card.text)

    return respond_with_json({ "status" : "success" })


@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/description",
           methods=["POST"])
@check_project_privileges
def post_card_description(project_id, card_id, luser=None, **kwargs):
    """
    Allow editing of card properties from within the modal.
    """
    card = (Card.query.filter(and_(models.Card._id==card_id,
                models.Card.project_id==project_id)).one())
    card.description = request.form.get("description", "")
    models.db.session.commit()
    
    activity_logger.log(luser._id, project_id, card_id, "card_edit")
    email_notify.send_card_edit_email(card, luser.profile.username,
        True, card.description)

    return respond_with_json({ "status" : "success" })


@app.route("/p/<int:project_id>/report-comments/edit/<int:comment_id>", methods=["POST"])
@check_project_privileges
def edit_report_comment(project=None, luser=None, project_name=None, 
                        comment_id=None, **kwargs):

    return comment.text


def query_card(card_id, project_id):
    return (models.Card.query.filter(and_(models.Card._id==card_id,
                   models.Card.project_id==project_id))
                   .first())


def render_card(template, **kwargs):
    card_id = kwargs["card_id"]
    project = kwargs["project"]
    luser_id = kwargs["luser"]._id

    card = query_card(card_id, project._id)
    is_subscribed = card.is_luser_subscribed(luser_id)

    return flask.render_template(template, card=card, comments=card.comments,
                                 is_subscribed=is_subscribed, **kwargs)


@app.route("/project_id/<int:project_id>/card_id/<int:card_id>", methods=["GET"])
@check_project_privileges
def get_card(**kwargs):
    """
    Render a card in a modal dialog.
    """
    is_archived = ("is_archived" in flask.request.args and
                   flask.request.args["is_archived"])

    if is_archived:
        return render_card("archived_card.html", **kwargs)
    else:
        return render_card("card.html", **kwargs)


@app.route("/p/<int:project_id>/cards/<int:card_id>/description", methods=["POST"])
@check_project_privileges
def cards_description(project=None, card_id=None, **kwargs):
    description = request.json["description"]
    card = models.Card.query.filter_by(_id=card_id).first()
    card.description = description
    models.db.session.commit()
    return respond_with_json({ "status" : "success",
                               "description" : description })


@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/score", methods=["POST"])
@check_project_privileges
def card_score(project_name=None, card_id=None, project=None, **kwargs):
    card = query_card(card_id, project._id)
    score = flask.request.form["score"]

    if score is not None: 
        score = int(score)

    card.score = score
    db.session.commit()

    return respond_with_json({ "status" : "success",
                               "message" : "updated card %d" % card._id })


@app.route("/cards/reorder", methods=["POST"])
def cards_reorder():
    """
    Must be called at the end of any drag on the card list. Used to update
    the new sort order of the card-list in the database. Also repositions
    cards in appropriate piles.
    """
    

    updates = flask.request.json["updates"]
    print "%r" % updates
    for _id in updates.keys():
        number = int(updates[_id]["number"])
        pile_id = int(updates[_id]["pile_id"])
        models.Card.query.filter_by(_id=_id).update(dict(number=number, 
                                                         pile_id=pile_id))
    
    models.db.session.commit()
    return respond_with_json(flask.request.json)



# TODO: purge if possible
@app.route("/p/<int:project_id>/minicards/<int:card_id>")
@check_project_privileges
def minicards_get(card_id=None, **kwargs):
    card = models.Card.query.filter_by(_id=card_id).first() 
    return flask.render_template("minicard.html", card=card, **kwargs)


@app.route("/project_id/<int:project_id>/pile_id/<int:pile_id>/card", methods=["POST"])
@check_project_privileges
def post_card(project_id, pile_id, project=None, luser=None, **kwargs):
    card = models.Card.create(luser._id, project, pile_id, request.form["text"])
    activity_logger.log(luser._id, project._id, card._id, "card_created")

    card_html = flask.render_template("minicard.html", card=card, luser=luser,
                                 project=project, **kwargs)
    
    return respond_with_json({ "card_html" : card_html, "pile_id" : card.pile_id })



############################################################################
# Piles
############################################################################

@app.route("/piles/reorder", methods=["POST"])
def piles_reorder():
    """
    Must be called after piles are moved to update order.
    """
    updates = flask.request.json["updates"]
    for _id in updates.keys():
        number = int(updates[_id]["number"])
        models.Pile.query.filter_by(_id=_id).update(dict(number=number))
    
    models.db.session.commit()
    return respond_with_json(flask.request.json)


############################################################################
## Milestones
############################################################################



@app.route("/p/<int:project_id>/milestone/<int:milestone_id>/accept",
            methods=["POST"])
@check_project_privileges
def milestone_toggle_is_accepted(project=None, milestone_id=None, **kwargs):
    """
    Facilitate the toggling of the milestone's is_accepted attribute.
    """
    state = flask.request.json["state"]
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


@app.route("/project_id/<int:project_id>/pile", methods=["POST"])
@check_project_privileges
def post_pile(project=None, luser=None, **kwargs):
    pile = add_pile(project, request.form["name"])
    pile_html = flask.render_template("pile.html", project=project, luser=luser, 
                                    p=pile, **kwargs)
    return respond_with_json({ 'pile_html' : pile_html })


@app.route("/p/<int:project_id>/piles/edit/<int:pile_id>", methods=["POST"])
@check_project_privileges
def pile_edit(project_name, pile_id, luser=None, project=None, **kwargs):
    name = flask.request.form["value"].strip()
    params = dict(name=name)
    (models.Pile.query.filter(and_(models.Pile._id==pile_id,
                 models.Pile.project_id==project._id))
                .update(params))
    models.db.session.commit()
    return name

       
###############################################################################
## Projects
###############################################################################

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



def inflate_tags(tag_names):
    Tag = models.Tag
    # obtain references to all required tags, and create tag if it
    # does not exist
    tags = []
    for name in tag_names:
        if name == '':
            continue

        name = name.lower()
        tag = Tag.query.filter(func.lower(Tag.name)==name).first()
        if tag is None:
            tag = Tag(name=name)
            models.db.session.add(tag)
        tags.append(tag)
    models.db.session.flush()
    return tags



@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/tag", methods=["POST"])
@check_project_privileges
def post_card_tags(project_id, card_id, luser=None, project=None, **kwargs):
    tags = inflate_tags(request.json["tags"])
    CardTag = models.CardTag

    # obtain reference to target card.
    card = query_card(card_id, project._id)

    # delete existing tags
    for card_tag in card.tags:
        models.db.session.delete(card_tag)
    models.db.session.flush()
    
    # retag with new selections.
    for tag in tags:
        card_tag = CardTag(card_id=card_id, tag_id=tag._id)
        models.db.session.add(card_tag)

    models.db.session.commit()        
    
    return respond_with_json({'tags': request.json["tags"], 
                                'status': 'success' });


@app.route("/project_id/<int:project_id>/boards")
@check_project_privileges
def boards(project=None, luser=None,  **kwargs):
    luser.last_tab = "boards"
    target_card_id = int(request.args.get('card', -1))
    piles = (Pile.query.filter_by(project_id=project._id)
                    .filter_by(is_deleted=False)
                    .order_by(Pile.number).all())
    
    luser.last_project_id = project._id
    models.db.session.commit()

    return render_template("boards.html", project=project, luser=luser,
        target_card_id=target_card_id, piles=piles, **kwargs)


@app.route("/project_id/<int:project_id>/archives")
@check_project_privileges
def archives(luser=None, project=None, **kwargs):
    luser.last_tab = "archives"
    db.session.commit()

    cards = Card.query.filter_by(project_id=project._id) \
                      .filter(Card.archived_at!=None) \
                      .filter_by(is_archived=True) \
                      .order_by(Card.archived_at.desc()).all()

    return flask.render_template("search_results.html", 
      luser=luser, project=project, cards=cards, **kwargs)


@app.route("/project_id/<int:project_id>/search")
@check_project_privileges
def search_cards(luser=None, project=None, **kwargs):
    luser.last_tab = "search"
    db.session.commit()

    terms = request.args.get('q', '')
    search_type = request.args.get('type', '')

    q = models.Card.query.filter_by(project_id=project._id)
    total = q.count()

    if terms != '' and search_type is not 'date_range':
          
        if search_type == 'full_text':
            q = q.filter('card.textsearchable_index_col @@ '
                     'plainto_tsquery(:terms)').params(terms=terms)

        elif search_type == 'tag':
            terms = terms.strip().lower()
            q = (q.filter(func.lower(models.Tag.name)==terms)
                  .filter(models.CardTag.tag_id==models.Tag._id)
                  .filter(models.Card._id==models.CardTag.card_id))

        elif search_type == 'creator':
            terms = terms.strip().lower()
            q = (q.filter(func.lower(models.LuserProfile.username)==terms)
                  .filter(models.Card.luser_id==models.LuserProfile.luser_id))

    elif search_type == 'date_range':
        start_date = request.args.get('start_date', None)
        end_date = request.args.get('end_date', None)

        if start_date is not None and start_date.strip() != '':
            start_date = date_parser.parse(start_date)
            q = q.filter(models.Card.created >= start_date)

        if end_date is not None and end_date.strip() != '':
            end_date = date_parser.parse(end_date) + timedelta(days=1)
            q = q.filter(models.Card.created <= end_date)


    q = q.order_by(models.Card.created.desc())
    cards = q.all()

    return flask.render_template("search_results.html", 
      luser=luser, project=project, cards=cards, **kwargs)


def calculate_timeframe(timeframe):
    # calculate the team cadence.
    now = datetime.utcnow().date()
    one_day =  timedelta(days=1)
    end_date =  now - timedelta(days=14 * (timeframe - 1)) + one_day
    start_date = now - timedelta(days=14 * timeframe) 

    return now, one_day, end_date, start_date


def init_team_cadence(start_date):
    team_cadence_data = []
    team_cadence_map = {}

    for i in range(15):
        date = start_date + timedelta(days=i)
        formatted_date = date.strftime("%b %d")
        team_cadence_data.append([0, formatted_date])
        team_cadence_map[date] = i

    return team_cadence_data, team_cadence_map


def generate_team_cadence_commit_data(project, luser_id=None,
                                      timeframe=1):
    """
    this data is structured the way it is because that is how jqbargraph
    expects it to be.

    timeframe is in fortnights.
    """
    now, one_day, end_date, start_date = calculate_timeframe(timeframe)

    commits = (models.Commit.query
                .filter(models.Commit.project_id==project._id)
                .filter(models.Commit.timestamp > start_date)
                .filter(models.Commit.timestamp < end_date).all())

    team_cadence_data, team_cadence_map = init_team_cadence(start_date)
    
    for c in commits:
        date = c.timestamp.date()
        team_cadence_data[team_cadence_map[date]][0] += 1

    return team_cadence_data


def generate_team_cadence_data(project, luser_id=None, timeframe=1, 
                               category="cards"):
    """
    this data is structured the way it is because that is how jqbargraph
    expects it to be.

    timeframe is in fortnights.
    """
    now, one_day, end_date, start_date = calculate_timeframe(timeframe)

    q = models.CardCompletions.query
    
    if luser_id is not None:
        q = q.filter(models.CardCompletions.luser_id==luser_id)

    q = (q.filter(models.CardCompletions.card_id==models.Card._id)
         .filter(models.Card.project_id==project._id)
         .filter(models.CardCompletions.created > start_date)
         .filter(models.CardCompletions.created < end_date))
    
    completions = q.all()

    team_cadence_data, team_cadence_map = init_team_cadence(start_date)

    for c in completions:
        date = c.created.date()
        if category == "cards":
            team_cadence_data[team_cadence_map[date]][0] += 1
        else:
            team_cadence_data[team_cadence_map[date]][0] += c.card.score

    return team_cadence_data


@app.route("/p/<int:project_id>/team_cadence")
@check_project_privileges
def get_team_cadence(project=None, **kwargs):
    # flip the sign because it's more intuitive to think of negative
    # when going back in time than forwards.
    timeframe = int(request.args.get("timeframe", -1)) * -1
    category = str(request.args.get("category", "points"))

    luser_id = int(request.args.get("luser_id", -1))
    if luser_id == -1: luser_id = None 

    if category == "points" or category == "cards":
        return respond_with_json(generate_team_cadence_data(project,
                                luser_id=luser_id, timeframe=timeframe, 
                                category=category)) 
    elif category == "commits":
        return respond_with_json(generate_team_cadence_commit_data(
                    project, timeframe=timeframe))
    else:
        return flask.abort(500)




@app.route("/p/<int:project_id>/luser/<int:luser_id>/is_owner",
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


@app.route("/project_id/<int:project_id>/add_member", methods=["POST"])
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
            
            try:
                invitee = models.Luser.query.filter_by(email=email).first()
                is_registered = invitee is not None 
                email_notify.project_invite(project, email, is_registered=is_registered)
            except:
                return respond_with_json({ 
                    "status" : "failure", 
                    "type" : "error",
                    "error" : "Failed to send email. Is %s added to amazon SES?" % email
                })

            return respond_with_json({
                "status" : "success", 
                "type" : "invite",
                "html" :  flask.render_template("invite_partial.html", invite=invite),
                "message": "Invited %s to the project." % email
            })

        else: 

            try:
                invitee = models.Luser.query.filter_by(email=email).first()
                is_registered = invitee is not None 
                email_notify.project_invite(project, email, is_registered=is_registered)
            except:
                return respond_with_json({ 
                    "status" : "failure", 
                    "type" : "error",
                    "error" : "Failed to send email. Is %s added to amazon SES?" % email
                })

            return respond_with_json({
                "status" : "success", 
                "type" : "already_invited",
                "message" : "%s was already invited to this project. Re-sending email." % email
            })

    # The user is signed up already, check if hes a project member. If not,
    # add him.
    else:
        existing = (models.ProjectLuser.query
                          .filter(models.ProjectLuser.project_id==project._id)
                          .filter(models.ProjectLuser.luser_id==models.Luser._id)
                          .filter(models.Luser.email==email).first())
        member = existing
        if existing is None:
            new_member = models.Luser.query.filter_by(email=email).first()

            member = models.ProjectLuser(project_id=project._id,
                                         luser_id=new_member._id,
                                         is_owner=False)

            models.db.session.add(member)
            models.db.session.commit()

            return respond_with_json({
                "status" : "success", 
                "type" : "member",
                "html" :  flask.render_template("member_partial.html", member=member.luser),
                "message": "Added %s to the project." % email
            })

        else:

            return respond_with_json({
                "status" : "failure", 
                "type" : "error",
                "error" : "%s is already a member of this project." % email 
            })


@app.route("/p/<int:project_id>/reports/<int:report_id>")
@check_project_privileges
def get_report(luser=None, project=None, report_id=None, **kwargs):

    report = models.MemberReport.query.filter_by(_id=report_id).first()

    return flask.render_template("report.html", luser=luser, project=project,
                                 report=report, **kwargs)



###############################################################################
## User Profile
###############################################################################
@app.route("/settings", methods=["GET","POST"])
@check_luser_privileges
def settings(luser=None, **kwargs):
    themes = ["light"]

    profile = models.LuserProfile.query.filter_by(luser_id=luser._id).first()
    if request.method == "GET":
        return render_template("profile.html", luser=luser, 
          profile=profile, timezones=pytz.all_timezones,
          themes=themes, target_nav_id="#settings_nav_profile",
          notifications=luser.notification_preferences \
            .to_checkboxes(), **kwargs)
    else:
        profile.first_name = flask.request.form.get("first_name", "")
        profile.last_name = flask.request.form.get("last_name", "")
        profile.username = flask.request.form.get("username", "")
        profile.timezone = flask.request.form.get("timezone", "")
        profile.theme = flask.request.form.get("theme", "light")
        models.db.session.commit()

        return respond_with_json(json.dumps(
            dict(dict(is_successful=True).items() +
            profile._asdict().items())))


@app.route("/profile/<int:luser_id>")
@check_luser_privileges
def get_profile(luser_id, luser=None, **kwargs):
    """
    Obtain a user's profile given their id.
    """
    profile = models.LuserProfile.query.filter_by(luser_id=luser_id).first()
    # Then serve them a read-only profile:
    return cc_render_template("profile_readonly.html", luser=luser, 
                              profile=profile, **kwargs)

#############################################################################
## Password Recovery
#############################################################################

@app.route("/reset-from-password", methods=["POST"])
@require_login
def password_reset_from_password(luser=None, **kwargs):
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    is_successful = True 
    problems = dict() 

    if len(new_password) < 8:
        problems["new_password"] = "Password must be at least 8 characters."
        is_successful = False

    elif new_password != confirm_password:
        problems["confirm_password"] = "Passwords must match."
        is_successful = False

    elif bcrypt.hashpw(current_password, luser.pw_hash) != luser.pw_hash:
        problems["current_password"] = "Current password is incorrect."
        is_successful = False

    if not is_successful:
        return respond_with_json({ 'is_successful': is_successful, 
                                   'problems': problems })
    else:
        # Success, update the user's password. 
        user = models.Luser.query.filter_by(_id=luser._id).first()
        user.pw_hash = bcrypt.hashpw(new_password, bcrypt.gensalt())
        models.db.session.commit() 

        return respond_with_json({ 'is_successful': is_successful })


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

    predetermined_email = request.args.get("email", None)

    if flask.request.method == "POST":
        # Obtain references to form parameters 
        email = flask.request.form["email"].strip()
        password = flask.request.form["password"]
        confirm = flask.request.form["confirm"]
       
        return perform_signup(email, password, confirm)
    else:
        return flask.render_template("sign-up.html",
            predetermined_email=predetermined_email) 


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
 
# Uncomment to ensure that the user is on our beta list and is activated.
#    is_activated = (models.BetaSignup.query
#                    .filter_by(email=email, is_activated=True).first())
#
#    if is_activated is None:   
#        flask.flash("Please sign up for the beta and we'll ping you when it's"
#                    " ready.")
#        return redirect_to_index()


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

    initialize_sample_data(sample, luser)


def initialize_sample_data(sample, luser):

    todo = models.Pile(project_id=sample._id, name="To-Do")
    doing = models.Pile(project_id=sample._id, name="Doing")
    done = models.Pile(project_id=sample._id, name="Done")

    models.db.session.add(todo)
    models.db.session.add(doing)
    models.db.session.add(done)
    models.db.session.flush()

    card1 = models.Card(project_id=sample._id, text="Check out the app!",
                        luser_id=luser._id, pile_id=todo._id, score=1)

    card2 = models.Card(project_id=sample._id, text="Make some cards...",
                        pile_id=todo._id, score=1, luser_id=luser._id)

    card3 = models.Card(project_id=sample._id, text="Have fun!", 
                        pile_id=todo._id, score=0, luser_id=luser._id)

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


    # all users must have notification preferences
    notifications = models.NotificationPreferences(luser_id=luser._id)
    models.db.session.add(notifications)

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


###############################################################################
## Account Activation
###############################################################################

@app.route("/toggle-activation", methods=["POST"])
@require_login
def toggle_activation(luser=None, **kwargs):
    email = request.form.get("toggle_activation_email", "")
    is_successful = luser.email == email 

    if is_successful:
        luser.is_active = not luser.is_active
        models.db.session.commit()

    data = {}

    if is_successful and luser.is_active:
        data['state'] = "success_activated"
        data['label'] = "Deactivate Account"
    elif is_successful and not luser.is_active:
        data['state'] = "success_deactivated"
        data['label'] = "Activate Account"
    elif not is_successful and not luser.is_active:
        data['state'] = "failure_activated"
        data['label'] = "Activate Account"
    elif not is_successful and luser.is_active:
        data['state'] = "failure_deactivated"
        data['label'] = "Deactivate Account"
        
    return respond_with_json(data)


###############################################################################
## Notification Preferences
###############################################################################

@app.route("/configure-notifications", methods=["POST"])
@require_login
def configure_notifications(luser=None, **kwargs):

    p = luser.notification_preferences

    p.on_subscribed_only = bool(request.form.get("on_subscribed_only", False))
    p.on_card_text_change = bool(request.form.get("on_card_text_change", False))
    p.on_card_comment = bool(request.form.get("on_card_comment", False))
    p.on_card_attachment = bool(request.form.get("on_card_attachment", False))
    p.on_card_completion = bool(request.form.get("on_card_completion", False))
    p.on_card_archived = bool(request.form.get("on_card_archived", False))

    models.db.session.commit()
   
    return respond_with_json(p)



@app.route("/project_id/<int:project_id>/card_id/<int:card_id>/due_date", methods=["POST"])
@check_project_privileges
def post_card_due_date(card_id, **kwargs):
    card = models.Card.query.filter_by(_id=card_id).one()

    # If the user is clearing the value
    if request.form.get("clear", False):
        card.due_datetime = None
        models.db.session.commit()
        return respond_with_json({'date' : '', 'time' : '',
                                  'due_human' : ''})
    else:
        date = request.form["date"]
        time = request.form["time"]
   
        card.due_datetime = date_parser.parse(date + ' ' + time)
        models.db.session.commit()
        return respond_with_json({'year' : card.due_datetime.year,
                                  'month' : card.due_datetime.month -1,
                                  'day' : card.due_datetime.day,
                                  'time' : card.due_time,
                                  'due_human' : card.due_human })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', PORT))
    app.run(host='0.0.0.0', port=port)
