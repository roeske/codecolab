import os
import flask
import models
import bcrypt
import json
import models

app = models.app

PORT = 8080

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
    if "card_id" in flask.request.args:
        return delete_card(flask.request.args.get("card_id"))

    return flask.abort(500)


def delete_card(card_id):
    """
    Deletes a todo list item by id.
    """
    todo = models.Card.query.filter_by(_id=card_id).first()
    models.db.session.delete(todo)
    models.db.session.commit()
    return flask.redirect(flask.url_for("index"))


# Add Project
###############################################################################


@app.route("/project/add", methods=["POST"])
def project_add():
    form = flask.request.form
    if "project_name" in form and "email" in form:
        email = form["email"]
        project_name = form["project_name"]
        return perform_project_add(email, project_name)
    else:
        print "[EE] Missing parameters."
        return flask.abort(400)


def perform_project_add(email, project_name):
    luser = get_luser_for_email(email)
    if luser is None:
        return flask.abort(400)

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


# Convenience Methods 
###############################################################################

def redirect_to(page):
    return flask.redirect(flask.url_for(page))

def redirect_to_index():
    return redirect_to("index")

def get_luser_for_email(email):
    return models.Luser.query.filter_by(email=email).first()


def get_projects_for_luser_id(luser_id):
    return (models.Project.query.join(models.Project.lusers)
                          .filter(models.Luser._id==luser_id)).all()


def add_card_for_luser(email, text):
    luser = get_luser_for_email(email)
    todo = models.Card(luser_id=luser._id, text=text)
    models.db.session.add(todo)
    models.db.session.commit()
    return render_index(email)


# Views 
###############################################################################

def render_index(email):
    return render_project_selection(email)


def render_project_selection(email):
    luser = get_luser_for_email(email)
    projects = get_projects_for_luser_id(luser._id)
    return flask.render_template("project_selection.html", email=email, projects=projects)


def render_project(email, project_id):
    luser = get_luser_for_email(email)
    project = get_project(project_id)
    return flask.render_template("project.html", email=email, project=project)


def respond_with_json(obj):
    " Helper for returning a JSON response body."
    mimetype = "application/json;charset=UTF-8"
    return flask.Response(json.dumps(obj), mimetype=mimetype)


@app.route("/todo/reorder", methods=["POST"])
def card_reorder():
    """
    Must be called at the end of any drag on the todo list. Used to update
    the new sort order of the todo-list in the database.

    Expected POST body:
    ------------------
        {
            "updates" : [
                { 
                    _id : <integer id>,
                    number : <new sort position number>
                }, ...
            ]
        }
    """
    for update in flask.request.json["updates"]:
        _id = int(update["_id"])
        number = int(update["number"])
        models.Card.query.filter_by(_id=_id).update(dict(number=number))
        models.db.session.commit()
    return respond_with_json({"status" : "success" })


@app.route('/', methods=["POST", "GET"])
def index():
    """
    Serves the index. Responsible for delegating to several 
    screens based on the state and type of request.
    """
    is_logged_in = "email" in flask.session
    
    if flask.request.method == "GET" and is_logged_in:
        email = flask.session["email"]
        return render_index(email)

    elif flask.request.method == "POST" and is_logged_in:
        # Add a TO-DO for the logged in user.
        email = flask.session["email"]
        text = flask.request.form["text"]
        return add_card_for_luser(email, text)

    if flask.request.method == "GET" and not is_logged_in:
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
