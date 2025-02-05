import jwt
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from config import get_config
from ..models.system_user import SystemUser
from typing import Annotated
from api.routes.dependencies import reuseable_oauth

def create_access_token(sub: str, config: dict):
    to_encode = {"sub": "user@user.us"}
    jwt_cfg = config.get("jwt")
    secret_key = jwt_cfg["secret_key"]
    algorithm = jwt_cfg["algorithm"]
    expires_delta = timedelta(minutes=jwt_cfg["expiration"])
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt

def verify_and_extend_token(token: Annotated[str, Depends(reuseable_oauth)], request: Request, response:Response):
    """
    Verify the token and extend it if it's close to expiry
    Args: 
        token: The JWT token to verify
        secret_key: The secret key used to sign the token
        algorithm: The algorithm used to sign the token
    Returns:
        The original token if it's not close to expiry, or a new token if it is
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    config = request.app.state.config
    jwt_cfg = config.get("jwt")
    secret_key = jwt_cfg.get("secret_key", None)
    algorithm = jwt_cfg.get("algorithm", None)
    sliding_threshold = jwt_cfg.get("sliding_expiration_threshold")
    if any(v is None for v in [secret_key, algorithm, sliding_threshold]):
        raise HTTPException(status_code=500, detail="JWT configuration is missing")

    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        remaining_time = (exp - datetime.now(timezone.utc)).total_seconds()  # In seconds

        if remaining_time < sliding_threshold:
            print("Token near expiration, extending...")
            # add to response headers new token
            new_token = create_access_token(payload["sub"], config)
            response.headers["Authorization"] = f"Bearer {new_token}"
            response.headers["X-Token-Extended"] = "true"
            return SystemUser(sub=payload["sub"])
        
        return SystemUser(sub=payload["sub"])
    except jwt.ExpiredSignatureError:
        raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception

# class AutoExtendTokenMiddleware(BaseHTTPMiddleware):
#     """Middleware that catches all POST requests."""
#     async def dispatch(self, request: Request, call_next):
#         response = await call_next(request)

#         cfg = request.app.state.config
#         jwt_cfg = cfg.get("jwt")
#         SECRET_KEY = jwt_cfg.get("secret_key")
#         ALGORITHM = jwt_cfg.get("algorithm")

#         # Check if the request is a POST
#         auth_header = request.headers.get("Authorization")
#         if auth_header and auth_header.startswith("Bearer "):
#             token = auth_header.split(" ")[1]
#             try:
#                 new_token = verify_and_extend_token(token, SECRET_KEY, ALGORITHM)
#                 response.headers["Authorization"] = f"Bearer {new_token}"
#             except ValueError as e:
#                 response = Response(content=str(e), status_code=401)

#         return response
