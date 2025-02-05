from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from api.routes.extend_token_middleware import create_access_token
from typing import Dict, Annotated
from config import get_config

router = APIRouter()

@router.post("/api/token")
def get_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], config: Dict = Depends(get_config)):
    """
    Generate a JWT token for the access to the microservice
    """
    jwt_conf = config.get("jwt")
    sys_user = jwt_conf.get("system_username", "")
    sys_pass = jwt_conf.get("system_password", "")
    if form_data.username != sys_user or form_data.password != sys_pass:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(sys_user, config)
    return {"access_token": access_token, "token_type": "bearer"}