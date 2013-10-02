from flask import Flask
from flask.ext.assets import Environment, Bundle


def register(app):
    assets = Environment(app)

    project_js = Bundle("js/lodash.min.js", 
                        "js/socket.io.js",
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
                        "js/lightbox-2.6.min.js",
                        output="gen/common_js.js")

    assets.register("common_js", common_js)

    theme_light_css = Bundle("css/jquery-ui.css",
                            "css/themes/light/bootstrap.css",
                            "css/themes/light/app.css",
                            "css/themes/light/card.css",
                            "css/themes/light/comments.css",
                            "css/themes/light/project_manage.css",
                            "css/themes/light/project_selection.css",
                            "css/themes/light/custom_tooltip.css",
                            "css/themes/light/profile.css",
                            "css/timepicker.css",
                            "css/common/reports.css",
                            "css/common/icons.css",
                            "css/select2.css",
                            "css/common/lightbox.css",
    #                        "css/common/screen.css",
                            output="gen/theme_light_css.css")

    assets.register("theme_light_css", theme_light_css)

    common_css = Bundle("css/google_open_sans.css",
                        "css/common/project_selection.css",
                        "css/common/office_hours.css",
                        "css/common/activity.css",
                        "css/common/members.css",
                        "css/common/editor.css",
                        output="gen/common_css.css")

    assets.register("common_css", common_css)
