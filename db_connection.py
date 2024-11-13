import pymongo

url = "mongodb+srv:***REMOVED***"

client = pymongo.MongoClient(url)
db = client['orca']
db['user_data'].create_index([('email', 1)], unique=True)
user_data = db['user_data']