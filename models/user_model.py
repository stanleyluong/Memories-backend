from mongoengine import Document, StringField

class User(Document):
    name = StringField(required=True)
    email = StringField(required=True, unique=True) # Assuming email should be unique
    password = StringField(required=True)
    # In Mongoose, 'id' is often an alias for '_id' or a Google ID.
    # MongoEngine automatically provides an 'id' field (ObjectId).
    # If this 'id' was specifically for a Google ID or similar external ID, 
    # you might want to name it explicitly, e.g., google_id = StringField()
    # For now, I'll assume the default MongoEngine 'id' is sufficient, 
    # or this was perhaps a virtual. If it was storing the _id as a string, 
    # it's redundant with MongoEngine's own id.
    # We will omit adding an explicit 'id' field here unless it served a distinct purpose.

    meta = {
        'collection': 'users' # Mongoose default collection name for model 'User'
    } 