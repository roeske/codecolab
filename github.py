from github_flask import GitHub

def setup(app):
    app.config['GITHUB_CLIENT_ID'] = '5851cf84441c928ff151'
    app.config['GITHUB_CLIENT_SECRET'] = '1311e09f2539c97347b3c9c942832a0d906ca15f'
   # app.config['GITHUB_CALLBACK_URL'] = "http://www.codecolab.com/github-callback"
    app.config['GITHUB_CALLBACK_URL'] = "http://localhost:8080/github-callback"
    return GitHub(app)


