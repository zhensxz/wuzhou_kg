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
├── sources/               # 原始史料（维基文库）
│   ├── wikisource_zztj/   # 资治通鉴
│   ├── wikisource_jiutangshu/  # 旧唐书
│   ├── wikisource_xintangshu/  # 新唐书
│   └── wikisource_tanghuiyao/  # 唐会要
│
├── llm_extraction/        # LLM实体关系抽取
│   ├── fetch_wikisource_*.py   # 史料爬取脚本
│   ├── llm_extract_volume_thinking_async.py  # LLM抽取主程序
│   ├── outputs/           # 抽取结果
│   └── README.md          # 抽取流程说明
│
├── data/                  # 知识图谱数据（Neo4j格式）
│   ├── nodes/             # 节点CSV
│   │   ├── Person.csv
│   │   ├── Event.csv
│   │   ├── Place.csv
│   │   └── TimeAnchor.csv
│   └── edges/             # 关系CSV
│       ├── PERSON_PERSON.csv
│       ├── PERSON_PARTICIPATES_EVENT.csv
│       └── ...
│
├── backend/               # Flask后端API
│   ├── app.py
│   └── requirements.txt
│
├── frontend/              # 前端可视化
│   └── index.html
│
├── scripts/               # 工具脚本
│   ├── start_neo4j.sh
│   └── import_neo4j.py
│
├── config/                # 配置文件
│   └── neo4j_config.txt
│
├── start.sh               # 一键启动
└── README.md
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

## 📚 数据来源与处理流程

### 数据来源
从中文维基文库爬取以下古籍：
- 《资治通鉴》卷203-209（武周至唐中宗编年史）
- 《旧唐书》卷5-8（唐代官修正史）
- 《新唐书》卷1-10（北宋重修唐史）
- 《唐会要》卷1-10（唐代典章制度）

### 处理流程
```
史料采集 → 文本分段 → LLM抽取 → 数据清洗 → Neo4j导入 → 可视化
```

1. **史料采集**：`llm_extraction/fetch_wikisource_*.py` 爬取维基文库
2. **LLM抽取**：`llm_extraction/llm_extract_volume_thinking_async.py` 调用Qwen API
3. **数据清洗**：实体消歧、关系规范化
4. **图谱构建**：导入Neo4j图数据库

详见 `llm_extraction/README.md`

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
