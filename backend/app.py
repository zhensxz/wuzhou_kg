#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
武周-唐初知识图谱 - Flask后端API
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from neo4j import GraphDatabase
import os
from pathlib import Path

app = Flask(__name__)
CORS(app)

def load_config():
    """加载Neo4j配置"""
    config = {
        'uri': os.environ.get('NEO4J_URI'),
        'username': os.environ.get('NEO4J_USERNAME', 'neo4j'),
        'password': os.environ.get('NEO4J_PASSWORD'),
        'database': os.environ.get('NEO4J_DATABASE', 'neo4j')
    }
    
    # 从配置文件读取
    config_file = Path(__file__).parent.parent / 'config' / 'neo4j_config.txt'
    if not config['uri'] and config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip().lower()] = value.strip()
    
    return config

config = load_config()
driver = GraphDatabase.driver(config['uri'], auth=(config['username'], config['password']))
DATABASE = config['database']


def query_neo4j(cypher, parameters=None):
    """执行Neo4j查询"""
    with driver.session(database=DATABASE) as session:
        result = session.run(cypher, parameters or {})
        return [dict(record) for record in result]


@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'message': '武周-唐初知识图谱API'})


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取数据库统计信息"""
    try:
        stats = {}
        
        result = query_neo4j("MATCH (p:Person) RETURN count(p) as count")
        stats['person_count'] = result[0]['count']
        
        result = query_neo4j("MATCH (l:Place) RETURN count(l) as count")
        stats['place_count'] = result[0]['count']
        
        result = query_neo4j("MATCH (e:Event) RETURN count(e) as count")
        stats['event_count'] = result[0]['count']
        
        result = query_neo4j("MATCH (t:TimeAnchor) RETURN count(t) as count")
        stats['time_count'] = result[0]['count']
        
        result = query_neo4j("MATCH ()-[r]->() RETURN count(r) as count")
        stats['relation_count'] = result[0]['count']
        
        result = query_neo4j("""
            MATCH (e:Event)
            RETURN e.event_type as type, count(*) as count
            ORDER BY count DESC
            LIMIT 10
        """)
        stats['event_types'] = result
        
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/search/person', methods=['GET'])
def search_person():
    """搜索人物"""
    keyword = request.args.get('keyword', '', type=str)
    limit = int(request.args.get('limit', 20))
    
    # 调试输出
    app.logger.info(f"搜索人物关键词: {keyword}, 类型: {type(keyword)}")
    
    try:
        result = query_neo4j("""
            MATCH (p:Person)
            WHERE p.name CONTAINS $keyword
            RETURN p.personId as id, p.name as name, 
                   p.roles as roles, p.offices as offices
            LIMIT $limit
        """, {'keyword': keyword, 'limit': limit})
        
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/search/event', methods=['GET'])
def search_event():
    """搜索事件"""
    keyword = request.args.get('keyword', '')
    event_type = request.args.get('type', '')
    limit = int(request.args.get('limit', 20))
    
    try:
        if event_type:
            result = query_neo4j("""
                MATCH (e:Event)
                WHERE e.event_type CONTAINS $event_type
                RETURN e.eventId as id, e.name as name, 
                       e.event_type as type, e.time as time, 
                       e.place as place, e.description as description
                ORDER BY e.time
                LIMIT $limit
            """, {'event_type': event_type, 'limit': limit})
        else:
            result = query_neo4j("""
                MATCH (e:Event)
                WHERE e.name CONTAINS $keyword
                RETURN e.eventId as id, e.name as name, 
                       e.event_type as type, e.time as time, 
                       e.place as place, e.description as description
                LIMIT $limit
            """, {'keyword': keyword, 'limit': limit})
        
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/person/<person_id>/relations', methods=['GET'])
def get_person_relations(person_id):
    """获取人物关系"""
    try:
        result = query_neo4j("""
            MATCH (p1:Person {personId: $person_id})-[r:PERSON_PERSON]-(p2:Person)
            RETURN p1.name as person1, r.relation as relation, 
                   p2.name as person2, p2.personId as person2_id, 
                   r.time as time
            LIMIT 50
        """, {'person_id': person_id})
        
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/person/<person_id>/events', methods=['GET'])
def get_person_events(person_id):
    """获取人物参与的事件"""
    try:
        result = query_neo4j("""
            MATCH (p:Person {personId: $person_id})-[:PERSON_PARTICIPATES_EVENT]->(e:Event)
            RETURN e.eventId as id, e.name as name, 
                   e.event_type as type, e.time as time, 
                   e.place as place, e.description as description
            ORDER BY e.time
            LIMIT 50
        """, {'person_id': person_id})
        
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/event/<event_id>/participants', methods=['GET'])
def get_event_participants(event_id):
    """获取事件参与者"""
    try:
        result = query_neo4j("""
            MATCH (p:Person)-[:PERSON_PARTICIPATES_EVENT]->(e:Event {eventId: $event_id})
            RETURN p.personId as id, p.name as name, p.roles as roles
            LIMIT 50
        """, {'event_id': event_id})
        
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/timeline', methods=['GET'])
def get_timeline():
    """获取时间线"""
    time_pattern = request.args.get('pattern', '')
    limit = int(request.args.get('limit', 50))
    
    try:
        result = query_neo4j("""
            MATCH (e:Event)-[:EVENT_OCCURS_AT]->(t:TimeAnchor)
            WHERE t.normalized CONTAINS $pattern
            RETURN e.eventId as id, e.name as name, 
                   e.event_type as type, t.normalized as time
            ORDER BY t.normalized
            LIMIT $limit
        """, {'pattern': time_pattern, 'limit': limit})
        
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/graph/person/<person_id>', methods=['GET'])
def get_person_graph(person_id):
    """获取人物关系图谱数据"""
    try:
        person = query_neo4j("""
            MATCH (p:Person {personId: $person_id})
            RETURN p.personId as id, p.name as name, p.roles as roles
        """, {'person_id': person_id})
        
        if not person:
            return jsonify({'success': False, 'error': '人物不存在'}), 404
        
        relations = query_neo4j("""
            MATCH (p1:Person {personId: $person_id})-[r:PERSON_PERSON]-(p2:Person)
            RETURN p1.personId as source, p2.personId as target, 
                   r.relation as relation, p2.name as target_name
            LIMIT 20
        """, {'person_id': person_id})
        
        nodes = [{'id': person[0]['id'], 'name': person[0]['name'], 'type': 'center'}]
        edges = []
        
        seen_nodes = {person[0]['id']}
        for rel in relations:
            if rel['target'] not in seen_nodes:
                nodes.append({
                    'id': rel['target'],
                    'name': rel['target_name'],
                    'type': 'related'
                })
                seen_nodes.add(rel['target'])
            
            edges.append({
                'source': rel['source'],
                'target': rel['target'],
                'relation': rel['relation']
            })
        
        return jsonify({'success': True, 'data': {'nodes': nodes, 'edges': edges}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/graph/full', methods=['GET'])
def get_full_graph():
    """获取完整知识图谱数据"""
    return get_graph_view('family')


@app.route('/api/graph/view/<view_type>', methods=['GET'])
def get_graph_view(view_type):
    """根据视图类型获取图谱数据"""
    try:
        if view_type == 'family':
            return get_family_graph()
        elif view_type == 'politics':
            return get_politics_graph()
        elif view_type == 'events':
            return get_events_chart()
        elif view_type == 'timeline':
            return get_timeline_chart()
        else:
            return get_family_graph()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def get_family_graph():
    """获取皇室家族关系图"""
    # 获取有血缘/婚姻关系的人物
    family_relations = ['父子', '母子', '父女', '母女', '兄弟', '子', '弟', '夫妻', '婚姻', '配偶', '曾孙']
    
    relations = query_neo4j("""
        MATCH (p1:Person)-[r:PERSON_PERSON]->(p2:Person)
        WHERE r.relation IN $rels
        RETURN p1.personId as source_id, p1.name as source_name, p1.roles as source_roles,
               p2.personId as target_id, p2.name as target_name, p2.roles as target_roles,
               r.relation as relation
    """, {'rels': family_relations})
    
    # 构建节点和边
    nodes = {}
    links = []
    
    for r in relations:
        # 源节点
        if r['source_id'] not in nodes:
            roles = r['source_roles'] if r['source_roles'] else []
            role_str = '|'.join(roles) if roles else ''
            nodes[r['source_id']] = {
                'id': r['source_id'],
                'name': r['source_name'],
                'role': role_str,
                'size': 30
            }
        nodes[r['source_id']]['size'] += 5
        
        # 目标节点
        if r['target_id'] not in nodes:
            roles = r['target_roles'] if r['target_roles'] else []
            role_str = '|'.join(roles) if roles else ''
            nodes[r['target_id']] = {
                'id': r['target_id'],
                'name': r['target_name'],
                'role': role_str,
                'size': 30
            }
        nodes[r['target_id']]['size'] += 5
        
        links.append({
            'source': r['source_id'],
            'target': r['target_id'],
            'relation': r['relation']
        })
    
    return jsonify({
        'success': True,
        'data': {
            'nodes': list(nodes.values()),
            'links': links
        }
    })


def get_politics_graph():
    """获取政治关系图"""
    political_relations = ['奏劾', '讨伐', '贬谪', '杀害', '弑杀', '通谋', '举荐', '弹劾', '诛杀']
    
    relations = query_neo4j("""
        MATCH (p1:Person)-[r:PERSON_PERSON]->(p2:Person)
        WHERE r.relation IN $rels
        RETURN p1.personId as source_id, p1.name as source_name, p1.roles as source_roles,
               p2.personId as target_id, p2.name as target_name, p2.roles as target_roles,
               r.relation as relation
    """, {'rels': political_relations})
    
    nodes = {}
    links = []
    
    for r in relations:
        if r['source_id'] not in nodes:
            roles = r['source_roles'] if r['source_roles'] else []
            nodes[r['source_id']] = {
                'id': r['source_id'],
                'name': r['source_name'],
                'role': '|'.join(roles) if roles else '',
                'size': 35
            }
        nodes[r['source_id']]['size'] += 8
        
        if r['target_id'] not in nodes:
            roles = r['target_roles'] if r['target_roles'] else []
            nodes[r['target_id']] = {
                'id': r['target_id'],
                'name': r['target_name'],
                'role': '|'.join(roles) if roles else '',
                'size': 35
            }
        nodes[r['target_id']]['size'] += 8
        
        links.append({
            'source': r['source_id'],
            'target': r['target_id'],
            'relation': r['relation']
        })
    
    return jsonify({
        'success': True,
        'data': {
            'nodes': list(nodes.values()),
            'links': links
        }
    })


def get_events_chart():
    """获取事件参与度排行"""
    result = query_neo4j("""
        MATCH (p:Person)-[:PERSON_PARTICIPATES_EVENT]->(e:Event)
        WITH p, count(e) as event_count
        WHERE event_count > 5
        RETURN p.personId as id, p.name as name, event_count as count
        ORDER BY event_count DESC
        LIMIT 25
    """)
    
    # 反转顺序（条形图从下到上）
    persons = list(reversed(result))
    
    return jsonify({
        'success': True,
        'data': {'persons': persons}
    })


def get_timeline_chart():
    """获取时间线数据"""
    # 按年号统计事件数量
    result = query_neo4j("""
        MATCH (e:Event)-[:EVENT_OCCURS_AT]->(t:TimeAnchor)
        WITH t.normalized as time, count(e) as count
        WHERE time IS NOT NULL AND time <> ''
        RETURN time, count
        ORDER BY time
        LIMIT 100
    """)
    
    # 提取年号并聚合
    period_counts = {}
    for r in result:
        time = r['time']
        # 提取年号（如"武德元年" -> "武德"）
        period = ''
        for char in time:
            if char in '元一二三四五六七八九十年':
                break
            period += char
        if period and len(period) <= 4:
            period_counts[period] = period_counts.get(period, 0) + r['count']
    
    # 转换为列表并排序
    periods = [{'name': k, 'count': v} for k, v in period_counts.items()]
    periods.sort(key=lambda x: -x['count'])
    periods = periods[:15]  # 取前15个年号
    
    return jsonify({
        'success': True,
        'data': {'periods': periods}
    })


if __name__ == '__main__':
    print("="*70)
    print("🚀 武周-唐初知识图谱 API Server")
    print("="*70)
    print(f"Neo4j URI: {config['uri']}")
    print(f"API地址: http://localhost:5002")
    print("="*70)
    
    app.run(debug=True, host='0.0.0.0', port=5002)
