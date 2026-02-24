#!/bin/bash
# 启动本地Neo4j Docker容器

echo "🐳 启动Neo4j Docker容器..."

# 检查是否已存在
if docker ps -a | grep -q neo4j-wuzhou; then
    echo "容器已存在，启动中..."
    docker start neo4j-wuzhou
else
    echo "创建新容器..."
    docker run -d \
        --name neo4j-wuzhou \
        -p 7474:7474 -p 7687:7687 \
        -e NEO4J_AUTH=neo4j/wuzhou123 \
        neo4j:5.15.0
fi

echo ""
echo "等待Neo4j启动..."
sleep 15

echo ""
echo "✅ Neo4j已启动！"
echo "   浏览器访问: http://localhost:7474"
echo "   Bolt连接: bolt://localhost:7687"
echo "   用户名: neo4j"
echo "   密码: wuzhou123"
