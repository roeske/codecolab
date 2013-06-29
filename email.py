from config import MAILER_PARAMS, BASE_URL
from pidgey import Mailer 

meta = dict(app_name="CodeColab")

def project_invite(project, email):
    html = render_email("project_invite.html", base_url=BASE_URL, project=project, meta=meta)
    text = render_email("project_invite.txt", base_url=BASE_URL, project=project, meta=meta)
    subject = render_email("project_invite.sub.txt", project=project, meta=meta)
    mailer = Mailer(**MAILER_PARAMS)
    mailer.send(from_addr=MAIL_FROM, to_addr=email, subject=subject,
                text=text, html=html)

def member_report(recipients, report, subject):
    html = render_email("report.html", report=report, meta=meta)
    text = render_email("report.txt", report=report, meta=meta)
    mailer = Mailer(**MAILER_PARAMS)
    mailer.send(from_addr=MAIL_FROM, to_addr=recipients, subject=subject,
                html=html, text=text)


def forgot_password(email, link):
    text = render_email("forgot_password.txt", link=link, meta=meta)
    html = render_email("forgot_password.html", link=link, meta=meta)
    mailer = Mailer(**MAILER_PARAMS)
    mailer.send(from_addr=MAIL_FROM, to_addr=email,
                subject="CodeColab password recovery.", text=text)


def send_welcome_email(luser):
    text = render_email("welcome.txt", luser=luser, meta=meta)
    html = render_email("welcome.html", luser=luser, meta=meta)
    subject = render_email("welcome.sub.txt", luser=luser, meta=meta)
    mailer = Mailer(**MAILER_PARAMS)
    mailer.send(from_addr=MAIL_FROM, to_addr=luser.email,
                    subject=subject, text=text)


