import os
import flask
import models
import bcrypt
import json
import models

from sqlalchemy import and_
from md5 import md5

app = models.app

PORT = 8080


def is_logged_in():
    return "email" in flask.session


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


def get_projects_for_luser_id(luser_id):
    return (models.Project.query.join(models.Project.lusers)
                          .filter(models.Luser._id==luser_id)).all()


def render_index(email, **kwargs):
    return render_project_selection(email, **kwargs)


def render_project_selection(email, **kwargs):
    luser = get_luser_for_email(email)
    projects = get_projects_for_luser_id(luser._id)
    return flask.render_template("project_selection.html", email=email,
                                 projects=projects, **kwargs)


def respond_with_json(obj):
    " Helper for returning a JSON response body."
    mimetype = "application/json;charset=UTF-8"
    return flask.Response(json.dumps(obj), mimetype=mimetype)


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

    # ensure that there is a login for this luser.
    if luser is None:
        error = "Email is not registered."
        return flask.render_template(template, email_error=error)

    # ensure that this luser's password is correct.
    elif bcrypt.hashpw(password, luser.pw_hash) == luser.pw_hash:
        flask.session["email"] = email
        return flask.redirect(flask.url_for("index"))

    # handle wrong passwords
    else:
        error = "Password is incorrect."
        return flask.render_template(template, password_error=error)


# Delete
###############################################################################

@app.route("/delete")
def delete():
    """
    Handles deletion of entities.
    """
    args = flask.request.args

    
    if is_logged_in() and "card_id" in args and "project_name" in args:
        email = flask.session["email"]
        card_id = args.get("card_id")
        project_name = args.get("project_name")
        return perform_delete_card(email, card_id, project_name)
                                    
    print "[EE] Insufficient parameters."
    flask.abort(400)


def perform_delete_card(email, card_id, project_name):
    """
    Deletes a card list item by id. Performs basic security checks
    first.
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
    return redirect_to("project", name=project_name)


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


# Cards
##############################################################################

@app.route("/cards/reorder", methods=["POST"])
def card_reorder():
    """
    Must be called at the end of any drag on the card list. Used to update
    the new sort order of the card-list in the database. Also repositions
    cards in appropriate piles.

    Expected POST body:
    ------------------
        {
            "updates" : [
                { 
                    _id : <integer id>,
                    pile_id : <pile_id>,
                    number : <new sort position number>
                }, ...
            ]
        }
    """

    print "%r" % flask.request.json
    for update in flask.request.json["updates"]:
        _id = int(update["_id"])
        number = int(update["number"])
        pile_id = int(update["pile_id"])
        card = models
        print "[DD] update=%r" % update
        models.Card.query.filter_by(_id=_id).update(dict(number=number, 
                                                         pile_id=pile_id))
    
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


# Projects
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


def render_project(project_name, email):
     
    luser = get_luser_for_email(email)
    if luser is None:
        print "[EE] No user found for email=%r" % email
        flask.abort(404)

    project = get_project(project_name, luser._id)
    if project is None:
        params = (project_name, luser._id)
        print "[EE] No project found for name=%r and luser_id=%r" % params
        flask.abort(404)

    gravatar_url = make_gravatar_url(email)
    profile_url = make_gravatar_profile_url(email)

    json_pile_ids = json.dumps([p.pile_uuid for p in project.piles])

    return flask.render_template("project.html", email=email, 
                                                 project=project,
                                                 gravatar_url=gravatar_url,
                                                 profile_url=profile_url,
                                                 json_pile_ids=json_pile_ids) 


@app.route("/project/<name>")
def project(name):
    if is_logged_in():        
        email = flask.session["email"]
        return render_project(name, email)
    else:
        print "[EE] Must be logged in."
        flask.abort(403)


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
    user = models.Luser(email=email, pw_hash=pw_hash)
    models.db.session.add(user)
    models.db.session.commit()

    # If signup was successful, just log the user in.
    return perform_login(email, password)


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
