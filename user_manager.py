import os
import unicodedata
import re
from fastapi_users import BaseUserManager, IntegerIDMixin
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select
from users import User
from database import get_async_db
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from fastapi_users.exceptions import UserNotExists, InvalidPasswordException, UserAlreadyExists
from typing import Optional
from email_service import get_email_service

# Carga el secreto desde variable de entorno (obligatorio)
SECRET = os.getenv("SECRET")

def normalize_string(text: str) -> str:
    """
    Normaliza un string removiendo tildes, acentos y convirtiendo a minúsculas
    """
    if not text:
        return ""
    
    # Convertir a minúsculas
    text = text.lower()
    
    # Remover tildes y acentos usando unicodedata
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
    
    # Remover espacios extra y caracteres especiales (opcional)
    text = re.sub(r'[^\w]', '', text)
    
    return text

class CustomSQLAlchemyUserDatabase(SQLAlchemyUserDatabase):
    async def get_by_email_or_username(self, email_or_username: str) -> Optional[User]:
        """Busca un usuario por email o username (sin distinguir mayúsculas/minúsculas)"""
        statement = select(User).where(
            or_(
                func.lower(User.email) == func.lower(email_or_username),
                func.lower(User.username) == func.lower(email_or_username)
            )
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()
    
    async def check_username_exists(self, username: str) -> bool:
        """
        Verifica si existe un username similar (ignorando mayúsculas y tildes)
        """
        normalized_username = normalize_string(username)
        
        # Buscar todos los usuarios y comparar sus usernames normalizados
        statement = select(User)
        result = await self.session.execute(statement)
        users = result.scalars().all()
        
        for user in users:
            if normalize_string(user.username) == normalized_username:
                return True
        return False
    
    async def check_email_exists(self, email: str) -> bool:
        """
        Verifica si existe un email similar (ignorando mayúsculas)
        """
        statement = select(User).where(func.lower(User.email) == func.lower(email))
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None

class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def create(self, user_create, safe: bool = False, request=None):
        """
        Sobrescribe el método create para agregar validación de duplicados
        """
        # Validar que el email no exista (ignorando mayúsculas)
        if hasattr(self.user_db, 'check_email_exists'):
            email_exists = await self.user_db.check_email_exists(user_create.email)
            if email_exists:
                raise UserAlreadyExists()
        
        # Validar que el username no exista (ignorando mayúsculas y tildes)
        if hasattr(self.user_db, 'check_username_exists') and hasattr(user_create, 'username'):
            username_exists = await self.user_db.check_username_exists(user_create.username)
            if username_exists:
                raise UserAlreadyExists("Username already exists")
        
        # Si pasa las validaciones, crear el usuario normalmente
        return await super().create(user_create, safe, request)

    async def on_after_forgot_password(self, user: User, token: str, request=None):
        """Maneja el evento después de solicitar recuperación de contraseña"""
        print(f"Usuario {user.username} ({user.email}) solicitó recuperación de contraseña.")
        
        # El envío de email se maneja directamente en el endpoint personalizado
        # para permitir usar el idioma de la interfaz del usuario
        print(f"Token de recuperación generado para {user.email}")
            # En producción, podrías querer logear esto de manera más robusta
            # o implementar un sistema de reintentos

    async def on_after_reset_password(self, user: User, request=None):
        """Maneja el evento después de resetear la contraseña"""
        print(f"Usuario {user.username} ({user.email}) ha restablecido su contraseña exitosamente.")

    async def authenticate(self, credentials) -> Optional[User]:
        """Autenticación personalizada que permite email o username"""
        try:
            # Intentar buscar por email o username
            if hasattr(self.user_db, 'get_by_email_or_username'):
                user = await self.user_db.get_by_email_or_username(credentials.username)
            else:
                # Fallback al método original (solo email)
                try:
                    user = await self.user_db.get_by_email(credentials.username)
                except:
                    user = None
            
            if user is None:
                return None
                
            verified, updated_password_hash = self.password_helper.verify_and_update(
                credentials.password, user.hashed_password
            )
            if not verified:
                return None
                
            if updated_password_hash is not None:
                user.hashed_password = updated_password_hash
                await self.user_db.update(user)
                
            return user
        except Exception as e:
            print(f"Error en autenticación: {e}")
            return None

    async def on_after_register(self, user: User, request=None):
        """Maneja el evento después del registro de usuario"""
        print(f"Usuario registrado: {user.id} - {user.username}")
        
        # Obtener el servicio de email
        email_service = get_email_service()
        
        # Determinar el idioma del usuario (por defecto español)
        # En el futuro podrías agregar un campo de idioma al modelo User
        user_language = 'es'  # Por defecto español
        
        try:
            # 1. Enviar email de bienvenida
            welcome_sent = await email_service.send_welcome_email(
                to_email=user.email,
                username=user.username,
                user_language=user_language
            )
            
            if welcome_sent:
                print(f"Email de bienvenida enviado a {user.email}")
            else:
                print(f"Error enviando email de bienvenida a {user.email}")
                
            # 2. Generar token de verificación y enviar email
            verification_token = await self.get_reset_password_token(user)  # Reutilizamos el mismo método
            
            verification_sent = await email_service.send_verification_email(
                to_email=user.email,
                username=user.username,
                verification_token=verification_token,
                user_language=user_language
            )
            
            if verification_sent:
                print(f"Email de verificación enviado a {user.email}")
            else:
                print(f"Error enviando email de verificación a {user.email}")
                
        except Exception as e:
            print(f"Error procesando emails post-registro para {user.email}: {e}")
            # No lanzamos la excepción para no interrumpir el registro

    async def on_after_login(self, user: User, request=None):
        print(f"Usuario logueado: {user.username}")

async def get_user_db(session: AsyncSession = Depends(get_async_db)):
    yield CustomSQLAlchemyUserDatabase(session, User)

async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)
