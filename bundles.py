from flask import Flask
from flask.ext.assets import Environment, Bundle


def register(app):
    assets = Environment(app)
    assets.debug = False 

    css_overrides = Bundle("css/jquery-ui.css",
                           "css/google_open_sans.css",
                           "css/app.css", 
                           "css/timepicker.css",
                           "css/select2.css",
                           output="gen/overrides.css")

    assets.register("css_overrides", css_overrides)


    boards_js = Bundle("js/select2.js",
                       "js/socket.io.js",
                       "js/jquery-ui.js",
                       "js/timepicker.js",
                       "js/raty/jquery.raty.js",
                        output="gen/boards_js.js") 

    assets.register("boards_js", boards_js)
