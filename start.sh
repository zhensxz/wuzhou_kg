#!/bin/bash
# 一键启动武周-唐初知识图谱系统

echo "======================================"
echo "🏛️ 武周-唐初历史知识图谱系统"
echo "======================================"

# 检查Neo4j是否运行
if ! docker ps | grep -q neo4j-wuzhou; then
    echo "⚠️  Neo4j未运行，请先执行："
    echo "   ./scripts/start_neo4j.sh"
    exit 1
fi

# 启动后端
echo ""
echo "🚀 启动后端服务..."
cd backend
python app.py &
BACKEND_PID=$!
cd ..

sleep 3

# 启动前端
echo ""
echo "🌐 启动前端服务..."
cd frontend
python -m http.server 8080 &
FRONTEND_PID=$!
cd ..

echo ""
echo "======================================"
echo "✅ 服务已启动！"
echo "======================================"
echo ""
echo "📊 前端地址: http://localhost:8080"
echo "🔌 后端API: http://localhost:5002"
echo "🗄️  Neo4j: http://localhost:7474"
echo ""
echo "按 Ctrl+C 停止服务"

wait
