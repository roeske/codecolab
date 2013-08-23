from github_flask import GitHub

TESTING = True

if TESTING:
    BASE_URL = "http://localhost:8080"
else:
    BASE_URL = "http://www.codecolab.com"

def setup(app):
    app.config['GITHUB_CALLBACK_URL'] = BASE_URL + "/github/callback"

    if TESTING:
        app.config['GITHUB_CLIENT_ID'] = 'be3d3e9e59cc50bc14ca'
        app.config['GITHUB_CLIENT_SECRET'] = 'f7ee25a9935525907d4a9b1b3f63891db4f6dc2a'
    else:
        app.config['GITHUB_CLIENT_ID'] = '5851cf84441c928ff151'
        app.config['GITHUB_CLIENT_SECRET'] = '1311e09f2539c97347b3c9c942832a0d906ca15f'
    return GitHub(app)
