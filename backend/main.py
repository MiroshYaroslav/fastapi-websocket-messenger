import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, chat, users
from services.websockets import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    listener_task = asyncio.create_task(manager.listen_to_redis())
    yield
    listener_task.cancel()
    await manager.pubsub.close()
    await manager.redis_client.close()


app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost",
    "http://localhost:80",
    "http://127.0.0.1",
    "http://127.0.0.1:80",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(chat.router)
