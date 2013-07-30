from config import MAILER_PARAMS, BASE_URL, MAIL_FROM
from pidgey import Mailer 
from jinja2 import Template
from urllib import quote_plus

meta = dict(app_name="CodeColab")

TEMPLATE_DIR = "emails/"

##############################################################################
# Private
##############################################################################

def _render_email(name, header_name="header.html", with_header=False,
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


def _send_comment_email(template_prefix, recipients, username, comment, 
                        title):
    params = dict(username=username, comment=comment, title=title, meta=meta)

    text = _render_email("%s.txt" % template_prefix, **params)
    subject = _render_email("%s.sub.txt" % template_prefix, **params)
    html = _render_email("%s.html" % template_prefix, **params)
    mailer = Mailer(**MAILER_PARAMS)
    mailer.send(from_addr=MAIL_FROM, to_addr=recipients,
                 subject=subject, text=text, html=html)


##############################################################################
# Public
##############################################################################

def project_invite(project, email, is_registered=True):
    quoted_email = quote_plus(email)

    html = _render_email("project_invite.html", base_url=BASE_URL,
        project=project, meta=meta, email=quoted_email, is_registered=is_registered)

    text = _render_email("project_invite.txt", base_url=BASE_URL,
        project=project, meta=meta, email=quoted_email, is_registered=is_registered)

    subject = _render_email("project_invite.sub.txt", project=project, meta=meta)

    mailer = Mailer(**MAILER_PARAMS)
    mailer.send(from_addr=MAIL_FROM, to_addr=email, subject=subject,
                text=text, html=html)


def member_report(recipients, report, subject):
    html = _render_email("report.html", report=report, meta=meta)
    text = _render_email("report.txt", report=report, meta=meta)
    mailer = Mailer(**MAILER_PARAMS)
    mailer.send(from_addr=MAIL_FROM, to_addr=recipients, subject=subject,
                html=html, text=text)


def forgot_password(email, link):
    text = _render_email("forgot_password.txt", link=link, meta=meta)
    html = _render_email("forgot_password.html", link=link, meta=meta)
    mailer = Mailer(**MAILER_PARAMS)
    mailer.send(from_addr=MAIL_FROM, to_addr=email,
                subject="CodeColab password recovery.", text=text)


def send_welcome_email(luser):
    text = _render_email("welcome.txt", luser=luser, meta=meta)
    html = _render_email("welcome.html", luser=luser, meta=meta)
    subject = _render_email("welcome.sub.txt", luser=luser, meta=meta)
    mailer = Mailer(**MAILER_PARAMS)
    mailer.send(from_addr=MAIL_FROM, to_addr=luser.email,
                    subject=subject, text=text)


def send_report_comment_email(recipients, username, comment, title):
    _send_comment_email("report_comment", recipients, username, comment, title)


def send_card_comment_email(recipients, username, comment, title):
    _send_comment_email("card_comment", recipients, username, comment, title)
