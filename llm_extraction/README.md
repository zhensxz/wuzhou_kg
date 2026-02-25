# LLM史料实体关系抽取

本目录包含使用大语言模型（Qwen）从古籍史料中抽取实体和关系的完整代码与输出。

## 一、数据来源

从中文维基文库爬取四部古籍的相关卷目：

| 古籍 | 卷数 | 说明 |
|-----|------|------|
| 资治通鉴 | 卷203-209 | 武周至唐中宗时期编年史 |
| 旧唐书 | 卷5-8 | 唐代官修正史 |
| 新唐书 | 卷1-10 | 北宋重修唐史 |
| 唐会要 | 卷1-10 | 唐代典章制度汇编 |

## 二、处理流程

```
1. 史料采集       2. 文本分段       3. LLM抽取       4. 结果合并
   (Wikisource) --> (JSONL格式) --> (Qwen API) --> (JSON输出)
```

### 步骤1：史料采集

使用 `fetch_wikisource_*.py` 脚本从维基文库爬取古籍原文。

```bash
python fetch_wikisource_zztj.py --volumes 203-209
python fetch_wikisource_jiutangshu.py --volumes 5-8
python fetch_wikisource_xintangshu.py --volumes 1-10
python fetch_wikisource_tanghuiyao.py --volumes 1-10
```

输出格式（JSONL，每行一个段落）：
```json
{"id": "zztj_203_p001", "work": "資治通鑑", "volume": "卷203", "kind": "paragraph", "text": "..."}
```

### 步骤2：LLM实体关系抽取

使用 `llm_extract_volume_thinking_async.py` 调用阿里云Qwen API进行抽取。

**核心特性：**
- 模型：qwen3-235b-a22b（深度思考模式）
- 异步并发：同时处理4个文本段落
- 断点续传：已处理的段落自动跳过
- 流式输出：实时显示处理进度

**运行命令：**
```bash
export DASHSCOPE_API_KEY="your_api_key"
python llm_extract_volume_thinking_async.py \
    --input ../sources/wikisource_zztj/items/資治通鑑_卷203.jsonl \
    --output ./outputs/資治通鑑/卷203.jsonl \
    --work 資治通鑑 \
    --volume 卷203 \
    --concurrency 4
```

### 步骤3：Prompt设计

系统提示词要求LLM输出结构化JSON，包含：

```json
{
  "extraction": {
    "persons": [
      {"name": "李世民", "aliases": ["太宗"], "roles": ["皇帝"], "offices": ["天策上将"]}
    ],
    "events": [
      {"name": "玄武门之变", "type": "政变", "time": "武德九年六月", "place": "长安", 
       "participants": ["李世民", "李建成"], "description": "..."}
    ],
    "relations": [
      {"person1": "李世民", "person2": "李建成", "relation": "兄弟", "time": "..."}
    ]
  }
}
```

**抽取的实体类型：**
- 人物（Person）：姓名、别名、身份、官职
- 事件（Event）：名称、类型、时间、地点、参与者
- 地点（Place）：地名、别称
- 时间锚点（TimeAnchor）：年号纪年

**抽取的关系类型：**
- 人物-人物：血缘（父子/兄弟）、婚姻、政治（奏劾/诛杀）
- 人物-事件：参与、主导
- 人物-官职：任命、罢免
- 事件-时间：发生于
- 事件-地点：位于

## 三、输出结果

`outputs/` 目录按古籍分类存储抽取结果：

```
outputs/
├── 資治通鑑/
│   ├── 卷203.jsonl
│   ├── 卷204.jsonl
│   └── ...
├── 舊唐書/
├── 新唐書/
└── 唐會要/
```

每个JSONL文件包含多条记录，每条对应一个文本段落的抽取结果。

## 四、数据统计

| 指标 | 数量 |
|-----|------|
| 处理段落数 | ~2,500 |
| 抽取人物 | 1,343 |
| 抽取事件 | 2,376 |
| 抽取地点 | 1,213 |
| 抽取关系 | 7,375 |

## 五、环境配置

```bash
# 创建conda环境
conda create -n wuzhoukg python=3.11
conda activate wuzhoukg

# 安装依赖
pip install openai dashscope

# 设置API密钥
export DASHSCOPE_API_KEY="sk-xxx"
```

## 六、文件说明

| 文件 | 说明 |
|-----|------|
| `fetch_wikisource_zztj.py` | 爬取资治通鉴 |
| `fetch_wikisource_jiutangshu.py` | 爬取旧唐书 |
| `fetch_wikisource_xintangshu.py` | 爬取新唐书 |
| `fetch_wikisource_tanghuiyao.py` | 爬取唐会要 |
| `llm_extract_volume_thinking_async.py` | LLM抽取主程序 |
| `outputs/` | 抽取结果输出目录 |
