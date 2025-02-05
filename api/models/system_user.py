from pydantic import BaseModel

class SystemUser(BaseModel):
    sub: str