from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from services.auth_service import verify_access_token
from services.inference_service import (
    get_recent_inference_runs,
    invoke_model_endpoint,
    list_playground_deployments,
)


router = APIRouter(prefix="/playground", tags=["Model Playground"])
security = HTTPBearer(auto_error=False)


class InferenceRequest(BaseModel):
    deployment_id: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=5000)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required.")
    user = verify_access_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.")
    return user


@router.get("/deployments")
def get_playground_deployments(current_user: dict = Depends(get_current_user)):
    return {"deployments": list_playground_deployments()}


@router.get("/history")
def get_playground_history(limit: int = 20, current_user: dict = Depends(get_current_user)):
    return {"runs": get_recent_inference_runs(max(1, min(limit, 100)))}


@router.post("/invoke")
def invoke_model(request: InferenceRequest, current_user: dict = Depends(get_current_user)):
    deployment = next(
        (item for item in list_playground_deployments() if item["id"] == request.deployment_id),
        None,
    )
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    if not deployment["configured"]:
        raise HTTPException(status_code=503, detail=f"{deployment['cloud']} inference is not configured.")
    try:
        return invoke_model_endpoint(deployment, request.text.strip(), current_user["username"])
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
