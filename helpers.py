import flask
import models
from md5 import md5

################################################################################
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

# JSONIZE!
def _handler(o):
    if hasattr(o, 'isoformat') and callable(o.isoformat):
        return o.isoformat()
    raise TypeError("Can't serialize %r" % (o,))

jsonize = lambda d: json.dumps(d, default=_handler)
