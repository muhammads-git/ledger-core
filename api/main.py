from fastapi import FastAPI
from api.router.routes import router
# from api.auths.authentication import auth_router
from api.auths.authentication import auths_router
from api.router.transactions import trans_router

app = FastAPI()
app.include_router(auths_router,tags=['auths'])
app.include_router(router,prefix='/v1',tags=['features'])
app.include_router(trans_router,tags=['transactions'])
# app.include_router(auth_router)


@app.get('/home')
def home():
   return 'Hello, Welcome back, Hammad!'