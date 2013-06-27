export AWS_ACCESS_KEY_ID=$(heroku config:get AWS_ACCESS_KEY_ID)
export DATABASE_URL=$(heroku config:get DATABASE_URL)
export AWS_SECRET_ACCESS_KEY=$(heroku config:get AWS_SECRET_ACCESS_KEY)
export S3_BUCKET=$(heroku config:get S3_BUCKET)

