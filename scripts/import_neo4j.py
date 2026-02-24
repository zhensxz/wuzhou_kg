#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j数据导入脚本
将CSV数据导入到本地Neo4j数据库
"""

import csv
import time
from pathlib import Path
from collections import defaultdict

from neo4j import GraphDatabase


class Neo4jImporter:
    """Neo4j数据导入器"""
    
    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None
        
        # 数据目录
        self.data_dir = Path(__file__).parent.parent / "data"
        self.nodes_dir = self.data_dir / "nodes"
        self.edges_dir = self.data_dir / "edges"
        
        self.stats = defaultdict(int)
    
    def connect(self) -> bool:
        """连接到Neo4j数据库"""
        print("🔌 连接到Neo4j...")
        try:
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.username, self.password)
            )
            self.driver.verify_connectivity()
            print("  ✓ 连接成功！")
            return True
        except Exception as e:
            print(f"  ✗ 连接失败: {e}")
            return False
    
    def close(self):
        if self.driver:
            self.driver.close()
    
    def clear_database(self):
        """清空数据库"""
        print("\n🗑️  清空数据库...")
        with self.driver.session(database=self.database) as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("  ✓ 数据库已清空")
    
    def create_constraints(self):
        """创建约束和索引"""
        print("\n📋 创建约束和索引...")
        
        constraints = [
            "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.personId IS UNIQUE",
            "CREATE CONSTRAINT place_id IF NOT EXISTS FOR (l:Place) REQUIRE l.placeId IS UNIQUE",
            "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.eventId IS UNIQUE",
            "CREATE CONSTRAINT time_id IF NOT EXISTS FOR (t:TimeAnchor) REQUIRE t.timeId IS UNIQUE",
        ]
        
        with self.driver.session(database=self.database) as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    pass
        print("  ✓ 完成")
    
    def import_nodes(self, label: str, id_field: str):
        """导入节点"""
        csv_file = self.nodes_dir / f"{label}.csv"
        if not csv_file.exists():
            print(f"  ✗ 文件不存在: {csv_file}")
            return
        
        print(f"\n📦 导入 {label} 节点...")
        count = 0
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            with self.driver.session(database=self.database) as session:
                for row in reader:
                    props = {}
                    for key, value in row.items():
                        if key == ':LABEL':
                            continue
                        
                        clean_key = key.replace(':ID', '').replace(':string[]', '').replace(':float', '')
                        
                        if ':string[]' in key:
                            props[clean_key] = value.split('|') if value else []
                        elif ':float' in key:
                            props[clean_key] = float(value) if value else 0.0
                        else:
                            props[clean_key] = value
                    
                    session.run(f"CREATE (n:{label} $props)", props=props)
                    count += 1
                    
                    if count % 200 == 0:
                        print(f"  已导入 {count}...")
        
        self.stats[f'{label}_nodes'] = count
        print(f"  ✓ 完成: {count} 个节点")
    
    def import_relationships(self, rel_file: Path):
        """导入关系"""
        rel_type = rel_file.stem
        print(f"\n🔗 导入 {rel_type} 关系...")
        
        count = 0
        with open(rel_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            with self.driver.session(database=self.database) as session:
                for row in reader:
                    start_id = row[':START_ID']
                    end_id = row[':END_ID']
                    
                    props = {}
                    for key, value in row.items():
                        if key in [':START_ID', ':END_ID', ':TYPE']:
                            continue
                        clean_key = key.replace(':float', '')
                        if ':float' in key:
                            props[clean_key] = float(value) if value else 0.0
                        else:
                            props[clean_key] = value
                    
                    start_label = self._get_label(start_id)
                    end_label = self._get_label(end_id)
                    start_id_field = self._get_id_field(start_label)
                    end_id_field = self._get_id_field(end_label)
                    
                    query = f"""
                    MATCH (a:{start_label} {{{start_id_field}: $start_id}})
                    MATCH (b:{end_label} {{{end_id_field}: $end_id}})
                    CREATE (a)-[r:{rel_type}]->(b)
                    SET r = $props
                    """
                    
                    try:
                        session.run(query, start_id=start_id, end_id=end_id, props=props)
                        count += 1
                    except:
                        pass
                    
                    if count % 500 == 0:
                        print(f"  已导入 {count}...")
        
        self.stats[f'rel_{rel_type}'] = count
        print(f"  ✓ 完成: {count} 条关系")
    
    def _get_label(self, node_id: str) -> str:
        if node_id.startswith('P'):
            return 'Person'
        elif node_id.startswith('L'):
            return 'Place'
        elif node_id.startswith('E'):
            return 'Event'
        elif node_id.startswith('T'):
            return 'TimeAnchor'
        return 'Unknown'
    
    def _get_id_field(self, label: str) -> str:
        return {
            'Person': 'personId',
            'Place': 'placeId',
            'Event': 'eventId',
            'TimeAnchor': 'timeId'
        }.get(label, 'id')
    
    def run(self):
        """运行导入"""
        print("="*70)
        print("🚀 武周-唐初知识图谱 - 数据导入")
        print("="*70)
        
        if not self.connect():
            return
        
        try:
            self.clear_database()
            self.create_constraints()
            
            # 导入节点
            self.import_nodes('Person', 'personId')
            self.import_nodes('Place', 'placeId')
            self.import_nodes('Event', 'eventId')
            self.import_nodes('TimeAnchor', 'timeId')
            
            # 导入关系
            for edge_file in sorted(self.edges_dir.glob("*.csv")):
                self.import_relationships(edge_file)
            
            # 统计
            print("\n" + "="*70)
            print("📊 导入完成！")
            print("="*70)
            for key, value in self.stats.items():
                print(f"  {key}: {value}")
            
        finally:
            self.close()


def load_config():
    """加载配置"""
    config_file = Path(__file__).parent.parent / 'config' / 'neo4j_config.txt'
    config = {'uri': '', 'username': 'neo4j', 'password': '', 'database': 'neo4j'}
    
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip().lower()] = value.strip()
    
    return config


def main():
    config = load_config()
    
    if not config['uri']:
        print("❌ 未找到配置文件")
        return
    
    importer = Neo4jImporter(
        uri=config['uri'],
        username=config['username'],
        password=config['password'],
        database=config['database']
    )
    
    importer.run()


if __name__ == "__main__":
    main()
