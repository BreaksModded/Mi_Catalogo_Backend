require('dotenv').config();
const { Pool } = require('pg');

// Configuración de conexión
const pool = new Pool({
  connectionString: "postgresql://media_0t7l_user:DAOS1Key0XhoQAd8G2DUcnWYjk4A0TF9@dpg-d0dku715pdvs739a5520-a.frankfurt-postgres.render.com/media_0t7l?ssl=true"
});

// Función para ejecutar consultas
async function query(text, params) {
  const client = await pool.connect();
  try {
    const res = await client.query(text, params);
    return res.rows;
  } finally {
    client.release();
  }
}

// Función principal
async function analyzeDatabase() {
  try {
    console.log('🔍 Analizando la estructura de la base de datos...\n');

    // 1. Obtener lista de tablas
    console.log('📋 TABLAS EN LA BASE DE DATOS:');
    const tables = await query(`
      SELECT table_name 
      FROM information_schema.tables 
      WHERE table_schema = 'public' 
      ORDER BY table_name
    `);
    
    const tableNames = tables.map(t => t.table_name);
    console.log(tableNames.map(name => `- ${name}`).join('\n'));
    console.log('');

    // 2. Para cada tabla, obtener su estructura
    for (const table of tableNames) {
      console.log(`📊 ESTRUCTURA DE LA TABLA: ${table.toUpperCase()}`);
      
      // Obtener columnas
      const columns = await query(`
        SELECT 
          column_name, 
          data_type, 
          is_nullable, 
          column_default
        FROM information_schema.columns
        WHERE table_name = $1
        ORDER BY ordinal_position
      `, [table]);

      console.log('Columnas:');
      console.table(columns);

      // Obtener índices
      const indexes = await query(`
        SELECT 
          indexname, 
          indexdef 
        FROM pg_indexes 
        WHERE tablename = $1
      `, [table]);

      if (indexes.length > 0) {
        console.log('\nÍndices:');
        console.table(indexes);
      }

      // Obtener claves foráneas
      const foreignKeys = await query(`
        SELECT
          tc.constraint_name,
          kcu.column_name, 
          ccu.table_name AS foreign_table_name,
          ccu.column_name AS foreign_column_name 
        FROM 
          information_schema.table_constraints AS tc 
          JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
          JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE 
          tc.table_name = $1
          AND tc.constraint_type = 'FOREIGN KEY'
      `, [table]);

      if (foreignKeys.length > 0) {
        console.log('\nClaves foráneas:');
        console.table(foreignKeys);
      }

      console.log('\n' + '='.repeat(80) + '\n');
    }

    // 3. Obtener información general de la base de datos
    console.log('📈 ESTADÍSTICAS DE LA BASE DE DATOS:');
    
    const dbStats = await query(`
      SELECT 
        (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public') as total_tables,
        (SELECT count(*) FROM information_schema.views WHERE table_schema = 'public') as total_views,
        (SELECT count(*) FROM information_schema.routines WHERE routine_schema = 'public') as total_functions
    `);
    
    console.table(dbStats);

    console.log('\n✅ Análisis completado con éxito!');

  } catch (error) {
    console.error('❌ Error al analizar la base de datos:', error);
  } finally {
    await pool.end();
    process.exit(0);
  }
}

// Ejecutar el análisis
analyzeDatabase();
