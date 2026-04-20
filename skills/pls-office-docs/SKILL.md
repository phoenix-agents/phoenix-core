# pls-office-docs

📄 **Office 文档处理技能** - 创建、读取、编辑 Word、Excel、PPT 和 PDF 文件

## 功能

- 📝 **Word (.docx)** - 创建、读取、编辑 Word 文档
- 📊 **Excel (.xlsx)** - 创建、读取、编辑 Excel 表格
- 📽️ **PPT (.pptx)** - 创建、读取、编辑 PowerPoint 演示文稿
- 📕 **PDF (.pdf)** - 读取、合并、拆分 PDF 文件

## 依赖安装

```bash
# 激活虚拟环境
source /Users/wangsai/phoenix-core/venv/bin/activate

# 安装依赖库
pip install python-docx openpyxl python-pptx pypdf2
```

## 使用方法

### 在对话中使用

```
@场控 创建一个 Word 文档，标题是"会议纪要"
@场控 生成一个 Excel 表格，包含姓名、年龄、城市三列
@场控 读取这个 PDF 文件的内容
@场控 创建一个 5 页的 PPT，主题是产品发布
```

### Python 代码示例

#### 创建 Word 文档
```python
from docx import Document

doc = Document()
doc.add_heading('文档标题', 0)
doc.add_paragraph('这是一个段落。')
doc.add_heading('第一节', 1)
doc.add_paragraph('第一节的内容...')
doc.save('output.docx')
```

#### 创建 Excel 表格
```python
from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws.title = "数据表"

# 添加表头
ws.append(["姓名", "年龄", "城市"])
# 添加数据
ws.append(["张三", 25, "北京"])
ws.append(["李四", 30, "上海"])

wb.save('output.xlsx')
```

#### 创建 PPT
```python
from pptx import Presentation

prs = Presentation()

# 添加标题页
slide = prs.slides.add_slide(prs.slide_layouts[0])
slide.shapes.title.text = "产品发布"
slide.placeholders[1].text = "2026 年 4 月"

# 添加内容页
slide = prs.slides.add_slide(prs.slide_layouts[1])
slide.shapes.title.text = "产品概述"
slide.placeholders[1].text = "这里是产品介绍..."

prs.save('output.pptx')
```

#### 读取 PDF
```python
from PyPDF2 import PdfReader

reader = PdfReader('document.pdf')
text = ""
for page in reader.pages:
    text += page.extract_text()
print(text)
```

## Phoenix Core 集成

在 Phoenix Core Bot 中使用此技能：

```python
# 在 discord_bot.py 或 phoenix_core_gateway.py 中
def create_word_document(title: str, content: str) -> str:
    """创建 Word 文档并返回文件路径"""
    from docx import Document
    import os
    
    doc = Document()
    doc.add_heading(title, 0)
    doc.add_paragraph(content)
    
    filename = f"workspaces/场控/output/{title}.docx"
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    doc.save(filename)
    return filename
```

## 安全说明

✅ **安全**: 本技能只进行本地文件操作，不涉及网络请求

⚠️ **注意事项**:
- 文件保存在 `workspaces/<bot_name>/output/` 目录
- 不要打开来源不明的文档（可能包含恶意宏）
- 大文件处理可能需要较长时间

## 技能版本

- **v1.0.0** (2026-04-11) - 初始版本
  - 支持 Word (.docx) 创建和读取
  - 支持 Excel (.xlsx) 创建和读取
  - 支持 PPT (.pptx) 创建和读取
  - 支持 PDF (.pdf) 读取

## 相关技能

- `markitdown` - 文档转 Markdown
- `ai-documentation-generator` - AI 文档生成
- `cron-task` - 定时任务（可定时生成报表）
