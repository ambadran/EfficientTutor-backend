
# load the url of production url
source ../.env

# install production db copy
pg_dump $DATABASE_URL --format=c --no-owner --no-privileges > prod_backup.dump

# load production db copy onto test db
#TODO: the user on mac is ambadran717, make a condition to condition the correct user
pg_restore --clean --if-exists -h localhost -U mr_a_717 -d efficient_tutor_test_db --no-owner prod_backup.dump
