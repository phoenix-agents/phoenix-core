# Tests
# Phoenix Core 测试包
# 添加项目根目录到路径，避免相对导入问题

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
