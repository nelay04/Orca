import pymongo # type: ignore

url = "mongodb+srv:***REMOVED***"

client = pymongo.MongoClient(url)
db = client['orca']
db['user_data'].create_index([('email', 1)], unique=True)
db['user_data'].create_index([('user_name', 1)], unique=True)
# user_data = db['user_data']
# friend_list = db['friend_list']