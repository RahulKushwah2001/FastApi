from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from neo4j import GraphDatabase

app = FastAPI()

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def get_db():
    with driver.session() as session:
        yield session


class UserCreate(BaseModel):
    name: str
    email: str
    age: int
    gender: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    age: int
    gender: str

class RelationshipCreate(BaseModel):
    source_id: int
    target_id: int
    relationship_type: str


class RelationshipDelete(BaseModel):
    source_id: int
    target_id: int
    relationship_type: str



@app.post("/users/", response_model=UserResponse)
def create_user(user: UserCreate, db=Depends(get_db)):
    query = """
    CREATE (u:User {name: $name, email: $email, age: $age, gender: $gender})
    RETURN id(u) as id, u.name AS name, u.email AS email, u.age AS age, u.gender AS gender
    """
    result = db.run(query, name=user.name, email=user.email, age=user.age, gender=user.gender)
    created_user = result.single()

    if not created_user:
        raise HTTPException(status_code=500, detail="Failed to create user")

    return created_user


@app.get("/users/", response_model=List[UserResponse])
def read_all_users(db=Depends(get_db)):
    query = """
    MATCH (u:User)
    RETURN id(u) AS id, u.name AS name, u.email AS email, u.age AS age, u.gender AS gender
    """
    result = db.run(query)
    users = [record.data() for record in result]
    return users


@app.get("/users/{user_id}", response_model=UserResponse)
def read_user(user_id: int, db=Depends(get_db)):
    query = """
    MATCH (u:User) WHERE id(u) = $user_id
    RETURN id(u) AS id, u.name AS name, u.email AS email, u.age AS age, u.gender AS gender
    """
    result = db.run(query, user_id=user_id).single()
    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")
    return result.data()


@app.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user: UserUpdate, db=Depends(get_db)):
    updates = []
    params = {}
    for key, value in user.dict(exclude_unset=True).items():
        updates.append(f"u.{key} = ${key}")
        params[key] = value
    query = f"""
    MATCH (u:User) WHERE id(u) = $user_id
    SET {", ".join(updates)}
    RETURN id(u) AS id, u.name AS name, u.email AS email, u.age AS age, u.gender AS gender
    """
    params["user_id"] = user_id
    result = db.run(query, **params).single()
    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")
    return result.data()


@app.delete("/users/{user_id}")
def delete_user(user_id: int, db=Depends(get_db)):

    query = """
    MATCH (u:User) WHERE id(u) = $user_id
    DELETE u
    """
    result = db.run(query, user_id=user_id)

    summary = result.consume()
    if summary.counters.nodes_deleted == 0:
        raise HTTPException(status_code=404, detail="User Not Found")

    return {"message": f"User with ID {user_id} has been successfully deleted."}

@app.post("/relationships/")
def create_relationship(relationship: RelationshipCreate, db=Depends(get_db)):
    query = """
    MATCH (source), (target)
    WHERE id(source) = $source_id AND id(target) = $target_id
    CREATE (source)-[r:{relationship_type}]->(target)
    RETURN id(r) AS relationship_id
    """
    params = {
        "source_id": relationship.source_id,
        "target_id": relationship.target_id,
        "relationship_type": relationship.relationship_type
    }

    formatted_query = query.replace("{relationship_type}", relationship.relationship_type)

    result = db.run(formatted_query, **params).single()
    if not result:
        raise HTTPException(status_code=404, detail="Nodes not found or relationship creation failed")
    return {"relationship_id": result["relationship_id"]}


@app.delete("/relationships/")
def delete_relationship(relationship: RelationshipDelete, db=Depends(get_db)):
    query = """
    MATCH (source)-[r:{relationship_type}]->(target)
    WHERE id(source) = $source_id AND id(target) = $target_id
    DELETE r
    """
    params = {
        "source_id": relationship.source_id,
        "target_id": relationship.target_id,
        "relationship_type": relationship.relationship_type
    }

    formatted_query = query.replace("{relationship_type}", relationship.relationship_type)

    result = db.run(formatted_query, **params)

    summary = result.consume()
    if summary.counters.relationships_deleted == 0:
        raise HTTPException(status_code=404, detail="Relationship not found")

    return {
        "message": f"Relationship of type '{relationship.relationship_type}' between nodes {relationship.source_id} and {relationship.target_id} has been successfully deleted."
    }