# 优路元航 GIS 盲道问题可视化

Streamlit 工作台把经过校验的盲道问题 CSV 导入 canonical 存储，并提供地图查看、CSV 导入导出和数据管理。未配置 `DATABASE_URL` 时使用本地 SQLite；部署时配置 Supabase/Postgres 以获得持久化数据。生产仓库不携带演示记录。

## 数据契约

`data/blind_path_issues.csv` 是空的 UTF-8 with BOM CSV，包含以下固定 13 列，顺序不可改变：

```text
id,city,district,street,longitude,latitude,problem_type,subtype,severity,confidence,description,detected_at,data_source
```

`data/gis.sqlite3` 是空数据库，启动时会创建 `gis_rows` 表。空状态是有效状态，不会触发地图准备；查看页给出导入/新增引导，数据管理页仍可用。

有效数据必须使用 GCJ-02 坐标、唯一 `id`、完整 13 列和 UTF-8 BOM。CSV 经过边界校验后写入 canonical 存储；本地为 SQLite，部署配置 `DATABASE_URL` 后为 PostgreSQL。

## 本地运行

```powershell
cd D:\社会实践\GIS可视化
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

地图需要高德配置。仅在项目父目录 `.env` 或进程环境中提供 `AMAP_KEY`、`AMAP_SECURITY_CODE`，不要提交 `.env` 或真实密钥。

```powershell
$env:AMAP_KEY = "<your-key>"
$env:AMAP_SECURITY_CODE = "<your-security-code>"
```

## 免费部署方案（核实于 2026-08-29）

### 方案 A：Streamlit Community Cloud（首选）

这是与当前应用最匹配的免费方案。把 `GIS可视化` 目录内容放到 GitHub 仓库根目录（或确保入口和依赖路径按仓库根目录配置），在 <https://share.streamlit.io/> 创建应用，入口文件填写 `streamlit_app.py`。不要提交 `.env`、高德 Key 或真实航拍原图。

在 Community Cloud 的 Secrets 中填写 TOML：

```toml
AMAP_KEY = "your-amap-web-key"
AMAP_SECURITY_CODE = "your-amap-security-code"
GIS_READ_ONLY = "1"
```

### Supabase/Postgres 持久化与编辑认证

需要在线维护数据时，在 Streamlit Cloud 的 App settings -> Secrets 中增加：

```toml
AMAP_KEY = "your-amap-web-key"
AMAP_SECURITY_CODE = "your-amap-security-code"
DATABASE_URL = "postgresql://postgres.PROJECT_REF:PASSWORD@HOST:6543/postgres"
GIS_ADMIN_CODE = "your-fixed-editor-code"
GIS_READ_ONLY = "0"
```

`DATABASE_URL` 必须是 Supabase 的 Postgres connection string，不是 anon key 或 service role key（代码也接受同值的 `SUPABASE_DB_URL`）。优先使用 Supabase Connect 页面提供的 transaction pooler（通常为 6543 端口）；密码含特殊字符时应按 URL 规则编码。应用首次启动会自动创建 `gis_rows` 表，并且只在该表为空时把 `data/blind_path_issues.csv` 迁移进去，后续新增、编辑、删除都直接写入 Postgres。

`GIS_ADMIN_CODE` 是共享编辑口令，不是多用户账户系统。口令只保存在 Streamlit Secrets 中；点击“数据管理”后输入正确口令才会打开编辑控件，退出编辑会清除当前会话授权。公开展示时请设置 `GIS_READ_ONLY = "1"`，此时管理入口完全关闭；如果配置了数据库但没有配置口令，应用也不会开放管理入口。

Postgres 改造持久化的是表格数据。当前图片附件仍写入应用文件系统，Streamlit Cloud 重启后可能丢失；需要长期保存图片时，应继续接入 Supabase Storage（或其他对象存储），并把图片 URL/对象键存入数据库。

应用代码同时支持 `st.secrets` 和环境变量。把部署后的 `*.streamlit.app` 域名加入高德 JS API 白名单，否则地图可能报 `INVALID_USER_DOMAIN`。Community Cloud 免费资源上限约为 2.7 GB 内存、2 CPU，连续 12 小时无访问会休眠；本地 SQLite、CSV 和图片不应视为持久存储。PNG 导出在没有 Chromium 的环境会自动降级为 Matplotlib 静态图。

仓库中的 `packages.txt` 会为降级 PNG 安装 `fonts-noto-cjk`，避免中文标题缺字。

### 方案 B：Render Free（临时演示/评审）

Render 支持从本项目 `Dockerfile` 创建 Free Web Service。Dockerfile 会安装 Chromium 和中文字体，首次构建较慢、镜像也较大。免费实例 15 分钟无请求会休眠，唤醒约需 1 分钟；休眠、重启或重新部署会丢失本地 SQLite、CSV 和图片，且官方明确不建议 Free 实例用于生产。它适合短期答辩演示，不适合持续维护数据。

### 方案 C：GitHub Pages（只发布静态地图）

如果只需要展示已经生成的交互 HTML，可将 `output/盲道问题GIS标注图.html` 放到公开 GitHub 仓库并用 GitHub Pages 发布。该方案没有 Streamlit 的上传、管理和 PNG 导出功能，仓库和页面是公开的；HTML 中的高德 Key 也会发送到浏览器，因此只能使用已脱敏数据并配置域名白名单。

### 关于 Hugging Face Spaces

Hugging Face 官方当前文档写明：CPU Basic 硬件本身无小时费，但新建运行 Docker/Gradio 的 Space 需要付费计划；免费个人账号的例外是最多两个 ZeroGPU Gradio Space。因此本项目的 Docker Space 不能再按“新账号免费首选”规划。若已有可用 Space 或愿意使用付费计划，现有 Dockerfile 可继续使用；容器磁盘默认不持久，持久化需挂载存储并设置 `GIS_DATA_DIR`。

### 公开上线开关与数据目录

`GIS_READ_ONLY=1` 只隐藏“数据管理”入口，不是认证机制。公开站点必须使用该开关，并在发布前确认 CSV、HTML 下载内容已去除个人信息、车牌、人脸和精确敏感位置。

需要挂载卷的平台可设置：

```text
GIS_DATA_DIR=/data
```

未配置 `DATABASE_URL` 时，应用会在该目录读取/写入 `blind_path_issues.csv`、`gis.sqlite3` 和图片附件；配置 Postgres 后，表格读写改由远程数据库承担，CSV 仅作为首次迁移种子。免费实例没有可靠持久卷，图片附件仍应迁移到受控对象存储并保留离线备份。

### 上线前检查

1. 当前仓库的 `data/blind_path_issues.csv` 只有表头，`gis.sqlite3` 为空；直接部署会显示“暂无可查看点位”，需要先导入已脱敏的真实结果或单独准备演示数据。
2. 验证高德 Key、Security Code 和实际 HTTPS 域名白名单；确认地图、CSV/HTML 下载和 PNG 降级导出都能完成。
3. 公开部署固定 `GIS_READ_ONLY=1`；在线编辑部署使用 Postgres，并准备数据库/图片的备份恢复流程。
4. 将 YOLOv8 推理与本页面分开说明：本仓库接收已校验的检测结果，不在网站端执行 YOLO 推理。

官方依据：<https://docs.streamlit.io/deploy/streamlit-community-cloud>、<https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app>、<https://huggingface.co/docs/hub/spaces-overview>、<https://huggingface.co/docs/hub/spaces-sdks-docker>、<https://render.com/docs/free>、<https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages>。

## 测试

```powershell
.venv\Scripts\python.exe -m py_compile streamlit_app.py (Get-ChildItem scripts -Filter '*.py' | Select-Object -Expand FullName)
.venv\Scripts\python.exe -m pytest tests -v
```

## 目录

- `streamlit_app.py`: Streamlit 入口和管理页。
- `scripts/`: CSV 校验、SQLite/Postgres 存储、地图与导出核心。
- `data/`: 空 canonical CSV 和本地 SQLite 表（Postgres 部署时仅作首次迁移种子）。
- `tests/`: 空启动、有效 fixture 和核心行为测试。
