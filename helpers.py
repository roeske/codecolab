import flask
import models
from md5 import md5
import simplejson as json
from jinja2 import Template

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


TEMPLATE_DIR = "emails/"

def render_email(name, header_name="header.html", with_header=False,
                              header_params={}, **kwargs):
    if with_header:
        with open("%s/%s" % (TEMPLATE_DIR, header_name), "r") as header_file:
            header_template = Template(header_file.read())
            header = header_template.render(**header_params)
    else:
        header = ""
    
    with open("%s/%s" % (TEMPLATE_DIR, name), "r") as template_file:
        template = Template(template_file.read())
        return str(header + template.render(**kwargs))

    return "<html><head></head><body>Template %s not found</body></html>" % name    
