from flask import Flask
from flask.ext.assets import Environment, Bundle


def register(app):
    assets = Environment(app)
    assets.debug = True

    css_overrides = Bundle("css/google_open_sans.css",
                           "css/app.css", 
                           output="gen/overrides.css")

    assets.register("css_overrides", css_overrides)


    boards_js = Bundle("js/jquery.jeditable.js",
                       "js/select2.js",
                       "js/socket.io.js",
                       "js/jquery-ui.js",
                        output="gen/boards_js.js") 

    assets.register("boards_js", boards_js)
