CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    article_id VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    link TEXT,
    content TEXT,
    pub_date DATE,
    source VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_time_ms FLOAT
);

CREATE INDEX idx_articles_date ON articles(pub_date);
CREATE INDEX idx_articles_source ON articles(source);


-- ============================================================================
-- ТАБЛИЦА СУЩНОСТЕЙ (entities)
-- ============================================================================

CREATE TABLE IF NOT EXISTS entities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,  -- 'person', 'organization', 'position', 'location', 'date', 'event'
    confidence FLOAT,
    source_method VARCHAR(50),  -- 'regex', 'xlm-roberta', etc
    context TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, entity_type)
);

CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_name ON entities(name);


-- ============================================================================
-- ТАБЛИЦА УПОМИНАНИЙ (entity_mentions)
-- ============================================================================

CREATE TABLE IF NOT EXISTS entity_mentions (
    id SERIAL PRIMARY KEY,
    article_id INT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    entity_id INT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    mention_position INT,  -- позиция в тексте
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_mentions_article ON entity_mentions(article_id);
CREATE INDEX idx_mentions_entity ON entity_mentions(entity_id);


-- ============================================================================
-- ТАБЛИЦА СВЯЗЕЙ МЕЖДУ СУЩНОСТЯМИ (relationships)
-- ============================================================================

CREATE TABLE IF NOT EXISTS relationships (
    id SERIAL PRIMARY KEY,
    article_id INT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    source_entity_id INT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_entity_id INT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation_type VARCHAR(50) NOT NULL,  -- 'works_for', 'owns', 'manages', 'competed_with', etc
    confidence FLOAT,
    evidence TEXT,  -- текст, подтверждающий связь
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_relationships_article ON relationships(article_id);
CREATE INDEX idx_relationships_source ON relationships(source_entity_id);
CREATE INDEX idx_relationships_target ON relationships(target_entity_id);
CREATE INDEX idx_relationships_type ON relationships(relation_type);


-- ============================================================================
-- ТАБЛИЦА СОБЫТИЙ (events)
-- ============================================================================

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    article_id INT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,  -- 'appointment', 'resignation', 'legal_proceeding', 'sanction', etc
    description TEXT,
    event_date DATE,
    location VARCHAR(255),
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_article ON events(article_id);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_date ON events(event_date);


-- ============================================================================
-- ТАБЛИЦА УЧАСТНИКОВ СОБЫТИЙ (event_participants)
-- ============================================================================

CREATE TABLE IF NOT EXISTS event_participants (
    id SERIAL PRIMARY KEY,
    event_id INT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entity_id INT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_participants_event ON event_participants(event_id);
CREATE INDEX idx_participants_entity ON event_participants(entity_id);


-- ============================================================================
-- ТАБЛИЦА РИСКОВ (risks)
-- ============================================================================

CREATE TABLE IF NOT EXISTS risks (
    id SERIAL PRIMARY KEY,
    article_id INT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    risk_type VARCHAR(50) NOT NULL,  -- 'corruption', 'sanctions', 'bankruptcy', etc
    confidence FLOAT,
    keyword_matches INT,
    total_mentions INT,
    keywords TEXT,  -- JSON массив
    risk_level VARCHAR(20),  -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'NO_RISK'
    risk_flags TEXT,  -- JSON массив
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_risks_article ON risks(article_id);
CREATE INDEX idx_risks_type ON risks(risk_type);
CREATE INDEX idx_risks_level ON risks(risk_level);


-- ============================================================================
-- ТАБЛИЦА ОБЩИХ РЕЗУЛЬТАТОВ (article_results)
-- ============================================================================

CREATE TABLE IF NOT EXISTS article_results (
    id SERIAL PRIMARY KEY,
    article_id INT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    overall_risk_score FLOAT,
    risk_level VARCHAR(20),
    persons_count INT,
    organizations_count INT,
    locations_count INT,
    events_count INT,
    relationships_count INT,
    top_risks TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_results_article ON article_results(article_id);
CREATE INDEX idx_results_risk_level ON article_results(risk_level);


-- ============================================================================
-- ПРЕДСТАВЛЕНИЯ (VIEWS) ДЛЯ УДОБНОГО ЗАПРОСА ДАННЫХ
-- ============================================================================

-- Статьи с общей информацией о рисках
CREATE OR REPLACE VIEW v_articles_with_risks AS
SELECT 
    a.id,
    a.article_id,
    a.title,
    a.pub_date,
    a.source,
    ar.overall_risk_score,
    ar.risk_level,
    ar.persons_count,
    ar.organizations_count,
    ar.relationships_count,
    COUNT(DISTINCT r.id) as risk_types_found
FROM articles a
LEFT JOIN article_results ar ON a.id = ar.article_id
LEFT JOIN risks r ON a.id = r.article_id
GROUP BY a.id, ar.id;

-- Персоны, связанные с высокими рисками
CREATE OR REPLACE VIEW v_high_risk_persons AS
SELECT 
    e.name,
    COUNT(DISTINCT a.id) as article_count,
    COUNT(DISTINCT rel.id) as relationship_count,
    MAX(ar.overall_risk_score) as max_risk_score,
    STRING_AGG(DISTINCT ar.risk_level, ', ') as risk_levels
FROM entities e
JOIN entity_mentions em ON e.id = em.entity_id
JOIN articles a ON em.article_id = a.id
JOIN article_results ar ON a.id = ar.article_id
LEFT JOIN relationships rel ON (
    (rel.source_entity_id = e.id OR rel.target_entity_id = e.id)
    AND rel.article_id = a.id
)
WHERE e.entity_type = 'person'
    AND ar.overall_risk_score > 0.5
GROUP BY e.id, e.name
ORDER BY max_risk_score DESC;

-- Организации, связанные с санкциями
CREATE OR REPLACE VIEW v_sanctioned_organizations AS
SELECT 
    e.name,
    COUNT(DISTINCT a.id) as sanction_articles,
    COUNT(DISTINCT r.id) as sanction_mentions,
    MAX(ar.overall_risk_score) as max_risk_score,
    STRING_AGG(DISTINCT a.source, ', ') as sources
FROM entities e
JOIN entity_mentions em ON e.id = em.entity_id
JOIN articles a ON em.article_id = a.id
JOIN article_results ar ON a.id = ar.article_id
JOIN risks r ON a.id = r.article_id
WHERE e.entity_type = 'organization'
    AND r.risk_type = 'sanctions'
GROUP BY e.id, e.name
ORDER BY sanction_mentions DESC;

-- Сетевой граф: кто с кем связан
CREATE OR REPLACE VIEW v_relationship_network AS
SELECT 
    se.name as source_name,
    se.entity_type as source_type,
    te.name as target_name,
    te.entity_type as target_type,
    rel.relation_type,
    COUNT(rel.id) as relationship_count,
    AVG(rel.confidence) as avg_confidence,
    COUNT(DISTINCT rel.article_id) as article_count
FROM relationships rel
JOIN entities se ON rel.source_entity_id = se.id
JOIN entities te ON rel.target_entity_id = te.id
GROUP BY se.id, te.id, rel.relation_type;


-- ============================================================================
-- ПРИМЕРЫ ЗАПРОСОВ
-- ============================================================================

/*

-- 1. Статьи с критическим уровнем риска
SELECT * FROM v_articles_with_risks 
WHERE risk_level = 'CRITICAL'
ORDER BY overall_risk_score DESC;

-- 2. Все персоны, упоминаемые в высокорисковых статьях
SELECT DISTINCT e.name, COUNT(em.id) as mentions
FROM entities e
JOIN entity_mentions em ON e.id = em.entity_id
JOIN articles a ON em.article_id = a.id
JOIN article_results ar ON a.id = ar.article_id
WHERE e.entity_type = 'person'
  AND ar.risk_level IN ('HIGH', 'CRITICAL')
GROUP BY e.id
ORDER BY mentions DESC;

-- 3. Все организации, попавшие под санкции
SELECT * FROM v_sanctioned_organizations;

-- 4. Высокорисковые персоны
SELECT * FROM v_high_risk_persons;

-- 5. Сетевой граф активных компаний
SELECT * FROM v_relationship_network
WHERE source_type = 'organization' 
  AND target_type = 'organization'
ORDER BY relationship_count DESC;

-- 6. Типы рисков в статьях за последний месяц
SELECT risk_type, COUNT(*) as count, AVG(confidence) as avg_confidence
FROM risks r
JOIN articles a ON r.article_id = a.id
WHERE a.pub_date >= CURRENT_DATE - INTERVAL '1 month'
GROUP BY risk_type
ORDER BY count DESC;

-- 7. События с участниками
SELECT ev.event_type, e.name, ev.event_date
FROM events ev
JOIN event_participants ep ON ev.id = ep.event_id
JOIN entities e ON ep.entity_id = e.id
ORDER BY ev.event_date DESC;

-- 8. Граф: кто управляет кем
SELECT * FROM v_relationship_network
WHERE relation_type = 'works_for'
ORDER BY relationship_count DESC;

-- 9. Статистика по источникам
SELECT a.source, COUNT(*) as articles, AVG(ar.overall_risk_score) as avg_risk
FROM articles a
LEFT JOIN article_results ar ON a.id = ar.article_id
GROUP BY a.source
ORDER BY avg_risk DESC;

-- 10. Самые часто упоминаемые организации
SELECT e.name, COUNT(em.id) as mentions, e.entity_type
FROM entities e
JOIN entity_mentions em ON e.id = em.entity_id
WHERE e.entity_type IN ('organization', 'person')
GROUP BY e.id
ORDER BY mentions DESC
LIMIT 20;

*/

-- ============================================================================
-- ОЧИСТКА (для удаления всех таблиц, если нужно)
-- ============================================================================

/*
DROP VIEW IF EXISTS v_relationship_network CASCADE;
DROP VIEW IF EXISTS v_sanctioned_organizations CASCADE;
DROP VIEW IF EXISTS v_high_risk_persons CASCADE;
DROP VIEW IF EXISTS v_articles_with_risks CASCADE;
DROP TABLE IF EXISTS event_participants CASCADE;
DROP TABLE IF EXISTS events CASCADE;
DROP TABLE IF EXISTS risks CASCADE;
DROP TABLE IF EXISTS relationships CASCADE;
DROP TABLE IF EXISTS entity_mentions CASCADE;
DROP TABLE IF EXISTS entities CASCADE;
DROP TABLE IF EXISTS article_results CASCADE;
DROP TABLE IF EXISTS articles CASCADE;
*/
