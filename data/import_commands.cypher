// ============================================
// Neo4j 数据导入命令
// ============================================

// 1. 清空现有数据（可选）
MATCH (n) DETACH DELETE n;

// 2. 创建约束和索引
CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.personId IS UNIQUE;
CREATE CONSTRAINT place_id IF NOT EXISTS FOR (l:Place) REQUIRE l.placeId IS UNIQUE;
CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.eventId IS UNIQUE;
CREATE CONSTRAINT time_id IF NOT EXISTS FOR (t:TimeAnchor) REQUIRE t.timeId IS UNIQUE;

CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.name);
CREATE INDEX place_name IF NOT EXISTS FOR (l:Place) ON (l.name);
CREATE INDEX event_name IF NOT EXISTS FOR (e:Event) ON (e.name);
CREATE INDEX time_normalized IF NOT EXISTS FOR (t:TimeAnchor) ON (t.normalized);

// 3. 导入节点
// 注意：需要将CSV文件放在Neo4j的import目录下
// 或者使用file:///绝对路径

// 导入人物节点
LOAD CSV WITH HEADERS FROM 'file:///nodes/Person.csv' AS row
CREATE (:Person {
  personId: row.`personId:ID`,
  name: row.name,
  aliases: CASE row.`aliases:string[]` WHEN '' THEN [] ELSE split(row.`aliases:string[]`, '|') END,
  roles: CASE row.`roles:string[]` WHEN '' THEN [] ELSE split(row.`roles:string[]`, '|') END,
  offices: CASE row.`offices:string[]` WHEN '' THEN [] ELSE split(row.`offices:string[]`, '|') END,
  evidence: CASE row.`evidence:string[]` WHEN '' THEN [] ELSE split(row.`evidence:string[]`, '|') END
});

// 导入地点节点
LOAD CSV WITH HEADERS FROM 'file:///nodes/Place.csv' AS row
CREATE (:Place {
  placeId: row.`placeId:ID`,
  name: row.name,
  aliases: CASE row.`aliases:string[]` WHEN '' THEN [] ELSE split(row.`aliases:string[]`, '|') END,
  place_type: row.place_type,
  evidence: CASE row.`evidence:string[]` WHEN '' THEN [] ELSE split(row.`evidence:string[]`, '|') END
});

// 导入事件节点
LOAD CSV WITH HEADERS FROM 'file:///nodes/Event.csv' AS row
CREATE (:Event {
  eventId: row.`eventId:ID`,
  name: row.name,
  event_type: row.event_type,
  time: row.time,
  place: row.place,
  participants: CASE row.`participants:string[]` WHEN '' THEN [] ELSE split(row.`participants:string[]`, '|') END,
  description: row.description,
  outcomes: CASE row.`outcomes:string[]` WHEN '' THEN [] ELSE split(row.`outcomes:string[]`, '|') END,
  evidence: CASE row.`evidence:string[]` WHEN '' THEN [] ELSE split(row.`evidence:string[]`, '|') END,
  confidence: toFloat(row.`confidence:float`)
});

// 导入时间锚点节点
LOAD CSV WITH HEADERS FROM 'file:///nodes/TimeAnchor.csv' AS row
CREATE (:TimeAnchor {
  timeId: row.`timeId:ID`,
  text: row.text,
  normalized: row.normalized,
  evidence: row.evidence,
  confidence: toFloat(row.`confidence:float`)
});

// 4. 导入关系
// 导入关系边，根据实际生成的CSV文件调整

// 导入 PERSON_EVENT 关系
LOAD CSV WITH HEADERS FROM 'file:///edges/PERSON_EVENT.csv' AS row
MATCH (a {[row.`:START_ID`]: row.`:START_ID`})
MATCH (b {[row.`:END_ID`]: row.`:END_ID`})
CREATE (a)-[r:PERSON_EVENT]->(b)
SET r.relation = row.relation,
    r.time = row.time,
    r.place = row.place,
    r.evidence = row.evidence,
    r.confidence = toFloat(row.`confidence:float`);

// 导入 PERSON_PLACE 关系
LOAD CSV WITH HEADERS FROM 'file:///edges/PERSON_PLACE.csv' AS row
MATCH (a {[row.`:START_ID`]: row.`:START_ID`})
MATCH (b {[row.`:END_ID`]: row.`:END_ID`})
CREATE (a)-[r:PERSON_PLACE]->(b)
SET r.relation = row.relation,
    r.time = row.time,
    r.place = row.place,
    r.evidence = row.evidence,
    r.confidence = toFloat(row.`confidence:float`);

// 导入 PERSON_OFFICE 关系
LOAD CSV WITH HEADERS FROM 'file:///edges/PERSON_OFFICE.csv' AS row
MATCH (a {[row.`:START_ID`]: row.`:START_ID`})
MATCH (b {[row.`:END_ID`]: row.`:END_ID`})
CREATE (a)-[r:PERSON_OFFICE]->(b)
SET r.relation = row.relation,
    r.time = row.time,
    r.place = row.place,
    r.evidence = row.evidence,
    r.confidence = toFloat(row.`confidence:float`);

// 导入 PERSON_PARTICIPATES_EVENT 关系
LOAD CSV WITH HEADERS FROM 'file:///edges/PERSON_PARTICIPATES_EVENT.csv' AS row
MATCH (a {[row.`:START_ID`]: row.`:START_ID`})
MATCH (b {[row.`:END_ID`]: row.`:END_ID`})
CREATE (a)-[r:PERSON_PARTICIPATES_EVENT]->(b)
SET r.relation = row.relation,
    r.confidence = toFloat(row.`confidence:float`);

// 导入 EVENT_LOCATED_AT 关系
LOAD CSV WITH HEADERS FROM 'file:///edges/EVENT_LOCATED_AT.csv' AS row
MATCH (a {[row.`:START_ID`]: row.`:START_ID`})
MATCH (b {[row.`:END_ID`]: row.`:END_ID`})
CREATE (a)-[r:EVENT_LOCATED_AT]->(b)
SET r.relation = row.relation,
    r.confidence = toFloat(row.`confidence:float`);

// 导入 PERSON_PERSON 关系
LOAD CSV WITH HEADERS FROM 'file:///edges/PERSON_PERSON.csv' AS row
MATCH (a {[row.`:START_ID`]: row.`:START_ID`})
MATCH (b {[row.`:END_ID`]: row.`:END_ID`})
CREATE (a)-[r:PERSON_PERSON]->(b)
SET r.relation = row.relation,
    r.time = row.time,
    r.place = row.place,
    r.evidence = row.evidence,
    r.confidence = toFloat(row.`confidence:float`);

// 导入 EVENT_OCCURS_AT 关系
LOAD CSV WITH HEADERS FROM 'file:///edges/EVENT_OCCURS_AT.csv' AS row
MATCH (a {[row.`:START_ID`]: row.`:START_ID`})
MATCH (b {[row.`:END_ID`]: row.`:END_ID`})
CREATE (a)-[r:EVENT_OCCURS_AT]->(b)
SET r.relation = row.relation,
    r.confidence = toFloat(row.`confidence:float`);

// 5. 验证导入
MATCH (n) RETURN labels(n) as label, count(*) as count;
MATCH ()-[r]->() RETURN type(r) as relationship, count(*) as count;
