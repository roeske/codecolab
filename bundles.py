from flask import Flask
from flask.ext.assets import Environment, Bundle


def register(app):
    assets = Environment(app)

    project_js = Bundle("js/lodash.min.js", 
                        "js/s3upload.js",
                        "pagedown/Markdown.Converter.js",
                        "pagedown/Markdown.Sanitizer.js",
                        "pagedown/Markdown.Editor.js",
                        "js/tags.js",
                        "js/project.js",
                        "js/jquery.jscroll.js",
                        "js/activity_feed.js",
                        "js/card_attachments.js",
                        output="gen/project_js.js") 

    assets.register("project_js", project_js)
   

    common_js = Bundle("js/jquery-latest.js",
                        "js/jquery-ui.js",
                        "js/jquery.jeditable.js",
                        "js/raty/jquery.raty.js",
                        "js/jquery.form.js" ,
                        "js/project.js",
                        "js/timepicker.js",
                        "js/require.js",
                        "js/select2.js",
                        output="gen/common_js.js")

    assets.register("common_js", common_js)
