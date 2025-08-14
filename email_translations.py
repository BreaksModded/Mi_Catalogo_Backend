"""
Sistema de traducciones para emails en el backend
"""

EMAIL_TRANSLATIONS = {
    'es': {
        # Password reset emails
        'subject': 'Recuperación de contraseña - Mi Catálogo',
        'title': '🎬 Mi Catálogo',
        'subtitle': 'Recuperación de contraseña',
        'greeting': 'Hola {username}',
        'message': 'Hemos recibido una solicitud para restablecer la contraseña de tu cuenta en Mi Catálogo.',
        'instruction': 'Para crear una nueva contraseña, haz clic en el siguiente enlace:',
        'buttonText': 'Restablecer contraseña',
        'alternativeText': 'Si no puedes hacer clic en el botón, copia y pega el siguiente enlace en tu navegador:',
        'expirationWarning': 'Este enlace expirará en 24 horas por seguridad.',
        'noRequestWarning': 'Si no solicitaste este cambio, puedes ignorar este email. Tu contraseña no será modificada.',
        'thanks': '¡Gracias por usar Mi Catálogo!',
        'footer': 'Este es un email automático, por favor no respondas a este mensaje.',
        
        # Welcome emails
        'welcome_subject': '¡Bienvenido a Mi Catálogo! 🎬',
        'welcome_title': 'Mi Catálogo',
        'welcome_subtitle': '¡Bienvenido a tu nuevo catálogo personal!',
        'welcome_greeting': '¡Hola {username}!',
        'welcome_message': 'Te damos la bienvenida a Mi Catálogo, tu plataforma personal para organizar y gestionar tu colección de películas y series.',
        'welcome_features': 'Con Mi Catálogo podrás:',
        'welcome_feature1': '📽️ Crear tu catálogo personal de películas y series',
        'welcome_feature2': '⭐ Calificar y agregar notas personales a tus títulos',
        'welcome_feature3': '📋 Organizar contenido en listas personalizadas',
        'welcome_feature4': '🏷️ Etiquetar y categorizar tu contenido',
        'welcome_feature5': '📊 Ver estadísticas de tu consumo audiovisual',
        'welcome_button_text': 'Empezar a explorar',
        'welcome_help_text': 'Si tienes alguna pregunta o necesitas ayuda, no dudes en contactarnos.',
        'welcome_thanks': '¡Esperamos que disfrutes de tu experiencia en Mi Catálogo!',
        
        # Verification emails
        'verify_subject': 'Verifica tu cuenta - Mi Catálogo',
        'verify_title': 'Mi Catálogo',
        'verify_subtitle': 'Verificación de cuenta',
        'verify_greeting': 'Hola {username}',
        'verify_message': 'Para completar el registro de tu cuenta en Mi Catálogo, necesitamos verificar tu dirección de email.',
        'verify_instruction': 'Haz clic en el botón de abajo para verificar tu cuenta:',
        'verify_button_text': 'Verificar cuenta',
        'verify_alternative_text': 'Si no puedes hacer clic en el botón, copia y pega el siguiente enlace en tu navegador:',
        'verify_expiration_warning': 'Este enlace de verificación expirará en 7 días.',
        'verify_benefits': 'Al verificar tu cuenta podrás acceder a todas las funcionalidades de la plataforma.',
        'verify_thanks': 'Gracias por unirte a Mi Catálogo',
    },
    'en': {
        # Password reset emails
        'subject': 'Password Recovery - My Catalog',
        'title': '🎬 My Catalog',
        'subtitle': 'Password Recovery',
        'greeting': 'Hello {username}',
        'message': 'We have received a request to reset the password for your My Catalog account.',
        'instruction': 'To create a new password, click on the following link:',
        'buttonText': 'Reset Password',
        'alternativeText': 'If you cannot click the button, copy and paste the following link into your browser:',
        'expirationWarning': 'This link will expire in 24 hours for security.',
        'noRequestWarning': 'If you did not request this change, you can ignore this email. Your password will not be modified.',
        'thanks': 'Thank you for using My Catalog!',
        'footer': 'This is an automated email, please do not reply to this message.',
        
        # Welcome emails
        'welcome_subject': 'Welcome to My Catalog! 🎬',
        'welcome_title': 'My Catalog',
        'welcome_subtitle': 'Welcome to your new personal catalog!',
        'welcome_greeting': 'Hello {username}!',
        'welcome_message': 'Welcome to My Catalog, your personal platform to organize and manage your movie and TV show collection.',
        'welcome_features': 'With My Catalog you can:',
        'welcome_feature1': '📽️ Create your personal catalog of movies and TV shows',
        'welcome_feature2': '⭐ Rate and add personal notes to your titles',
        'welcome_feature3': '📋 Organize content in custom lists',
        'welcome_feature4': '🏷️ Tag and categorize your content',
        'welcome_feature5': '📊 View statistics of your audiovisual consumption',
        'welcome_button_text': 'Start exploring',
        'welcome_help_text': 'If you have any questions or need help, feel free to contact us.',
        'welcome_thanks': 'We hope you enjoy your experience on My Catalog!',
        
        # Verification emails
        'verify_subject': 'Verify your account - My Catalog',
        'verify_title': 'My Catalog',
        'verify_subtitle': 'Account verification',
        'verify_greeting': 'Hello {username}',
        'verify_message': 'To complete your My Catalog account registration, we need to verify your email address.',
        'verify_instruction': 'Click the button below to verify your account:',
        'verify_button_text': 'Verify account',
        'verify_alternative_text': 'If you cannot click the button, copy and paste the following link into your browser:',
        'verify_expiration_warning': 'This verification link will expire in 7 days.',
        'verify_benefits': 'By verifying your account you will be able to access all platform features.',
        'verify_thanks': 'Thank you for joining My Catalog',
    },
    'fr': {
        # Password reset emails
        'subject': 'Récupération de mot de passe - Mon Catalogue',
        'title': '🎬 Mon Catalogue',
        'subtitle': 'Récupération de mot de passe',
        'greeting': 'Bonjour {username}',
        'message': 'Nous avons reçu une demande de réinitialisation du mot de passe de votre compte Mon Catalogue.',
        'instruction': 'Pour créer un nouveau mot de passe, cliquez sur le lien suivant :',
        'buttonText': 'Réinitialiser le mot de passe',
        'alternativeText': 'Si vous ne pouvez pas cliquer sur le bouton, copiez et collez le lien suivant dans votre navigateur :',
        'expirationWarning': 'Ce lien expirera dans 24 heures pour des raisons de sécurité.',
        'noRequestWarning': 'Si vous n\'avez pas demandé ce changement, vous pouvez ignorer cet email. Votre mot de passe ne sera pas modifié.',
        'thanks': 'Merci d\'utiliser Mon Catalogue !',
        'footer': 'Ceci est un email automatique, veuillez ne pas répondre à ce message.',
        
        # Welcome emails
        'welcome_subject': 'Bienvenue sur Mon Catalogue ! 🎬',
        'welcome_title': 'Mon Catalogue',
        'welcome_subtitle': 'Bienvenue dans votre nouveau catalogue personnel !',
        'welcome_greeting': 'Bonjour {username} !',
        'welcome_message': 'Bienvenue sur Mon Catalogue, votre plateforme personnelle pour organiser et gérer votre collection de films et séries.',
        'welcome_features': 'Avec Mon Catalogue vous pouvez :',
        'welcome_feature1': '📽️ Créer votre catalogue personnel de films et séries',
        'welcome_feature2': '⭐ Noter et ajouter des notes personnelles à vos titres',
        'welcome_feature3': '📋 Organiser le contenu dans des listes personnalisées',
        'welcome_feature4': '🏷️ Étiqueter et catégoriser votre contenu',
        'welcome_feature5': '📊 Voir les statistiques de votre consommation audiovisuelle',
        'welcome_button_text': 'Commencer à explorer',
        'welcome_help_text': 'Si vous avez des questions ou besoin d\'aide, n\'hésitez pas à nous contacter.',
        'welcome_thanks': 'Nous espérons que vous apprécierez votre expérience sur Mon Catalogue !',
        
        # Verification emails
        'verify_subject': 'Vérifiez votre compte - Mon Catalogue',
        'verify_title': 'Mon Catalogue',
        'verify_subtitle': 'Vérification de compte',
        'verify_greeting': 'Bonjour {username}',
        'verify_message': 'Pour compléter l\'inscription de votre compte Mon Catalogue, nous devons vérifier votre adresse email.',
        'verify_instruction': 'Cliquez sur le bouton ci-dessous pour vérifier votre compte :',
        'verify_button_text': 'Vérifier le compte',
        'verify_alternative_text': 'Si vous ne pouvez pas cliquer sur le bouton, copiez et collez le lien suivant dans votre navigateur :',
        'verify_expiration_warning': 'Ce lien de vérification expirera dans 7 jours.',
        'verify_benefits': 'En vérifiant votre compte, vous pourrez accéder à toutes les fonctionnalités de la plateforme.',
        'verify_thanks': 'Merci de rejoindre Mon Catalogue',
    },
    'pt': {
        # Password reset emails
        'subject': 'Recuperação de senha - Meu Catálogo',
        'title': '🎬 Meu Catálogo',
        'subtitle': 'Recuperação de senha',
        'greeting': 'Olá {username}',
        'message': 'Recebemos uma solicitação para redefinir a senha da sua conta no Meu Catálogo.',
        'instruction': 'Para criar uma nova senha, clique no link a seguir:',
        'buttonText': 'Redefinir senha',
        'alternativeText': 'Se você não consegue clicar no botão, copie e cole o seguinte link no seu navegador:',
        'expirationWarning': 'Este link expirará em 24 horas por segurança.',
        'noRequestWarning': 'Se você não solicitou esta alteração, pode ignorar este email. Sua senha não será modificada.',
        'thanks': 'Obrigado por usar o Meu Catálogo!',
        'footer': 'Este é um email automático, por favor não responda a esta mensagem.',
        
        # Welcome emails
        'welcome_subject': 'Bem-vindo ao Meu Catálogo! 🎬',
        'welcome_title': 'Meu Catálogo',
        'welcome_subtitle': 'Bem-vindo ao seu novo catálogo pessoal!',
        'welcome_greeting': 'Olá {username}!',
        'welcome_message': 'Bem-vindo ao Meu Catálogo, sua plataforma pessoal para organizar e gerenciar sua coleção de filmes e séries.',
        'welcome_features': 'Com o Meu Catálogo você pode:',
        'welcome_feature1': '📽️ Criar seu catálogo pessoal de filmes e séries',
        'welcome_feature2': '⭐ Avaliar e adicionar notas pessoais aos seus títulos',
        'welcome_feature3': '📋 Organizar conteúdo em listas personalizadas',
        'welcome_feature4': '🏷️ Etiquetar e categorizar seu conteúdo',
        'welcome_feature5': '📊 Ver estatísticas do seu consumo audiovisual',
        'welcome_button_text': 'Começar a explorar',
        'welcome_help_text': 'Se tiver alguma dúvida ou precisar de ajuda, não hesite em nos contatar.',
        'welcome_thanks': 'Esperamos que você aproveite sua experiência no Meu Catálogo!',
        
        # Verification emails
        'verify_subject': 'Verifique sua conta - Meu Catálogo',
        'verify_title': 'Meu Catálogo',
        'verify_subtitle': 'Verificação de conta',
        'verify_greeting': 'Olá {username}',
        'verify_message': 'Para completar o registro da sua conta no Meu Catálogo, precisamos verificar seu endereço de email.',
        'verify_instruction': 'Clique no botão abaixo para verificar sua conta:',
        'verify_button_text': 'Verificar conta',
        'verify_alternative_text': 'Se não conseguir clicar no botão, copie e cole o seguinte link no seu navegador:',
        'verify_expiration_warning': 'Este link de verificação expirará em 7 dias.',
        'verify_benefits': 'Ao verificar sua conta, você poderá acessar todas as funcionalidades da plataforma.',
        'verify_thanks': 'Obrigado por se juntar ao Meu Catálogo',
    },
    'de': {
        'subject': 'Passwort-Wiederherstellung - Mein Katalog',
        'title': '🎬 Mein Katalog',
        'subtitle': 'Passwort-Wiederherstellung',
        'greeting': 'Hallo {username}',
        'message': 'Wir haben eine Anfrage zur Zurücksetzung des Passworts für Ihr Mein Katalog-Konto erhalten.',
        'instruction': 'Um ein neues Passwort zu erstellen, klicken Sie auf den folgenden Link:',
        'buttonText': 'Passwort zurücksetzen',
        'alternativeText': 'Wenn Sie nicht auf die Schaltfläche klicken können, kopieren Sie den folgenden Link und fügen Sie ihn in Ihren Browser ein:',
        'expirationWarning': 'Dieser Link läuft aus Sicherheitsgründen in 24 Stunden ab.',
        'noRequestWarning': 'Wenn Sie diese Änderung nicht angefordert haben, können Sie diese E-Mail ignorieren. Ihr Passwort wird nicht geändert.',
        'thanks': 'Vielen Dank, dass Sie Mein Katalog verwenden!',
        'footer': 'Dies ist eine automatische E-Mail, bitte antworten Sie nicht auf diese Nachricht.',
    }
}

def get_email_translation(language: str, key: str, **kwargs) -> str:
    """
    Obtiene una traducción para emails
    """
    # Usar español como fallback si el idioma no está disponible
    lang = language if language in EMAIL_TRANSLATIONS else 'es'
    
    # Obtener el texto
    text = EMAIL_TRANSLATIONS[lang].get(key, EMAIL_TRANSLATIONS['es'].get(key, ''))
    
    # Aplicar formato si hay variables
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            # Si hay error de formato, devolver el texto sin formatear
            pass
    
    return text
