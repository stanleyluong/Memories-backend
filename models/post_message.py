import mongoengine as me
import datetime

class PostMessage(me.Document):
    title = me.StringField(required=True)
    message = me.StringField(required=True)
    name = me.StringField(required=True) # Name of the creator
    creator = me.ReferenceField('User', required=True) # Changed to ReferenceField
    tags = me.ListField(me.StringField())
    selectedFile = me.StringField() # Will store S3 key or path
    likes = me.ListField(me.StringField(), default=[]) # List of user IDs who liked
    # comments = me.ListField(me.StringField(), default=[]) # For future use
    createdAt = me.DateTimeField(default=lambda: datetime.datetime.now(datetime.timezone.utc)) # Timezone-aware UTC

    # Meta information for MongoEngine, like the collection name
    meta = {
        'collection': 'postmessages', # Explicitly set collection name
        'strict': False, # Allow fields not defined in schema (like _id -> id)
        'ordering': ['-createdAt'] # Default sort order
    }

    def to_json_serializable(self):
        post_dict = self.to_mongo().to_dict()
        if '_id' in post_dict:
            post_dict['id'] = str(post_dict.pop('_id'))
        if 'creator' in post_dict and hasattr(self.creator, 'id'): # Ensure creator is populated
            post_dict['creator'] = str(self.creator.id)
        
        # Ensure datetime fields are in ISO format and explicitly UTC
        if 'createdAt' in post_dict and isinstance(post_dict['createdAt'], datetime.datetime):
            dt_obj = post_dict['createdAt']
            # If it's naive, assume it's UTC (our model default is UTC)
            if dt_obj.tzinfo is None or dt_obj.tzinfo.utcoffset(dt_obj) is None:
                dt_obj = dt_obj.replace(tzinfo=datetime.timezone.utc)
            # If it's not UTC, convert it to UTC
            elif dt_obj.tzinfo is not datetime.timezone.utc:
                dt_obj = dt_obj.astimezone(datetime.timezone.utc)
            
            # Format to ISO string. For UTC, this typically includes +00:00 or Z
            post_dict['createdAt'] = dt_obj.isoformat()

        # Do not send base64 selectedFile to client if it somehow still exists
        if 'selectedFile' in post_dict and isinstance(post_dict.get('selectedFile'), str) and post_dict.get('selectedFile', '').startswith('data:image'):
            del post_dict['selectedFile']
            
        return post_dict

    def __str__(self):
        return f"Post(id={self.id}, title='{self.title}', name='{self.name}')"

    # Additional methods can be added here as needed

    # ... rest of the original file content ... 