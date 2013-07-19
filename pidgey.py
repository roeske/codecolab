"""
pidgey.py

Email made simple.

Author:     Thomas Dignan <tom@tomdignan.com>
Date:       Fri Mar 15 02:03:55 EDT 2013
License:    Apache2 License
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class Mailer(object):

    def __init__(self, host="127.0.0.1", port=25, username=None, password=None,
                 starttls=True, debug_env="PIDGEY_DEBUG"):
        """
        Construct a new mailer instance.

        Params:

            host        -- SMTP server host
            port        -- SMTP server port
            username    -- SMTP server username
            password    -- SMTP server password
        """

        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.starttls = starttls
        self.debug_env = debug_env

    def send(self, to_addr, from_addr, subject, text, html=None):
        """
        Send an email. 

        Params:
        
            to_addr <string>    -- recipient
            from_addr <string>  -- sender
            subject <string>    -- subject line
            text <string>       -- plain text version
            html <string>       -- html version
        """ 
        # Note, not "" evaluates to the same as not False,
        # so we must use False == False or "" == False.
        if os.getenv(self.debug_env, False) == False:
            self.smtp = smtplib.SMTP(self.host, self.port)
            print "sending email..."
            msg = self._make_message(to_addr, from_addr, subject, text, html)
            self._send_msg(from_addr, to_addr, msg)
        else:
            print "skipped, since we're in debug mode..."


    def _make_message(self, to_addr, from_addr, subject, text, html):
 
        msg = self._make_message_header(to_addr, from_addr, subject)
        msg.attach(MIMEText(text, "plain"))   

        if html is not None:
            msg.attach(MIMEText(html, "html"))

        return msg
    

    def _make_message_header(self, to_addr, from_addr, subject):
        msg = MIMEMultipart("alternative")

        msg["Subject"] = subject
        msg["From"] = from_addr
        
        if isinstance(to_addr, basestring):
            msg["To"] = to_addr
        else:
            msg["To"] = ", ".join(to_addr)

        return msg


    def _send_msg(self, from_addr, to_addr, msg):
        if self.starttls:
            self.smtp.ehlo()
            self.smtp.starttls()
            self.smtp.ehlo()
           
        if self.username is not None and self.password is not None:
            self.smtp.login(self.username, self.password)

        elif self.username is not None:
            raise ValueError("Username specified, but no password!")

        elif self.password is not None:
            raise ValueError("Password specified, but no username!")

       
        print to_addr

        if isinstance(to_addr, basestring):
            self.smtp.sendmail(from_addr, [to_addr], msg.as_string())
        else:
            self.smtp.sendmail(from_addr, to_addr, msg.as_string())

        self.smtp.close()
