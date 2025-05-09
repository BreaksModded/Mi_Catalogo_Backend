-- Índices recomendados para acelerar filtros y búsquedas frecuentes
CREATE INDEX IF NOT EXISTS idx_media_tipo ON media (tipo);
CREATE INDEX IF NOT EXISTS idx_media_pendiente ON media (pendiente);
CREATE INDEX IF NOT EXISTS idx_media_favorito ON media (favorito);
CREATE INDEX IF NOT EXISTS idx_media_genero ON media (genero);
CREATE INDEX IF NOT EXISTS idx_media_anio ON media (anio);
CREATE INDEX IF NOT EXISTS idx_media_nota_imdb ON media (nota_imdb);
CREATE INDEX IF NOT EXISTS idx_media_nota_personal ON media (nota_personal);
-- Puedes ejecutar este script en tu base de datos PostgreSQL para mejorar el rendimiento de los filtros.
