from flask import Blueprint, request, jsonify, current_app
from models.post_message import PostMessage # Changed to direct import
from middleware.auth_middleware import auth_required # Changed to direct import
import math
from mongoengine.queryset.visitor import Q
import datetime # Ensure datetime is imported for createdAt
import traceback # Add this import
import mongoengine
import boto3 # Add boto3 for S3
import uuid    # Add uuid for unique filenames
import os      # Add os to access environment variables

# Blueprint Configuration
posts_bp = Blueprint(
    'posts_bp',
    __name__,
    url_prefix='/posts' # All routes in this blueprint will be prefixed with /posts
)

@posts_bp.route('/', methods=['GET'])
def get_posts():
    # Diagnostic log for Lambda's current time
    lambda_current_utc_time = datetime.datetime.utcnow()
    print(f"LAMBDA DIAGNOSTIC: Current UTC time according to Lambda is {lambda_current_utc_time.isoformat()}")

    page = request.args.get('page', 1, type=int)
    LIMIT = 8
    startIndex = (page - 1) * LIMIT

    try:
        total = PostMessage.objects.count()
        # MongoEngine uses .order_by('-_id') for descending sort by id
        posts = PostMessage.objects.order_by('-id').skip(startIndex).limit(LIMIT)
        
        # Convert MongoEngine documents to JSON serializable format
        posts_list = []
        for post in posts:
            # Assuming PostMessage model has a to_json_serializable method
            # or you manually construct the dict.
            # Using the to_json_serializable method from the model:
            if hasattr(post, 'to_json_serializable') and callable(getattr(post, 'to_json_serializable')):
                posts_list.append(post.to_json_serializable())
            else: # Fallback to manual construction if method is missing
                posts_list.append({
                    'id': str(post.id),
                    'title': post.title,
                    'message': post.message,
                    'name': post.name,
                    'creator': post.creator,
                    'tags': post.tags,
                    'selectedFile': post.selectedFile,
                    'likes': post.likes,
                    'comments': post.comments,
                    'createdAt': post.createdAt.isoformat() if post.createdAt else None
                })

        return jsonify({
            'data': posts_list,
            'currentPage': page,
            'numberOfPages': math.ceil(total / LIMIT)
        }), 200
    except mongoengine.errors.LookUpError as e:
        current_app.logger.error(f"LookUpError in get_posts: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({"message": f"Field lookup error: {str(e)}"}), 500
    except Exception as e:
        current_app.logger.error(f"Error in get_posts: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({"message": "An unexpected error occurred fetching posts."}), 500

@posts_bp.route('/<string:id>', methods=['GET'])
def get_post(id):
    try:
        # MongoEngine's get method raises DoesNotExist or MultipleObjectsReturned
        # if not found or multiple found, respectively.
        # We can also use .objects(id=id).first() which returns None if not found.
        post = PostMessage.objects(id=id).first()
        if post:
            post_data = {
                'id': str(post.id),
                'title': post.title,
                'message': post.message,
                'name': post.name,
                'creator': post.creator,
                'tags': post.tags,
                'selectedFile': post.selectedFile,
                'likes': post.likes,
                'comments': post.comments,
                'createdAt': post.createdAt.isoformat()
            }
            return jsonify(post_data), 200
        else:
            return jsonify(message="Post not found"), 404
    except Exception as e:
        # Catching specific exceptions like ValidationError from mongoengine might be better
        print(f"Error in get_post: {e}")
        if "ValidationError" in str(type(e)): # Basic check for invalid ObjectId format
             return jsonify(message="Invalid Post ID format"), 400
        return jsonify(message=str(e)), 500 

@posts_bp.route('/search', methods=['GET'])
def get_posts_by_search():
    search_query = request.args.get('searchQuery', '')
    tags = request.args.get('tags', '') # Comma-separated string

    try:
        query_conditions = []
        if search_query:
            # MongoEngine query for case-insensitive regex on title
            query_conditions.append(PostMessage.title.matches(f"(?i){search_query}"))
        
        if tags:
            tags_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            if tags_list:
                # MongoEngine query for tags in list
                query_conditions.append(PostMessage.tags.in_(tags_list))
        
        if not query_conditions:
            return jsonify(data=[]), 200 # Or perhaps an error/message?

        # MongoEngine uses Q objects for $or, $and logic if not directly chainable
        # For a simple OR, you can often construct it manually or use Q for clarity
        # If using Q: from mongoengine.queryset.visitor import Q
        # posts = PostMessage.objects(Q(title__icontains=search_query) | Q(tags__in=tags_list))
        # For simplicity here, if only one condition, use it. If both, this requires $or.
        # A direct $or equivalent in MongoEngine for complex queries can be done via raw query dictionary
        # or by constructing Q objects.

        # Simplified: if we have search_query OR tags. If both, this finds docs matching EITHER.
        # For MongoEngine, the .objects() call with multiple keyword arguments implies an AND.
        # To achieve OR, we need to use Q objects or filter multiple times and combine.
        # Let's try a more direct translation of the $or logic using MongoEngine's syntax:

        final_query = None
        if search_query and tags_list:
            final_query = Q(title__icontains=search_query) | Q(tags__in=tags_list)
        elif search_query:
            final_query = Q(title__icontains=search_query)
        elif tags_list:
            final_query = Q(tags__in=tags_list)
        
        if final_query:
            posts = PostMessage.objects(final_query)
        else:
            posts = PostMessage.objects.none() # Returns an empty queryset

        posts_list = []
        for post in posts:
            posts_list.append({
                'id': str(post.id),
                'title': post.title,
                'message': post.message,
                'name': post.name,
                'creator': post.creator,
                'tags': post.tags,
                'selectedFile': post.selectedFile,
                'likes': post.likes,
                'comments': post.comments,
                'createdAt': post.createdAt.isoformat()
            })
        return jsonify(data=posts_list), 200
    except Exception as e:
        print(f"Error in get_posts_by_search: {e}")
        return jsonify(message=str(e)), 500 

@posts_bp.route('/', methods=['POST'])
@auth_required
def create_post(current_user_id): # current_user_id is injected by @auth_required
    data = request.get_json()
    if not data:
        return jsonify(message="No input data provided"), 400

    try:
        # Ensure all required fields for PostMessage are present or handled
        new_post = PostMessage(
            title=data.get('title'),
            message=data.get('message'),
            name=data.get('name'), # Name of the user posting, usually from user profile
            creator=current_user_id, # Set by auth_required decorator
            tags=data.get('tags', []),
            selectedFile=data.get('selectedFile', ''),
            # likes and comments default to empty lists in the model
        )
        new_post.save() # This will also validate based on model definition
        
        # Prepare response data (similar to get_post)
        post_data = {
            'id': str(new_post.id),
            'title': new_post.title,
            'message': new_post.message,
            'name': new_post.name,
            'creator': new_post.creator,
            'tags': new_post.tags,
            'selectedFile': new_post.selectedFile,
            'likes': new_post.likes,
            'comments': new_post.comments,
            'createdAt': new_post.createdAt.isoformat()
        }
        return jsonify(post_data), 201
    except Exception as e:
        # More specific error handling (e.g., mongoengine.errors.ValidationError)
        print(f"Error in create_post: {e}")
        # 409 Conflict was used in Node.js, usually for duplicate unique entries.
        # If it's a general validation error, 400 Bad Request might be more appropriate.
        # For now, let's use 400 for general save errors as 409 has specific meaning.
        if "ValidationError" in str(type(e)):
            return jsonify(message=f"Validation Error: {str(e)}"), 400
        return jsonify(message=f"Error creating post: {str(e)}"), 500 

@posts_bp.route('/<string:id>', methods=['PATCH'])
@auth_required
def update_post(current_user_id, id):
    data = request.get_json()
    if not data:
        return jsonify(message="No update data provided"), 400

    try:
        post = PostMessage.objects(id=id).first()
        if not post:
            return jsonify(message="Post not found"), 404

        # Security check: Optionally, ensure the user updating the post is the creator
        # if post.creator != current_user_id:
        #     return jsonify(message="User not authorized to update this post"), 403

        # Update fields from data. MongoEngine's .update() or modifying and .save()
        # For partial updates, .update() is efficient. 
        # If you need to run pre/post save hooks defined on the model, modify and .save().
        
        # Example: post.title = data.get('title', post.title) ... then post.save()
        # Or using update_one for atomic update:
        update_fields = {}
        if 'title' in data: update_fields['set__title'] = data['title']
        if 'message' in data: update_fields['set__message'] = data['message']
        if 'name' in data: update_fields['set__name'] = data['name'] # Name of user?
        if 'tags' in data: update_fields['set__tags'] = data['tags']
        if 'selectedFile' in data: update_fields['set__selectedFile'] = data['selectedFile']
        # Cannot update creator or createdAt typically. Likes/comments handled by separate endpoints.

        if not update_fields:
            return jsonify(message="No valid fields to update provided"), 400

        post.update(**update_fields) # Atomic update
        post.reload() # Reload to get the updated document for the response

        post_data = {
            'id': str(post.id),
            'title': post.title,
            'message': post.message,
            'name': post.name,
            'creator': post.creator,
            'tags': post.tags,
            'selectedFile': post.selectedFile,
            'likes': post.likes,
            'comments': post.comments,
            'createdAt': post.createdAt.isoformat()
        }
        return jsonify(post_data), 200
    except Exception as e:
        print(f"Error in update_post: {e}")
        if "ValidationError" in str(type(e)): # For invalid ID format
             return jsonify(message="Invalid Post ID format or validation error"), 400
        return jsonify(message=str(e)), 500 

@posts_bp.route('/<string:id>', methods=['DELETE'])
@auth_required
def delete_post(current_user_id, id):
    try:
        post = PostMessage.objects(id=id).first()
        if not post:
            return jsonify(message="Post not found"), 404

        # Security check: Optionally, ensure the user deleting the post is the creator
        # if post.creator != current_user_id:
        #     return jsonify(message="User not authorized to delete this post"), 403

        post.delete() # MongoEngine's delete method
        return jsonify(message="Post Deleted successfully"), 200
    except Exception as e:
        print(f"Error in delete_post: {e}")
        if "ValidationError" in str(type(e)): # For invalid ID format
             return jsonify(message="Invalid Post ID format"), 400
        return jsonify(message=str(e)), 500 

@posts_bp.route('/<string:id>/likePost', methods=['PATCH'])
@auth_required
def like_post(current_user_id, id):
    try:
        post = PostMessage.objects(id=id).first()
        if not post:
            return jsonify(message="Post not found"), 404

        # The user ID (current_user_id) is already a string from the decorator
        if current_user_id in post.likes:
            # User has liked it, so unlike: remove user_id from likes
            post.update(pull__likes=current_user_id)
        else:
            # User hasn't liked it yet, so like: add user_id to likes
            post.update(add_to_set__likes=current_user_id) # add_to_set ensures no duplicates
        
        post.reload() # Reload to get the updated document

        post_data = {
            'id': str(post.id),
            'title': post.title,
            'message': post.message,
            'name': post.name,
            'creator': post.creator,
            'tags': post.tags,
            'selectedFile': post.selectedFile,
            'likes': post.likes,
            'comments': post.comments,
            'createdAt': post.createdAt.isoformat()
        }
        return jsonify(post_data), 200
    except Exception as e:
        print(f"Error in like_post: {e}")
        if "ValidationError" in str(type(e)):
             return jsonify(message="Invalid Post ID format"), 400
        return jsonify(message=str(e)), 500 

@posts_bp.route('/<string:id>/commentPost', methods=['POST'])
@auth_required
def comment_post(current_user_id, id): # current_user_id is available if needed
    data = request.get_json()
    comment_value = data.get('value')

    if not comment_value:
        return jsonify(message="Comment value cannot be empty"), 400

    try:
        post = PostMessage.objects(id=id).first()
        if not post:
            return jsonify(message="Post not found"), 404

        # Add the comment. The original code pushed the raw value.
        # You might want to store comments as objects with user ID, name, timestamp, etc.
        # For now, replicating the simple string push.
        post.update(push__comments=comment_value)
        post.reload()

        post_data = {
            'id': str(post.id),
            'title': post.title,
            'message': post.message,
            'name': post.name,
            'creator': post.creator,
            'tags': post.tags,
            'selectedFile': post.selectedFile,
            'likes': post.likes,
            'comments': post.comments, # This will now include the new comment
            'createdAt': post.createdAt.isoformat()
        }
        return jsonify(post_data), 200
    except Exception as e:
        print(f"Error in comment_post: {e}")
        if "ValidationError" in str(type(e)):
             return jsonify(message="Invalid Post ID format"), 400
        return jsonify(message=str(e)), 500 

@posts_bp.route('/signed-url/upload', methods=['GET'])
@auth_required # Optional: protect this route if needed
def get_signed_url_for_upload(current_user_id): # current_user_id from @auth_required
    filename = request.args.get('filename')
    filetype = request.args.get('filetype')

    if not filename or not filetype:
        return jsonify({"message": "filename and filetype query parameters are required"}), 400

    # Retrieve S3 bucket name and region from environment variables
    s3_bucket_name = os.environ.get('S3_BUCKET_NAME')
    aws_region_name = os.environ.get('AWS_REGION_NAME')

    if not s3_bucket_name or not aws_region_name:
        current_app.logger.error("S3_BUCKET_NAME or AWS_REGION_NAME environment variables not set.")
        return jsonify({"message": "Server configuration error for S3 uploads."}), 500

    # Generate a unique key for the S3 object
    # Example: uploads/user_id/uuid_filename.ext
    # Ensure file extension is preserved or correctly set based on filetype
    file_extension = filename.rsplit('.', 1)[-1] if '.' in filename else ''
    unique_key = f"uploads/{current_user_id}/{uuid.uuid4()}.{file_extension}"

    s3_client = boto3.client(
        's3',
        region_name=aws_region_name,
        config=boto3.session.Config(signature_version='s3v4') # Recommended for pre-signed URLs
    )

    try:
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': s3_bucket_name, 'Key': unique_key, 'ContentType': filetype},
            ExpiresIn=3600  # URL expiration time in seconds (e.g., 1 hour)
        )
        return jsonify({'uploadURL': presigned_url, 'key': unique_key}), 200
    except Exception as e:
        current_app.logger.error(f"Error generating S3 pre-signed URL: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({"message": "Could not generate S3 upload URL."}), 500 