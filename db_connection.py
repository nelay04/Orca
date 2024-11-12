import pymongo

url = "mongodb+srv:***REMOVED***"

client = pymongo.MongoClient(url)
db = client['orca']