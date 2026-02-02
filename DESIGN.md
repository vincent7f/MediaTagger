# Dataset Video Manager - 功能设计与实现方案

## 1. 功能目标

- **本地 GUI 应用**：管理用户指定目录下所有视频文件，以列表形式展示。
- **列信息**：文件名、相对路径（相对所选目录）、分类标签（多个标签以分号/逗号/空格分隔）、备注信息。
- **持久化**：将上述信息保存到**数据集所在目录**下的 `.data` 目录中，便于随数据集一起迁移或备份。
- **历史与回滚**：每次保存时在 `.data/history/` 下生成带时间戳的副本，便于回滚到历史版本。
- **预览与快捷操作**：为每个视频生成预览图，选中行时在右侧显示；双击文件名用系统默认播放器打开。

---

## 2. 数据结构与存储约定

### 2.1 目录结构（在用户选择的「数据集目录」下）

```
<dataset_dir>/
  .data/
    video_metadata.json     # 当前元数据（key 为相对路径）
    history/                # 历史备份
      video_metadata_YYYYMMDD_HHMMSS.json
    previews/               # 视频预览图（可选，依赖 opencv）
      <md5(相对路径)>.jpg
```

### 2.2 video_metadata.json 格式

- **Key**：视频文件相对于 `dataset_dir` 的路径字符串（便于跨机器、移动目录后仍可加载）。
- **Value**：`{ "tags": "标签1; 标签2", "notes": "备注内容" }`。
- 标签在界面输入时支持**分号、逗号、空格**分隔；存储时统一规范化为分号分隔。

示例：

```json
{
  "sub\\a.mp4": { "tags": "真实; 训练集", "notes": "备注A" },
  "videos\\b.avi": { "tags": "合成", "notes": "" }
}
```

### 2.3 历史备份

- 每次点击「保存」成功写入 `video_metadata.json` 后，将该文件复制到 `.data/history/`。
- 文件名：`video_metadata_YYYYMMDD_HHMMSS.json`。
- 用户可手动从 history 中选某一文件覆盖当前 `video_metadata.json` 实现回滚。

---

## 3. 功能列表与交互

| 功能 | 说明 |
|------|------|
| 选择目录 | 通过「Select directory」选择数据集根目录，递归扫描所有子目录中的视频（.mp4/.avi/.mov/.mkv/.flv/.webm）。 |
| 列表展示 | 表格四列：文件名、路径（相对所选目录）、分类标签、备注。路径列显示相对路径，便于阅读。 |
| 标签编辑 | 支持分号、逗号、空格分隔；存储时规范化为分号分隔。点击标签/备注单元格可内联编辑，或通过「编辑」按钮打开对话框同时编辑标签与备注。 |
| 保存 | 将当前内存中的元数据写入 `dataset_dir/.data/video_metadata.json`（相对路径 key），并写入 history 副本。保存后在状态栏显示标签统计及「未打标签文件数」。 |
| 刷新 | 重新扫描目录并重新加载 `.data` 中的元数据，合并后刷新列表与状态栏统计。 |
| 双击文件名 | 使用系统默认播放器打开该视频（Windows: `os.startfile`；macOS: `open`；Linux: `xdg-open`）。 |
| 预览图 | 选择目录并刷新后，在后台线程为每个视频在 `.data/previews/` 下生成一帧预览图（约 0.5 秒处或首帧）；选中某行时在右侧「Preview」面板显示对应预览图。 |

---

## 4. 界面布局

- **顶部**：选择目录按钮、当前目录标签、刷新 / 编辑 / 保存按钮。
- **中部**：左侧为视频列表（Treeview + 滚动条），右侧为「Preview」面板（固定宽度，显示当前选中视频的预览图或占位提示）。
- **底部**：状态区（预留最小高度，避免被挤压），四行：
  1. 标签输入说明（分号/逗号/空格分隔）；
  2. 当前状态（如「N video(s) (including subfolders).」或「Saved to ...」）；
  3. 标签统计（Tag counts: 标签1 (n), 标签2 (m), ...）；
  4. 未打标签文件数（Files without tags: k）。

---

## 5. 技术实现要点

### 5.1 技术选型

- **GUI**：Python 标准库 `tkinter` + `ttk`，无额外 GUI 依赖。
- **可选依赖**：`opencv-python`（预览图截帧）、`pillow`（预览图缩放与在 tk 中显示）；未安装时列表与元数据功能正常，仅预览不可用。
- **单文件分发**：`dataset_manager.py` 内含元数据读写与完整 GUI 逻辑，`run_dataset_manager.py` 仅负责导入并调用入口函数。

### 5.2 路径与 key 约定

- **内存与表格**：内部用视频的**绝对路径**作为元数据字典的 key 和 Treeview 行的 `iid`，保证唯一性与打开文件时路径正确。
- **显示**：路径列显示为相对 `dataset_dir` 的路径。
- **存储**：写入 JSON 前将 key 转为相对路径；读取时将相对路径还原为绝对路径再填入内存字典。

### 5.3 预览图

- 路径：`dataset_dir/.data/previews/<md5(相对路径)>.jpg`。
- 生成：后台线程遍历当前视频列表，若对应预览文件不存在则用 OpenCV 截一帧并保存；生成完成后若当前选中行正是该视频，则刷新右侧预览显示。
- 显示：用 PIL 读图、缩放到最大 320×240、转为 `ImageTk.PhotoImage` 在 Label 中显示。

### 5.4 内联编辑

- 点击表格「标签」或「备注」列时，在该单元格上覆盖一个 Entry，提交（Enter/焦点离开）后更新内存中的 `_metadata` 和对应行显示；标签提交前经 `normalize_tags` 规范化。

### 5.5 标签统计

- 保存后与刷新后：遍历当前 `_metadata`，按分号拆分 tags，用 `Counter` 统计各标签出现次数；在状态栏第三行输出，并在控制台打印（便于从 .bat 运行时查看）。未打标签数量为 tags 为空或仅空白的条目数。

---

## 6. 运行与分发

- **运行**：在 dist 目录下执行 `python run_dataset_manager.py`，或双击 `bin\dataset_manager.bat`（依赖系统 PATH 中的 Python）。
- **依赖**：仅需 Python 3.9+ 与 tkinter；需要预览功能时执行 `pip install -r requirements.txt`（opencv-python, pillow）。
- **分发**：将 dist 目录整体复制到其他电脑即可使用，无需安装项目其余部分。

---

## 7. 文件清单（dist）

| 文件 | 说明 |
|------|------|
| `dataset_manager.py` | 单文件实现：元数据读写、历史备份、GUI 与预览逻辑。 |
| `run_dataset_manager.py` | 启动脚本：导入并调用 `run_dataset_manager()`。 |
| `requirements.txt` | 可选依赖：opencv-python、pillow。 |
| `bin/dataset_manager.bat` | Windows 下双击启动 GUI。 |
| `DESIGN.md` | 本文档：功能设计与实现方案。 |
