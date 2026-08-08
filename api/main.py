from fastapi import FastAPI
from api.router.routes import router

app = FastAPI()

app.include_router(router,prefix='/v1')

@app.get('/home')
def home():
   return 'Hello, Welcome back, Hammad!'