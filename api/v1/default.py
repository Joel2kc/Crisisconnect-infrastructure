from fastapi import APIRouter

home_route = APIRouter(
  prefix="/api/v1",
  tags=["Health Check"],
)

@home_route.get("/")
def home():
  return {"message": "Welcome to the CrisisConnect API"}

@home_route.get("/health")
def health_check():
  return {"status": "UP"}