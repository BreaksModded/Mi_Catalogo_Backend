import unicodedata

# Normalize text: lowercase, strip, remove diacritics
def normalize_text(s: str) -> str:
    if not s:
        return ''
    s = s.strip().lower()
    # remove accents
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

# Canonical mapping: keys are normalized (ascii, lowercase) and map to a consistent Spanish display name
GENRE_MAPPING = {
    # Acción
    'accion': 'Acción',
    'action': 'Acción',
    'acao': 'Acción',            # pt
    'azione': 'Acción',          # it (por si aparece)

    # Aventura
    'aventura': 'Aventura',
    'adventure': 'Aventura',
    'abenteuer': 'Aventura',     # de
    'aventure': 'Aventura',      # fr

    # Comedia
    'comedia': 'Comedia',
    'comedy': 'Comedia',
    'comedie': 'Comedia',
    'komodie': 'Comedia',
    'comedia romantica': 'Romance',  # a veces viene así
    'romantic comedy': 'Romance',
    'romcom': 'Romance',
    'comedia dramatica': 'Drama',

    # Drama
    'drama': 'Drama',
    'drame': 'Drama',
    'drama criminal': 'Drama',

    # Terror
    'terror': 'Terror',
    'horror': 'Terror',
    'horreur': 'Terror',
    'schocker': 'Terror',        # de (coloquial)

    # Thriller / Suspense
    'thriller': 'Thriller',
    'suspense': 'Thriller',
    'suspenso': 'Thriller',
    'suspense thriller': 'Thriller',
    'psychological thriller': 'Thriller',

    # Ciencia ficción
    'ciencia ficcion': 'Ciencia ficción',
    'science fiction': 'Ciencia ficción',
    'sci-fi': 'Ciencia ficción',
    'science-fiction': 'Ciencia ficción',
    'ficcao cientifica': 'Ciencia ficción',  # pt
    'sciencefiction': 'Ciencia ficción',     # de (junto)

    # Fantasía
    'fantasia': 'Fantasía',
    'fantasy': 'Fantasía',
    'fantaisie': 'Fantasía',
    'fantasie': 'Fantasía',
    'fantastique': 'Fantasía',   # fr

    # Romance
    'romance': 'Romance',
    'romantica': 'Romance',
    'romantic': 'Romance',
    'romantique': 'Romance',
    'romantik': 'Romance',
    'liebesfilm': 'Romance',     # de
    'amor': 'Romance',           # es/pt

    # Animación
    'animacion': 'Animación',
    'animación': 'Animación',  # por si está guardado así
    'animation': 'Animación',
    'anime': 'Animación',
    'animacao': 'Animación',     # pt
    'zeichentrick': 'Animación', # de (dibujo animado)
    'cartoon': 'Animación',

    # Documental
    'documental': 'Documental',
    'documentary': 'Documental',
    'documentaire': 'Documental',
    'dokumentar': 'Documental',
    'dokumentation': 'Documental',  # de
    'documentario': 'Documental',   # pt

    # Crimen
    'crimen': 'Crimen',
    'crime': 'Crimen',
    'criminal': 'Crimen',
    'krimi': 'Crimen',           # de
    'policial': 'Policial',      # ya cubierto abajo pero común como género

    # Misterio
    'misterio': 'Misterio',
    'mystery': 'Misterio',
    'mystere': 'Misterio',
    'mysterium': 'Misterio',
    'enigme': 'Misterio',        # fr
    'geheimnis': 'Misterio',     # de

    # Guerra / Bélica
    'guerra': 'Guerra',
    'war': 'Guerra',
    'guerre': 'Guerra',
    'krieg': 'Guerra',
    'belica': 'Guerra',
    'war film': 'Guerra',
    'belico': 'Guerra',

    # Western
    'western': 'Western',
    'oeste': 'Western',
    'faroeste': 'Western',       # pt

    # Musical
    'musical': 'Musical',
    'musique': 'Musical',
    'musik': 'Musical',

    # Biografía
    'biografia': 'Biografía',
    'biography': 'Biografía',
    'biographie': 'Biografía',
    'biografie': 'Biografía',
    'biographical': 'Biografía',
    'biopic': 'Biografía',

    # Historia
    'historia': 'Historia',
    'history': 'Historia',
    'histoire': 'Historia',
    'geschichte': 'Historia',
    'historical': 'Historia',
    'historico': 'Historia',
    'historico': 'Historia',     # pt/es sin acento

    # Familia
    'familia': 'Familia',
    'family': 'Familia',
    'famille': 'Familia',
    'familie': 'Familia',
    'familiar': 'Familia',
    'familienfilm': 'Familia',   # de

    # Deporte
    'deporte': 'Deporte',
    'sport': 'Deporte',
    'sports': 'Deporte',
    'deportes': 'Deporte',
    'esporte': 'Deporte',        # pt

    # Música
    'musica': 'Música',
    'music': 'Música',
    'musique': 'Música',         # fr (también como música, arriba ya Musical)

    # Otros comunes
    'superhero': 'Superhéroes',
    'superheroe': 'Superhéroes',
    'superheroes': 'Superhéroes',
    'superheroi': 'Superhéroes', # pt
    'superheld': 'Superhéroes',  # de singular
    'superhelden': 'Superhéroes',# de plural
    'neo-noir': 'Neo-noir',
    'noir': 'Noir',
    'film noir': 'Noir',
    'cine negro': 'Noir',
    'psychological': 'Psicológico',
    'psicologico': 'Psicológico',
    'politico': 'Político',
    'political': 'Político',
    'politik': 'Político',       # de
    'politique': 'Político',     # fr
    'satirico': 'Sátira',
    'satire': 'Sátira',
    'espionaje': 'Espionaje',
    'spy': 'Espionaje',
    'espionagem': 'Espionaje',   # pt
    'spionage': 'Espionaje',     # de
    'policiaco': 'Policial',
    'police': 'Policial',
    'policier': 'Policial',      # fr
    'heist': 'Atracos',
    'atraco': 'Atracos',
    'assalto': 'Atracos',        # pt
    'braquage': 'Atracos',       # fr
    'raub': 'Atracos',           # de
    'road movie': 'Road Movie',
    'roadmovie': 'Road Movie',   # de
    'road-movie': 'Road Movie',  # fr
    'coming of age': 'Coming of Age',
    'slice of life': 'Slice of Life',

    # TV y formatos
    'tv movie': 'Película de TV',
    'telefilm': 'Película de TV',
    'telefilme': 'Película de TV',    # pt
    'television film': 'Película de TV',
    'film tv': 'Película de TV',
    'téléfilm': 'Película de TV',

    'news': 'Noticias',
    'noticias': 'Noticias',
    'nachrichten': 'Noticias',       # de
    'actualites': 'Noticias',        # fr (actualités)
    'journal': 'Noticias',           # fr

    'talk': 'Talk Show',
    'talk show': 'Talk Show',
    'talk-show': 'Talk Show',
    'entrevistas': 'Talk Show',
    'debate': 'Talk Show',
    'spielshow': 'Concurso',         # de game show
    'game show': 'Concurso',
    'gameshow': 'Concurso',
    'concurso': 'Concurso',
    'quiz': 'Concurso',
    'jeu televise': 'Concurso',      # fr (jeu télévisé)
    'jeu tv': 'Concurso',

    'reality': 'Reality',
    'reality tv': 'Reality',
    'telerrealidad': 'Reality',
    'telerealidade': 'Reality',      # pt
    'telerrealite': 'Reality',       # fr (téléréalité)
    'realityshow': 'Reality',
    'reality-show': 'Reality',

    'soap': 'Telenovela',
    'soap opera': 'Telenovela',
    'telenovela': 'Telenovela',
    'culebron': 'Telenovela',
    'feuilleton': 'Telenovela',      # fr
    'seifenoper': 'Telenovela',      # de

    'kids': 'Infantil',
    'children': 'Infantil',
    'ninos': 'Infantil',
    'enfants': 'Infantil',           # fr
    'kinder': 'Infantil',            # de
    'infantil': 'Infantil',

    # Combinados TMDb
    'accion y aventura': 'Acción y Aventura',
    'action & adventure': 'Acción y Aventura',
    'action and adventure': 'Acción y Aventura',
    'acao e aventura': 'Acción y Aventura',
    'action und abenteuer': 'Acción y Aventura',
    'action abenteuer': 'Acción y Aventura',

    'sci-fi & fantasy': 'Ciencia ficción y Fantasía',
    'sci fi & fantasy': 'Ciencia ficción y Fantasía',
    'science fiction & fantasy': 'Ciencia ficción y Fantasía',
    'ficcao cientifica e fantasia': 'Ciencia ficción y Fantasía',
    'science-fiction & fantasy': 'Ciencia ficción y Fantasía',
    'science fiction et fantastique': 'Ciencia ficción y Fantasía',

    'war & politics': 'Guerra y política',
    'war and politics': 'Guerra y política',
    'guerra y politica': 'Guerra y política',
    'guerra e politica': 'Guerra y política',
    'guerre et politique': 'Guerra y política',
    'krieg und politik': 'Guerra y política',

    # Cortos / otros
    'cortometraje': 'Cortometraje',
    'corto': 'Cortometraje',
    'short': 'Cortometraje',
    'short film': 'Cortometraje',

    'erotico': 'Erótico',
    'erotica': 'Erótico',
    'erotique': 'Erótico',
    'erotic': 'Erótico',
}

def get_consistent_name(term: str) -> str:
    key = normalize_text(term)
    return GENRE_MAPPING.get(key)


def get_variants_for_input(term: str) -> list[str]:
    """Return a list of genre substrings to filter by when client asks for `term`.
    Includes canonical display name (with accents) plus all known synonyms from the mapping.
    """
    if not term:
        return []
    key = normalize_text(term)
    consistent = GENRE_MAPPING.get(key)

    variants = set()
    if consistent:
        # Include canonical display label (with accents), and its ascii-folded version
        variants.add(consistent)
        variants.add(normalize_text(consistent))
        # Include all keys (normalized) that map to the same consistent label
        for k, v in GENRE_MAPPING.items():
            if v == consistent:
                variants.add(k)
    else:
        # Fallback: use both the raw term and its normalized variant
        variants.add(term)
        variants.add(key)

    # Return as list preserving no particular order
    return list(variants)
