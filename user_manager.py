import os
from fastapi_users import BaseUserManager, IntegerIDMixin
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from users import User
from database import get_async_db
from fastapi_users.db import SQLAlchemyUserDatabase

# Carga el secreto desde variable de entorno (obligatorio)
SECRET = os.getenv("SECRET")

class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request=None):
        print(f"Usuario registrado: {user.id}")

async def get_user_db(session: AsyncSession = Depends(get_async_db)):
    yield SQLAlchemyUserDatabase(session, User)

async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)
