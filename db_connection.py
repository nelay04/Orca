import os

import pymongo  # type: ignore
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get('MONGO_URL')

# Constructing a MongoClient does not open a connection, PyMongo connects
# lazily on first use. Index creation does hit the server, so it lives in
# ensure_indexes() rather than running at import time: otherwise importing
# this module would make every manage.py command fail without a live MongoDB.
client = pymongo.MongoClient(url)
db = client['orca']


def ensure_indexes():
    """Create the unique indexes the app depends on.

    Run via `python manage.py init_mongo`. Safe to run repeatedly.
    """
    # email and username should be unique in user_data collection
    db['user_data'].create_index([('email', 1)], unique=True)
    db['user_data'].create_index([('user_name', 1)], unique=True)

    # Ensures that the combination of user_name_sender and user_name_receiver
    # is unique in friend_request_list collection
    db['friend_request_list'].create_index(
        [('user_name_sender', 1), ('user_name_receiver', 1)],
        unique=True
    )
