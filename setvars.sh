export AWS_ACCESS_KEY_ID=$(heroku config:get --app $1 AWS_ACCESS_KEY_ID)
export DATABASE_URL=$(heroku config:get --app $1 DATABASE_URL)
export AWS_SECRET_ACCESS_KEY=$(heroku config:get --app $1 AWS_SECRET_ACCESS_KEY)
export S3_BUCKET=$(heroku config:get --app $1 S3_BUCKET)

echo "AWS_SECRET_ACCESS_KEY=$AWS_ACCESS_KEY_ID"
echo "DATABASE_URL=$DATABASE_URL"
echo "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY"
echo "S3_BUCKET=$S3_BUCKET"
