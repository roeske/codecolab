import os
import flask
import models
import bcrypt 
import models
import pytz

import simplejson as json

from flaskext import uploads
from functools import wraps
from sqlalchemy import and_
from md5 import md5

from pidgey import Mailer
from config import MAILER_PARAMS, MAIL_FROM, BASE_URL 

from datetime import datetime

import httplib2
from oauth2client.client import flow_from_clientsecrets

app = models.app

PORT = 8080

files = uploads.UploadSet("files", uploads.ALL, default_dest=lambda app:"./uploads")

uploads.configure_uploads(app, (files,))

# JSONIZE!
def _handler(o):
    if hasattr(o, 'isoformat') and callable(o.isoformat):
        return o.isoformat()
    raise TypeError("Can't serialize %r" % (o,))

jsonize = lambda d: json.dumps(d, default=_handler)


def is_logged_in():
    return "email" in flask.session


# Serve static files for development
################################################

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


# Convenience Methods 
###############################################################################


def make_gravatar_url(email):
    email_hash = md5(email.strip().lower()).hexdigest()
    return "http://gravatar.com/avatar/%s" % email_hash

def make_gravatar_profile_url(email):
    email_hash = md5(email.strip().lower()).hexdigest()
    return "http://gravatar.com/%s" % email_hash


def redirect_to(page, **kwargs):
    url = flask.url_for(page, **kwargs)
    return flask.redirect(url)


def redirect_to_index():
    return redirect_to("index")


def get_luser_for_email(email):
    return models.Luser.query.filter_by(email=email).first()


def respond_with_json(obj):
    " Helper for returning a JSON response body."
    mimetype = "application/json;charset=UTF-8"
    return flask.Response(jsonize(obj), mimetype=mimetype)

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


## Log out
###############################################################################


@app.route("/logout")
def logout():
    flask.session.pop("email", None)
    return redirect_to_index()


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
    models.db.session.flush()

    create_luser_data(luser, first_name=userinfo["given_name"],
                             last_name=userinfo["family_name"])
    return luser


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


def perform_delete_pile(email, pile_id, project_name):
    """
    Deletes a pile by id. Performs basic security checks first.
    Does NOT delete associated cards. They remain orphaned in
    the database.
    """
    luser = get_luser_or_404(email)
    project = get_project_or_404(project_name, luser._id)
    
    if luser not in project.lusers:
        print "[EE] User is not a member of this project."
        flask.abort(403)

    # Set card pile_id's to null if they are a member of the target pile.
    params = dict(pile_id=None)
    models.Card.query.filter_by(pile_id=pile_id).update(params)
    models.db.session.flush()

    # Should now be safe to delete the pile.
    pile = models.Pile.query.filter_by(_id=pile_id).first()
    models.db.session.delete(pile)
    models.db.session.commit()

    return redirect_to("project", name=project_name)


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

#-----------------------------------------------------------------------------
# Privilege Decorators 
#
# These functions are reusable security measures that can 'decorate'
# any view function in order to prevent unauthorized users from 
# obtaining access to them.
#
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

## Cards
##############################################################################

def card_get_comments(project=None, project_name=None, card_id=None, **kwargs):
    """
    Called via .ajax to refresh comments after a comment is added.
    """
    card = query_card(card_id, project._id)
    return flask.render_template("card_comments.html", card=card, 
                                                       project_name=project_name,
                                                       card_id=card_id,
                                                       **kwargs)


@app.route("/project/<project_name>/cards/<int:card_id>/comment", methods=["POST"])
@check_project_privileges
def cards_comment(project_name=None, card_id=None, **kwargs):
    """
    Update the database when a user posts a comment.
    """
    luser = kwargs["luser"]

    text = flask.request.form["text"].encode("UTF-8").strip()

    comment = models.CardComment(card_id=card_id, luser_id=luser._id, text=text)
    models.db.session.add(comment)
    models.db.session.commit()
    models.db.session.flush()

    return card_get_comments(project_name=project_name, card_id=card_id, **kwargs)


@app.route("/project/<project_name>/card/<int:card_id>/archive")
@check_project_privileges
def archive(card_id=None, **kwargs):
    """
    Handles archival of cards.
    """
    card = models.Card.query.filter_by(_id=card_id).first()
    card.is_archived = True
    models.db.session.flush()
    models.db.session.commit()
   
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
    models.db.session.flush()
    models.db.session.commit()

    ## todo: ajaxify 
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
    models.db.session.flush()
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


@app.route("/project/<name>/cards/edit/<int:card_id>", methods=["POST"])
def card_edit(name,card_id):
    """
    Allow editing of card properties from within the modal.
    """

    # Obtain email from session, otherwise, error 403
    email = get_email_or_403()

    # Obtain the luser, or return not found.
    luser = get_luser_or_404(email)
 
    # Do this to make sure the luser is a member of the project. 
    project = get_project_or_404(name, luser._id)


    form = flask.request.form

    # Here we enumerate properties that can possibly be edited. Only
    # one is sent at a time.
    if "text" in form:
        value = form["text"].strip()
        params = dict(text=value)
    elif "description" in form:
        value = form["description"].strip()
        params = dict(description=value)
    else:
        flask.abort(400)

    (models.Card.query.filter(and_(models.Card._id==card_id,
                                   models.Card.project_id==project._id))
                     .update(params))

    models.db.session.commit()

    return value


def query_card(card_id, project_id):
    return (models.Card.query.filter(and_(models.Card._id==card_id,
                                   models.Card.project_id==project_id))
                             .first())


@app.route("/project/<project_name>/cards/<int:card_id>", methods=["GET"])
@check_project_privileges
def cards_get(project_name=None, card_id=None, project=None, **kwargs):
    """
    Used to render a card in a modal dialog.
    """

    is_archived = ("is_archived" in flask.request.args and
                   flask.request.args["is_archived"])

    card = query_card(card_id, project._id)

    if is_archived:
        return flask.render_template("archived_card.html", card=card, project=project, 
                                     project_name=project_name, **kwargs)
    else:
        return flask.render_template("card.html", card=card, project=project, 
                                     project_name=project_name, **kwargs)




@app.route("/project/<project_name>/cards/<int:card_id>/score", methods=["POST"])
@check_project_privileges
def card_score(project_name=None, card_id=None, project=None, **kwargs):
    
    card = query_card(card_id, project._id)
    
    score = int(flask.request.json["score"])
    print "score = %r" % score
    card.score = score
    
    models.db.session.commit()
    return respond_with_json({ "status" : "success",
                               "message" : "updated card %d" % card._id })


@app.route("/project/<project_name>/cards/<int:card_id>/attach", methods=["POST"])
@check_project_privileges
def card_attach_file(project_name=None, card_id=None, luser=None, **kwargs):
    """
    Upload a file & attach it to a card.
    """

    if flask.request.method == 'POST' and "file" in flask.request.files:
        filename = files.save(flask.request.files["file"])

        attachment = models.CardFile(card_id=card_id, luser_id=luser._id, 
                        filename=filename)
        
        models.db.session.add(attachment)
        models.db.session.flush()
        models.db.session.commit()

    return respond_with_json(dict(attachment=attachment, luser=luser))


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


# Piles
##############################################################################
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


def perform_add_card(email, project_name, text, form=None):
    """
    Adds a card to a project. Do not invoke directly, pass as a callback 
    to add_to_project.
    """
    
    # Get the pile id, it's safe to do this here, because not all
    # things we add might need a pile_id, and piles do not have
    # their own permissions within a project.
    if form is None:
        print "[EE] Missing parameters."
        flask.abort(500)

    pile_id = int(form["pile_id"])

    luser = get_luser_or_404(email)
    project = get_project_or_404(project_name, luser._id)
    params = (project_name, luser._id)

    card = models.Card(project_id=project._id, text=text, pile_id=pile_id)
    models.db.session.add(card)
    models.db.session.commit()
    return redirect_to("project", name=project_name)


@app.route("/cards/add", methods=["POST"])
def card_add():
    return add_to_project(perform_add_card)


@app.route("/project/<project_name>/cards/<int:card_id>/complete",
            methods=["POST"])
@check_project_privileges
def card_toggle_is_completed(project=None, card_id=None, **kwargs):
    """
    Facilitate the toggling of the Card's "is_completed" state.
    """
    state = flask.request.json["state"]

    print "state=%r" % state

    card = models.Card.query.filter_by(_id=card_id).first()

    card.is_completed = not state

    models.db.session.commit()
    models.db.session.flush()

    print "card.is_completed = %r" % card.is_completed
    return respond_with_json(dict(state=card.is_completed))


## Milestones
###############################################################################

@app.route("/project/<project_name>/milestones/add", methods=["POST"])
@check_owner_privileges
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
    
    return redirect_to("project_manage", **kwargs)


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
    models.db.session.flush()

    return respond_with_json(dict(state=milestone.is_approved))


# Piles
##############################################################################

def perform_add_pile(email, project_name, name, form=None):
    """
    Adds a pile to a project. Do not invoke directly, pass as a callback 
    to add_to_project.
    """
    luser = get_luser_or_404(email)
    project = get_project_or_404(project_name, luser._id)

    name = name.strip()
    if name == "":
        name = "Unnamed Pile"
    
    card = models.Pile(project_id=project._id, name=name)
    models.db.session.add(card)
    models.db.session.commit()

    return redirect_to("project", name=project_name)


@app.route("/piles/add", methods=["POST"])
def pile_add():
    return add_to_project(perform_add_pile)


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


@app.route("/project/<project_name>/manage")
@check_owner_privileges
def project_manage(project_name=None, project=project, **kwargs):
    """
    Renders the project management view. 

    This view should allow project owners to create milestones, and
    view progress.
    """
  
    # We also need to display project invites
    invites = (models.ProjectInvite.query.filter_by(project_id=project._id)
                     .all())

    return cc_render_template("project_manage.html", project=project,
                              invites=invites, **kwargs)


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
            text = """
You've been invited to join a project on CodeColab!  Please sign up using this
email and you will be added to the project automatically: %(base_url)ssignup.
    """.replace("\n", " ") % { "base_url" : BASE_URL }

            mailer = Mailer(**MAILER_PARAMS)
            mailer.send(from_addr=MAIL_FROM, to_addr=email,
                        subject="You've been invited to %s on CodeColab" % project.name,
                        text=text)
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
        
    return flask.redirect("/project/%s/manage" % project.name)


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

## Signup
###############################################################################

def perform_signup(email, password, confirm):
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

    create_luser_data(luser)

    # If signup was successful, just log the user in.
    return perform_login(email, password)


def create_sample_project_for_luser(luser):
    sample = models.Project(name="Sample")
    models.db.session.add(sample)
    models.db.session.flush()

    assoc = models.ProjectLuser(luser_id=luser._id, 
                                project_id=sample._id,
                                is_owner=True)
    models.db.session.add(assoc)
    models.db.session.flush()

    todo = models.Pile(project_id=sample._id, name="To-Do")
    doing = models.Pile(project_id=sample._id, name="Doing")
    done = models.Pile(project_id=sample._id, name="Done")

    models.db.session.add(todo)
    models.db.session.add(doing)
    models.db.session.add(done)
    models.db.session.flush()

    card1 = models.Card(project_id=sample._id, text="Check out the app!", pile_id=todo._id, score=1)
    card2 = models.Card(project_id=sample._id, text="Make some cards...", pile_id=todo._id, score=1)
    card3 = models.Card(project_id=sample._id, text="Have fun!", pile_id=todo._id, score=0)
    models.db.session.add(card1)
    models.db.session.add(card2)
    models.db.session.add(card3)
    
    models.db.session.commit()


def create_luser_data(luser, first_name="Unknown", last_name="Unknown"):
    email = luser.email

    # Must also create a profile for that user. Default the username
    # to the name part of the email.
    profile = models.LuserProfile(luser_id=luser._id,
                                  first_name=first_name,
                                  last_name=last_name,
                                  username=email.split("@")[0])

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


## Luser Profile
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
        models.db.session.flush()

        flask.flash("Profile updated.")
        return cc_render_template("profile.html", luser=luser, 
                                  profile=profile,
                                  timezones=pytz.all_timezones,
                                  themes=themes,
                                  **kwargs)

## Password Recovery
###############################################################################

@app.route("/reset/<uuid>", methods=["POST", "GET"])
def reset(uuid):

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
def forgot():

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
        models.db.session.flush()
 
        link = BASE_URL + "reset/%s" % request.uuid

        text = """
To reset your CodeColab password, please click this link:
%s. If you received this email in error, it is safe
to ignore it.
""".replace("\n", " ") % link

        mailer = Mailer(**MAILER_PARAMS)
        mailer.send(from_addr=MAIL_FROM, to_addr=email,
                    subject="CodeColab password recovery.", text=text)

        flask.flash("A password recovery email has been sent to: %s" % email)
        return redirect_to_index()
    else:
        return flask.render_template("forgot.html")

## Signup
###############################################################################

@app.route("/signup", methods=["POST", "GET"])
def signup():
    template = "sign-up.html"    

    if flask.request.method == "POST":
        # Obtain references to form parameters 
        email = flask.request.form["email"].strip()
        password = flask.request.form["password"]
        confirm = flask.request.form["confirm"]
       
        return perform_signup(email, password, confirm)
    else:
        return flask.render_template("sign-up.html") 


if __name__ == '__main__':
    port = int(os.environ.get('PORT', PORT))
    app.run(host='0.0.0.0', port=port)
