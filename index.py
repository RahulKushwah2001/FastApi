from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from neo4j import GraphDatabase
from datetime import datetime

app = FastAPI()

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "rahul1234"
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def get_session():
    return driver.session()

class CreatePostRequest(BaseModel):
    id: str
    content: str
    timestamp: str

class CreateUserRequest(BaseModel):
    id: str
    name: str

class User(BaseModel):
    id: str
    name: str

class Post(BaseModel):
    id: str
    content: str
    timestamp: str

class FollowResponse(BaseModel):
    message: str

class UserResponse(User):
    pass

class PostResponse(Post):
    pass

def create_user(user_id: str, name: str):
    with get_session() as session:
        query = """
        CREATE (u:User {id: $user_id, name: $name})
        RETURN u
        """
        result = session.run(query, user_id=user_id, name=name)
        return result.single()

def create_post(post_id: str, content: str, timestamp: str):
    with get_session() as session:
        query = """
        CREATE (p:Post {id: $post_id, content: $content, timestamp: $timestamp})
        RETURN p
        """
        result = session.run(query, post_id=post_id, content=content, timestamp=timestamp)
        return result.single()

def create_follow(follower_id: str, followee_id: str):
    with get_session() as session:
        query = """
        MATCH (follower:User {id: $follower_id}), (followee:User {id: $followee_id})
        CREATE (follower)-[:FOLLOW]->(followee)
        RETURN follower, followee
        """
        result = session.run(query, follower_id=follower_id, followee_id=followee_id)
        return result.single()

def create_like(user_id: str, post_id: str):
    with get_session() as session:
        query = """
        MATCH (user:User {id: $user_id}), (post:Post {id: $post_id})
        CREATE (user)-[:LIKE]->(post)
        RETURN user, post
        """
        result = session.run(query, user_id=user_id, post_id=post_id)
        return result.single()

def get_followers(user_id: str):
    with get_session() as session:
        query = """
        MATCH (follower:User)-[:FOLLOW]->(user:User {id: $user_id})
        RETURN follower
        """
        try:
            result = session.run(query, user_id=user_id)
            followers = []
            for record in result:

                follower_node = record.get("follower")
                if follower_node is not None:
                    followers.append(follower_node._properties)
            return followers
        except Exception as e:
            raise Exception(f"Neo4j query error: {str(e)}")


def get_following(user_id: str):
    with get_session() as session:
        query = """
        MATCH (user:User {id: $user_id})-[:FOLLOW]->(followee:User)
        RETURN followee
        """
        try:
            result = session.run(query, user_id=user_id)
            following = []
            for record in result:
                followee_node = record.get("followee")
                if followee_node is not None:  
                    following.append(followee_node._properties)
            return following
        except Exception as e:
            raise Exception(f"Neo4j query error: {str(e)}")

def get_likes(post_id: str):
    with get_session() as session:
        query = """
        MATCH (user:User)-[:LIKE]->(post:Post {id: $post_id})
        RETURN user
        """
        try:
            result = session.run(query, post_id=post_id)
            users_liked = []
            for record in result:

                user_node = record.get("user")
                if user_node is not None:

                    users_liked.append(user_node._properties)
            return users_liked
        except Exception as e:
            raise Exception(f"Neo4j query error: {str(e)}")

# Route to create a new user
@app.post("/users", response_model=UserResponse)
async def create_user_route(user: CreateUserRequest):
    try:
        created_user = create_user(user.id, user.name)
        return UserResponse(id=user.id, name=user.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")

# Route to create a new post
@app.post("/posts", response_model=PostResponse)
async def create_post_route(post: CreatePostRequest):
    try:
        created_post = create_post(post.id, post.content, post.timestamp)
        return PostResponse(id=post.id, content=post.content, timestamp=post.timestamp)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating post: {str(e)}")


@app.post("/users/{follower_id}/follow/{followee_id}", response_model=FollowResponse)
async def follow_user(follower_id: str, followee_id: str):
    try:
        create_follow(follower_id, followee_id)
        return {"message": "Follow relationship created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating follow relationship: {str(e)}")


@app.post("/users/{user_id}/like/{post_id}", response_model=FollowResponse)
async def like_post(user_id: str, post_id: str):
    try:
        create_like(user_id, post_id)
        return {"message": "Like relationship created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating like relationship: {str(e)}")

# Route to get all followers of a user
@app.get("/users/{user_id}/followers", response_model=List[UserResponse])
async def get_user_followers(user_id: str):
    try:
        followers = get_followers(user_id)
        if not followers:
            raise HTTPException(status_code=404, detail="No followers found for this user")
        return followers
    except Exception as e:
        # Return the specific error message from Neo4j
        raise HTTPException(status_code=500, detail=f"Error fetching followers: {str(e)}")


@app.get("/users/{user_id}/following", response_model=List[UserResponse])
async def get_user_following(user_id: str):
    try:
        following = get_following(user_id)
        if not following:
            raise HTTPException(status_code=404, detail="This user is not following anyone")
        return following
    except Exception as e:
        # Return the specific error message from Neo4j
        raise HTTPException(status_code=500, detail=f"Error fetching following: {str(e)}")


@app.get("/posts/{post_id}/likes", response_model=List[UserResponse])
async def get_post_likes(post_id: str):
    try:
        users_liked = get_likes(post_id)
        if not users_liked:
            raise HTTPException(status_code=404, detail="No users liked this post")
        return users_liked
    except Exception as e:
        # Return the specific error message from Neo4j
        raise HTTPException(status_code=500, detail=f"Error fetching likes: {str(e)}")