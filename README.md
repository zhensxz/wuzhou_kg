# 武周-唐初历史知识图谱

基于Neo4j的历史知识图谱可视化系统，涵盖武周至唐初（约618-713年）的历史人物、事件、地点和时间关系。

## 📊 数据规模

| 类型 | 数量 |
|-----|------|
| 人物节点 | 1,343 |
| 事件节点 | 2,376 |
| 地点节点 | 1,213 |
| 时间锚点 | 2,768 |
| **节点总计** | **7,700** |
| 关系总计 | 7,375 |

## 📁 项目结构

```
wuzhou_kg_project/
├── backend/                # Flask后端API
│   ├── app.py             # API服务
│   └── requirements.txt   # Python依赖
│
├── frontend/              # 前端界面
│   └── index.html         # ECharts可视化页面
│
├── data/                  # 知识图谱数据
│   ├── nodes/            # 节点CSV文件
│   │   ├── Person.csv    # 人物
│   │   ├── Event.csv     # 事件
│   │   ├── Place.csv     # 地点
│   │   └── TimeAnchor.csv # 时间锚点
│   │
│   └── edges/            # 关系CSV文件
│       ├── PERSON_PERSON.csv
│       ├── PERSON_PARTICIPATES_EVENT.csv
│       ├── EVENT_OCCURS_AT.csv
│       ├── EVENT_LOCATED_AT.csv
│       └── ...
│
├── config/               # 配置文件
│   └── neo4j_config.txt  # Neo4j连接配置
│
├── scripts/              # 脚本
│   ├── start_neo4j.sh    # 启动Neo4j
│   └── import_neo4j.py   # 导入数据脚本
│
├── docs/                 # 文档
│
├── start.sh              # 一键启动脚本
└── README.md             # 本文件
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Docker Desktop
- 浏览器（Chrome/Firefox/Safari）

### 1. 安装Python依赖

```bash
cd backend
pip install flask flask-cors neo4j
```

### 2. 启动Neo4j数据库

```bash
chmod +x scripts/start_neo4j.sh
./scripts/start_neo4j.sh
```

等待约30秒，Neo4j启动后可访问：http://localhost:7474

### 3. 导入数据

```bash
python scripts/import_neo4j.py
```

导入约需3-5分钟。

### 4. 启动后端服务

```bash
cd backend
python app.py
```

API地址：http://localhost:5002

### 5. 启动前端

```bash
cd frontend
python -m http.server 8080
```

### 6. 访问系统

打开浏览器：**http://localhost:8080**

## 🎨 功能特性

### 数据统计
- 实时显示节点和关系数量
- 事件类型分布图

### 多维度搜索
- **人物搜索**：按名称查找历史人物
- **事件搜索**：按类型查找历史事件
- **时间线**：按年号查询事件

### 可视化
- ECharts力导向关系图
- 人物关系网络
- 事件参与者图
- 时间线柱状图

## 📚 数据来源

从以下古籍提取：
- 《资治通鉴》卷203-209
- 《旧唐书》卷5-8
- 《新唐书》卷1-10
- 《唐会要》卷1-10

使用LLM（Qwen）进行实体和关系抽取。

## 🛠️ 技术栈

- **后端**：Flask + Neo4j Python Driver
- **前端**：HTML + Bootstrap 5 + ECharts
- **数据库**：Neo4j 5.15 (Docker)
- **数据处理**：Python + Qwen LLM

## 📝 API接口

| 接口 | 方法 | 说明 |
|-----|------|------|
| `/api/stats` | GET | 获取统计信息 |
| `/api/search/person?keyword=xxx` | GET | 搜索人物 |
| `/api/search/event?type=xxx` | GET | 搜索事件 |
| `/api/person/<id>/relations` | GET | 获取人物关系 |
| `/api/person/<id>/events` | GET | 获取人物参与的事件 |
| `/api/timeline?pattern=xxx` | GET | 获取时间线 |

## 📄 许可证

本项目仅供学术研究和课程学习使用。

---

**知识图谱导论课程项目 | 2026**
