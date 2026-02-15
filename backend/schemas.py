from pydantic import BaseModel, Field, ConfigDict
from typing import Annotated

class BaseUser(BaseModel):
    name: Annotated[str, Field(..., title="The username", min_length=1, max_length=20)]
    age: Annotated[int, Field(..., title="The age of the user", ge=10, le=120)]

class CreateUser(BaseUser):
    password: Annotated[str, Field(..., title="The password of the user", min_length=5)]

class UserResponse(BaseUser):
    id: int
    model_config = ConfigDict(from_attributes=True)

class BasePost(BaseModel):
    title: str
    comment: str
    author_id: int

class PostResponse(BasePost):
    id: int
    author: UserResponse

    model_config = ConfigDict(from_attributes=True)

class CreatePost(BasePost):
    pass

class Token(BaseModel):
    access_token: str
    token_type: str



