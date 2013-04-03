#!/usr/bin/env python
"""
remind_user_to_report.py

This script sends the user a reminder if he has a schedule but
has not made a daily report.
"""
from delorean import Delorean
from sys import path
path.append("..")

import models
from pidgey import Mailer

from config import MAILER_PARAMS, MAIL_FROM, BASE_URL 

message = """
Dear %(username)s,

We noticed that you had scheduled hours today on %(project)s, and it's been an hour since your quitting time. Please log in so that you can report to your project owner.

%(url)s
""" 

#return d.datetime.strftime("%A, %b. %d, %Y at %I:%M %p")

day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]

print "Today's scheduled work"
print "----------------------"
print "user\tstart_time\tend_time"

# Iterate each user
for luser in models.Luser.query.all():
   
    # We need to use the time in the user's own timezone, because
    # we are storing naive times in the user's schedule.
    now = Delorean(timezone=luser.profile[0].timezone).datetime
    day = now.weekday()

    mailer = Mailer(**MAILER_PARAMS)

    # Users have multiple schedules. Check all of them.
    for schedule in luser.schedules:

        # Check each day until we hit the day that is today, in the
        # user's timezone.
        for range in schedule.ranges:
            if range.day is not None and range.day.name == day_names[day]:

                # Print out today's users who have hours, as an aid.
                print "%s\t%s\t%s" % (luser.profile[0].username,
                                      range.start_time,
                                      range.end_time)

                
                # Only notify within the first 15 minutes of the hour after.
                # This will allow us to use the flow of time to avoid 
                # duplicating notifications.
                time_now = now.time()
               

                end_time_in_minutes = range.end_time.hour * 60 + range.end_time.minute
                now_in_minutes = time_now.hour * 60 + time_now.minute

                # If it is within 15 minutes after an hour has passed,
                # send the reminder email
                if end_time_in_minutes + 60 < now_in_minutes and \
                    now_in_minutes < end_time_in_minutes + 75:

                    # send the email.
                    mailer.send(from_addr=MAIL_FROM, to_addr=luser.email,
                                subject="Reminder: Please report in on %s" % \
                                schedule.project.name,
                                text=message % \
                                { "username" : luser.profile[0].username,
                                  "project" : schedule.project.name,
                                  "url" : BASE_URL })
                else:
                    print "no mail sent."
