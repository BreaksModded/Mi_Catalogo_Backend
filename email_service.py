import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging
from email_translations import get_email_translation
from config import (
    SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_USE_TLS,
    EMAIL_FROM, EMAIL_FROM_NAME, FRONTEND_URL, EMAIL_DEVELOPMENT_MODE
)

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        # Configuración desde config.py
        self.smtp_server = SMTP_HOST
        self.smtp_port = SMTP_PORT
        self.smtp_username = SMTP_USERNAME
        self.smtp_password = SMTP_PASSWORD
        self.use_tls = SMTP_USE_TLS
        self.from_email = EMAIL_FROM
        self.from_name = EMAIL_FROM_NAME
        
        # Modo desarrollo
        self.development_mode = EMAIL_DEVELOPMENT_MODE or not (self.smtp_username and self.smtp_password)
        
        if self.development_mode:
            logger.info("Email service en modo desarrollo - los emails se mostrarán en consola")
        else:
            logger.info(f"Email service configurado con SMTP: {self.smtp_server}:{self.smtp_port}")

    async def send_password_reset_email(self, to_email: str, username: str, reset_token: str, user_language: str = 'es') -> bool:
        """Envía email de recuperación de contraseña en el idioma del usuario"""
        try:
            # URL de recuperación
            reset_url = f"{FRONTEND_URL}/reset-password?token={reset_token}"
            
            # Obtener traducciones en el idioma del usuario
            subject = get_email_translation(user_language, 'subject')
            title = get_email_translation(user_language, 'title')
            subtitle = get_email_translation(user_language, 'subtitle')
            greeting = get_email_translation(user_language, 'greeting', username=username)
            message = get_email_translation(user_language, 'message')
            instruction = get_email_translation(user_language, 'instruction')
            button_text = get_email_translation(user_language, 'buttonText')
            alternative_text = get_email_translation(user_language, 'alternativeText')
            expiration_warning = get_email_translation(user_language, 'expirationWarning')
            no_request_warning = get_email_translation(user_language, 'noRequestWarning')
            thanks = get_email_translation(user_language, 'thanks')
            footer = get_email_translation(user_language, 'footer')
            
            # HTML template para el email con diseño actualizado
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{subject}</title>
                <style>
                    * {{
                        box-sizing: border-box;
                        margin: 0;
                        padding: 0;
                    }}
                    body {{ 
                        font-family: 'Segoe UI', Arial, sans-serif; 
                        line-height: 1.6; 
                        color: #ffffff; 
                        background-color: #181818;
                        margin: 0;
                        padding: 20px;
                    }}
                    .container {{ 
                        max-width: 600px; 
                        margin: 0 auto; 
                        background-color: #2a2a2a;
                        border-radius: 16px;
                        overflow: hidden;
                        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                    }}
                    .header {{ 
                        background: linear-gradient(135deg, #00e2c7 0%, #00b8a5 100%); 
                        color: #181818; 
                        padding: 40px 30px; 
                        text-align: center;
                    }}
                    .header h1 {{ 
                        font-size: 32px; 
                        font-weight: 700; 
                        margin: 0 0 10px 0;
                        text-align: center;
                    }}
                    .header h2 {{ 
                        font-size: 20px; 
                        font-weight: 600; 
                        margin: 0;
                        opacity: 0.9;
                        text-align: center;
                    }}
                    .content {{ 
                        background: #2a2a2a; 
                        color: #ffffff;
                        padding: 40px 30px; 
                    }}
                    .content p {{
                        margin: 0 0 16px 0;
                        font-size: 16px;
                        line-height: 1.6;
                    }}
                    .button-container {{
                        text-align: center;
                        margin: 30px 0;
                    }}
                    .button {{ 
                        display: inline-block; 
                        background: linear-gradient(135deg, #00e2c7 0%, #00b8a5 100%); 
                        color: #181818; 
                        padding: 16px 32px; 
                        text-decoration: none; 
                        border-radius: 8px; 
                        font-weight: 600;
                        font-size: 16px;
                        transition: all 0.3s ease;
                        box-shadow: 0 4px 15px rgba(0, 226, 199, 0.3);
                    }}
                    .button:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 8px 25px rgba(0, 226, 199, 0.4);
                    }}
                    .url-box {{
                        background: #1a1a1a;
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        padding: 16px;
                        border-radius: 8px;
                        word-break: break-all;
                        font-family: 'Courier New', monospace;
                        font-size: 14px;
                        color: #00e2c7;
                        margin: 20px 0;
                    }}
                    .warning {{
                        background: rgba(239, 68, 68, 0.1);
                        border: 1px solid rgba(239, 68, 68, 0.3);
                        color: #ef4444;
                        padding: 16px;
                        border-radius: 8px;
                        margin: 20px 0;
                        font-weight: 500;
                        text-align: center;
                    }}
                    .info {{
                        background: rgba(59, 130, 246, 0.1);
                        border: 1px solid rgba(59, 130, 246, 0.3);
                        color: #3b82f6;
                        padding: 16px;
                        border-radius: 8px;
                        margin: 20px 0;
                        text-align: center;
                    }}
                    .thanks {{
                        text-align: center;
                        font-size: 18px;
                        margin-top: 30px;
                    }}
                    .footer {{ 
                        text-align: center; 
                        padding: 30px;
                        background: #1a1a1a;
                        color: rgba(255, 255, 255, 0.6);
                        font-size: 14px;
                        border-top: 1px solid rgba(255, 255, 255, 0.1);
                    }}
                    
                    /* Responsive */
                    @media (max-width: 480px) {{
                        body {{ padding: 10px; }}
                        .container {{ border-radius: 12px; }}
                        .header {{ padding: 30px 20px; }}
                        .header h1 {{ font-size: 28px; }}
                        .content {{ padding: 30px 20px; }}
                        .button {{ padding: 14px 24px; font-size: 15px; }}
                        .footer {{ padding: 25px 20px; }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🎬 {title}</h1>
                        <h2>{subtitle}</h2>
                    </div>
                    <div class="content">
                        <p><strong>{greeting},</strong></p>
                        
                        <p>{message}</p>
                        
                        <p>{instruction}</p>
                        
                        <div class="button-container">
                            <a href="{reset_url}" class="button">{button_text}</a>
                        </div>
                        
                        <p>{alternative_text}</p>
                        <div class="url-box">
                            {reset_url}
                        </div>
                        
                        <div class="warning">
                            <strong>⏰ {expiration_warning}</strong>
                        </div>
                        
                        <div class="info">
                            🔒 {no_request_warning}
                        </div>
                        
                        <p class="thanks"><strong>{thanks}</strong></p>
                    </div>
                    <div class="footer">
                        <p>{footer}</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Texto plano alternativo
            text_body = f"""
            {greeting},

            {message}

            {instruction}
            {reset_url}

            {expiration_warning}

            {no_request_warning}

            {thanks}
            """
            
            if self.development_mode:
                # Modo desarrollo - mostrar en consola
                return await self._send_development_email(to_email, subject, text_body, reset_url, user_language)
            else:
                # Modo producción - enviar email real
                return await self._send_smtp_email(to_email, subject, html_body, text_body)
                
        except Exception as e:
            logger.error(f"Error enviando email de recuperación: {e}")
            return False

    async def _send_development_email(self, to_email: str, subject: str, body: str, reset_url: str, user_language: str = 'es') -> bool:
        """Simula envío de email en desarrollo"""
        print("\n" + "="*80)
        print("📧 EMAIL DE DESARROLLO SIMULADO")
        print("="*80)
        print(f"Para: {to_email}")
        print(f"Idioma: {user_language}")
        print(f"Asunto: {subject}")
        print("-"*80)
        print(body)
        print("-"*80)
        print(f"🔗 ENLACE DE RECUPERACIÓN:")
        print(f"   {reset_url}")
        print("="*80)
        print("💡 Para configurar email real, configura las variables SMTP_USERNAME y SMTP_PASSWORD")
        print("="*80 + "\n")
        return True

    async def _send_smtp_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        """Envía email real usando SMTP"""
        try:
            # Crear mensaje
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email

            # Agregar versiones texto plano y HTML
            part1 = MIMEText(text_body, 'plain', 'utf-8')
            part2 = MIMEText(html_body, 'html', 'utf-8')
            
            msg.attach(part1)
            msg.attach(part2)

            # Conectar y enviar
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
                
            logger.info(f"Email de recuperación enviado exitosamente a {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email SMTP: {e}")
            return False

    async def send_welcome_email(self, to_email: str, username: str, user_language: str = 'es') -> bool:
        """Envía email de bienvenida al usuario"""
        try:
            # Obtener traducciones en el idioma del usuario
            subject = get_email_translation(user_language, 'welcome_subject')
            title = get_email_translation(user_language, 'welcome_title')
            subtitle = get_email_translation(user_language, 'welcome_subtitle')
            greeting = get_email_translation(user_language, 'welcome_greeting', username=username)
            message = get_email_translation(user_language, 'welcome_message')
            features = get_email_translation(user_language, 'welcome_features')
            feature1 = get_email_translation(user_language, 'welcome_feature1')
            feature2 = get_email_translation(user_language, 'welcome_feature2')
            feature3 = get_email_translation(user_language, 'welcome_feature3')
            feature4 = get_email_translation(user_language, 'welcome_feature4')
            feature5 = get_email_translation(user_language, 'welcome_feature5')
            button_text = get_email_translation(user_language, 'welcome_button_text')
            help_text = get_email_translation(user_language, 'welcome_help_text')
            thanks = get_email_translation(user_language, 'welcome_thanks')
            footer = get_email_translation(user_language, 'footer')
            
            # HTML template para el email de bienvenida
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{subject}</title>
                <style>
                    * {{
                        box-sizing: border-box;
                        margin: 0;
                        padding: 0;
                    }}
                    body {{ 
                        font-family: 'Segoe UI', Arial, sans-serif; 
                        line-height: 1.6; 
                        color: #ffffff; 
                        background-color: #181818;
                        margin: 0;
                        padding: 20px;
                    }}
                    .container {{ 
                        max-width: 600px; 
                        margin: 0 auto; 
                        background-color: #2a2a2a;
                        border-radius: 16px;
                        overflow: hidden;
                        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                    }}
                    .header {{ 
                        background: linear-gradient(135deg, #e50914 0%, #b81d24 100%); 
                        color: #ffffff; 
                        padding: 40px 30px; 
                        text-align: center;
                    }}
                    .header h1 {{ 
                        font-size: 32px; 
                        font-weight: 700; 
                        margin: 0 0 10px 0;
                        text-align: center;
                    }}
                    .header h2 {{ 
                        font-size: 20px; 
                        font-weight: 600; 
                        margin: 0;
                        opacity: 0.9;
                        text-align: center;
                    }}
                    .content {{ 
                        background: #2a2a2a; 
                        color: #ffffff;
                        padding: 40px 30px; 
                    }}
                    .content p {{
                        margin: 0 0 16px 0;
                        font-size: 16px;
                        line-height: 1.6;
                    }}
                    .features-list {{
                        background: #1a1a1a;
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        padding: 20px;
                        border-radius: 8px;
                        margin: 20px 0;
                    }}
                    .features-list p {{
                        margin: 8px 0;
                        font-size: 15px;
                    }}
                    .button-container {{
                        text-align: center;
                        margin: 30px 0;
                    }}
                    .button {{ 
                        display: inline-block; 
                        background: linear-gradient(135deg, #e50914 0%, #b81d24 100%); 
                        color: #ffffff; 
                        padding: 16px 32px; 
                        text-decoration: none; 
                        border-radius: 8px; 
                        font-weight: 600;
                        font-size: 16px;
                        transition: all 0.3s ease;
                        box-shadow: 0 4px 15px rgba(229, 9, 20, 0.3);
                    }}
                    .button:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 8px 25px rgba(229, 9, 20, 0.4);
                    }}
                    .info {{
                        background: rgba(59, 130, 246, 0.1);
                        border: 1px solid rgba(59, 130, 246, 0.3);
                        color: #3b82f6;
                        padding: 16px;
                        border-radius: 8px;
                        margin: 20px 0;
                        text-align: center;
                    }}
                    .thanks {{
                        text-align: center;
                        font-size: 18px;
                        margin-top: 30px;
                        font-weight: 600;
                    }}
                    .footer {{ 
                        text-align: center; 
                        padding: 30px;
                        background: #1a1a1a;
                        color: rgba(255, 255, 255, 0.6);
                        font-size: 14px;
                        border-top: 1px solid rgba(255, 255, 255, 0.1);
                    }}
                    
                    /* Responsive */
                    @media (max-width: 480px) {{
                        body {{ padding: 10px; }}
                        .container {{ border-radius: 12px; }}
                        .header {{ padding: 30px 20px; }}
                        .header h1 {{ font-size: 28px; }}
                        .content {{ padding: 30px 20px; }}
                        .button {{ padding: 14px 24px; font-size: 15px; }}
                        .footer {{ padding: 25px 20px; }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🎬 {title}</h1>
                        <h2>{subtitle}</h2>
                    </div>
                    <div class="content">
                        <p><strong>{greeting}</strong></p>
                        
                        <p>{message}</p>
                        
                        <p><strong>{features}</strong></p>
                        <div class="features-list">
                            <p>{feature1}</p>
                            <p>{feature2}</p>
                            <p>{feature3}</p>
                            <p>{feature4}</p>
                            <p>{feature5}</p>
                        </div>
                        
                        <div class="button-container">
                            <a href="{FRONTEND_URL}" class="button">{button_text}</a>
                        </div>
                        
                        <div class="info">
                            💡 {help_text}
                        </div>
                        
                        <p class="thanks">{thanks}</p>
                    </div>
                    <div class="footer">
                        <p>{footer}</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Texto plano alternativo
            text_body = f"""
            {greeting}

            {message}

            {features}
            {feature1}
            {feature2}
            {feature3}
            {feature4}
            {feature5}

            {help_text}

            {thanks}
            """
            
            if self.development_mode:
                # Modo desarrollo - mostrar en consola
                print(f"\n=== EMAIL DE BIENVENIDA (DESARROLLO) ===")
                print(f"Para: {to_email}")
                print(f"Asunto: {subject}")
                print(f"Idioma: {user_language}")
                print("=" * 50)
                print(text_body)
                print("=" * 50)
                return True
            else:
                # Modo producción - enviar email real
                return await self._send_smtp_email(to_email, subject, text_body, html_body)
                
        except Exception as e:
            logger.error(f"Error enviando email de bienvenida: {e}")
            return False

    async def send_verification_email(self, to_email: str, username: str, verification_token: str, user_language: str = 'es') -> bool:
        """Envía email de verificación de cuenta"""
        try:
            # URL de verificación
            verify_url = f"{FRONTEND_URL}/verify-email?token={verification_token}"
            
            # Obtener traducciones en el idioma del usuario
            subject = get_email_translation(user_language, 'verify_subject')
            title = get_email_translation(user_language, 'verify_title')
            subtitle = get_email_translation(user_language, 'verify_subtitle')
            greeting = get_email_translation(user_language, 'verify_greeting', username=username)
            message = get_email_translation(user_language, 'verify_message')
            instruction = get_email_translation(user_language, 'verify_instruction')
            button_text = get_email_translation(user_language, 'verify_button_text')
            alternative_text = get_email_translation(user_language, 'verify_alternative_text')
            expiration_warning = get_email_translation(user_language, 'verify_expiration_warning')
            benefits = get_email_translation(user_language, 'verify_benefits')
            thanks = get_email_translation(user_language, 'verify_thanks')
            footer = get_email_translation(user_language, 'footer')
            
            # HTML template para el email de verificación
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{subject}</title>
                <style>
                    * {{
                        box-sizing: border-box;
                        margin: 0;
                        padding: 0;
                    }}
                    body {{ 
                        font-family: 'Segoe UI', Arial, sans-serif; 
                        line-height: 1.6; 
                        color: #ffffff; 
                        background-color: #181818;
                        margin: 0;
                        padding: 20px;
                    }}
                    .container {{ 
                        max-width: 600px; 
                        margin: 0 auto; 
                        background-color: #2a2a2a;
                        border-radius: 16px;
                        overflow: hidden;
                        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                    }}
                    .header {{ 
                        background: linear-gradient(135deg, #00e2c7 0%, #00b8a5 100%); 
                        color: #181818; 
                        padding: 40px 30px; 
                        text-align: center;
                    }}
                    .header h1 {{ 
                        font-size: 32px; 
                        font-weight: 700; 
                        margin: 0 0 10px 0;
                        text-align: center;
                    }}
                    .header h2 {{ 
                        font-size: 20px; 
                        font-weight: 600; 
                        margin: 0;
                        opacity: 0.9;
                        text-align: center;
                    }}
                    .content {{ 
                        background: #2a2a2a; 
                        color: #ffffff;
                        padding: 40px 30px; 
                    }}
                    .content p {{
                        margin: 0 0 16px 0;
                        font-size: 16px;
                        line-height: 1.6;
                    }}
                    .button-container {{
                        text-align: center;
                        margin: 30px 0;
                    }}
                    .button {{ 
                        display: inline-block; 
                        background: linear-gradient(135deg, #00e2c7 0%, #00b8a5 100%); 
                        color: #181818; 
                        padding: 16px 32px; 
                        text-decoration: none; 
                        border-radius: 8px; 
                        font-weight: 600;
                        font-size: 16px;
                        transition: all 0.3s ease;
                        box-shadow: 0 4px 15px rgba(0, 226, 199, 0.3);
                    }}
                    .button:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 8px 25px rgba(0, 226, 199, 0.4);
                    }}
                    .url-box {{
                        background: #1a1a1a;
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        padding: 16px;
                        border-radius: 8px;
                        word-break: break-all;
                        font-family: 'Courier New', monospace;
                        font-size: 14px;
                        color: #00e2c7;
                        margin: 20px 0;
                    }}
                    .warning {{
                        background: rgba(255, 193, 7, 0.1);
                        border: 1px solid rgba(255, 193, 7, 0.3);
                        color: #ffc107;
                        padding: 16px;
                        border-radius: 8px;
                        margin: 20px 0;
                        font-weight: 500;
                        text-align: center;
                    }}
                    .info {{
                        background: rgba(59, 130, 246, 0.1);
                        border: 1px solid rgba(59, 130, 246, 0.3);
                        color: #3b82f6;
                        padding: 16px;
                        border-radius: 8px;
                        margin: 20px 0;
                        text-align: center;
                    }}
                    .thanks {{
                        text-align: center;
                        font-size: 18px;
                        margin-top: 30px;
                    }}
                    .footer {{ 
                        text-align: center; 
                        padding: 30px;
                        background: #1a1a1a;
                        color: rgba(255, 255, 255, 0.6);
                        font-size: 14px;
                        border-top: 1px solid rgba(255, 255, 255, 0.1);
                    }}
                    
                    /* Responsive */
                    @media (max-width: 480px) {{
                        body {{ padding: 10px; }}
                        .container {{ border-radius: 12px; }}
                        .header {{ padding: 30px 20px; }}
                        .header h1 {{ font-size: 28px; }}
                        .content {{ padding: 30px 20px; }}
                        .button {{ padding: 14px 24px; font-size: 15px; }}
                        .footer {{ padding: 25px 20px; }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🎬 {title}</h1>
                        <h2>{subtitle}</h2>
                    </div>
                    <div class="content">
                        <p><strong>{greeting},</strong></p>
                        
                        <p>{message}</p>
                        
                        <p>{instruction}</p>
                        
                        <div class="button-container">
                            <a href="{verify_url}" class="button">{button_text}</a>
                        </div>
                        
                        <p>{alternative_text}</p>
                        <div class="url-box">
                            {verify_url}
                        </div>
                        
                        <div class="warning">
                            <strong>⏰ {expiration_warning}</strong>
                        </div>
                        
                        <div class="info">
                            ✨ {benefits}
                        </div>
                        
                        <p class="thanks"><strong>{thanks}</strong></p>
                    </div>
                    <div class="footer">
                        <p>{footer}</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Texto plano alternativo
            text_body = f"""
            {greeting},

            {message}

            {instruction}
            {verify_url}

            {expiration_warning}

            {benefits}

            {thanks}
            """
            
            if self.development_mode:
                # Modo desarrollo - mostrar en consola
                print(f"\n=== EMAIL DE VERIFICACIÓN (DESARROLLO) ===")
                print(f"Para: {to_email}")
                print(f"Asunto: {subject}")
                print(f"Idioma: {user_language}")
                print(f"Token: {verification_token}")
                print("=" * 50)
                print(text_body)
                print("=" * 50)
                return True
            else:
                # Modo producción - enviar email real
                return await self._send_smtp_email(to_email, subject, text_body, html_body)
                
        except Exception as e:
            logger.error(f"Error enviando email de verificación: {e}")
            return False

# Instancia global del servicio
_email_service = None

def get_email_service() -> EmailService:
    """Obtiene la instancia del servicio de email"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
