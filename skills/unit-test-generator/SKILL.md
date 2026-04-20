---
name: unit-test-generator
description: 为代码生成单元测试用例
version: 1.0.0
category: development
author: Phoenix Core Team (参考 anthropics/skills)
license: MIT
tags: ["testing", "code-generation", "unit-test"]
---

# Unit Test Generator - 单元测试生成器

## 触发条件

当用户需要为代码生成测试时触发：
- "为这个函数写测试"
- "生成单元测试"
- "测试这段代码"
- "添加测试覆盖率"

## 执行步骤

1. **分析代码** - 理解函数功能、输入输出
2. **识别测试场景** - 正常情况、边界情况、异常情况
3. **选择测试框架** - pytest、unittest、jest 等
4. **生成测试用例** - 覆盖所有场景
5. **添加断言** - 验证预期行为
6. **生成测试数据** - 必要的 mock 和 fixture

## 测试覆盖维度

| 维度 | 说明 | 示例 |
|------|------|------|
| **正常路径** | 主要功能测试 | 输入有效数据 |
| **边界条件** | 极限值测试 | 空列表、最大值、None |
| **异常处理** | 错误输入测试 | 类型错误、无效值 |
| **副作用** | 状态变化测试 | 数据库、文件、缓存 |

## 输出格式

```python
# 测试文件
import pytest
from module import function_name

class TestFunctionName:
    """function_name 的测试"""
    
    def test_normal_case(self):
        """测试正常情况"""
        result = function_name(valid_input)
        assert result == expected_output
    
    def test_edge_case(self):
        """测试边界情况"""
        result = function_name(edge_input)
        assert result == edge_expected
    
    def test_exception(self):
        """测试异常抛出"""
        with pytest.raises(ExpectedException):
            function_name(invalid_input)
```

## 示例

### 示例 1：Python 函数测试

用户："为这个函数生成测试"

```python
def calculate_discount(price: float, discount: float) -> float:
    """计算折扣价"""
    if discount < 0 or discount > 1:
        raise ValueError("折扣必须在 0-1 之间")
    return price * (1 - discount)
```

输出:
```python
import pytest
from module import calculate_discount

class TestCalculateDiscount:
    """calculate_discount 测试"""
    
    def test_normal_discount(self):
        """测试正常折扣"""
        assert calculate_discount(100, 0.2) == 80
        assert calculate_discount(200, 0.1) == 180
    
    def test_zero_discount(self):
        """测试零折扣"""
        assert calculate_discount(100, 0) == 100
    
    def test_full_discount(self):
        """测试全免"""
        assert calculate_discount(100, 1) == 0
    
    def test_invalid_discount_negative(self):
        """测试负数折扣抛出异常"""
        with pytest.raises(ValueError, match="折扣必须在 0-1 之间"):
            calculate_discount(100, -0.1)
    
    def test_invalid_discount_over_one(self):
        """测试超过 1 的折扣抛出异常"""
        with pytest.raises(ValueError, match="折扣必须在 0-1 之间"):
            calculate_discount(100, 1.5)
    
    def test_zero_price(self):
        """测试零价格"""
        assert calculate_discount(0, 0.5) == 0
```

### 示例 2：类方法测试

用户："为这个类生成测试"

```python
class ShoppingCart:
    def __init__(self):
        self.items = []
    
    def add_item(self, name, price, quantity=1):
        self.items.append({"name": name, "price": price, "quantity": quantity})
    
    def total(self):
        return sum(item["price"] * item["quantity"] for item in self.items)
```

输出:
```python
import pytest
from cart import ShoppingCart

class TestShoppingCart:
    """购物车测试"""
    
    def test_empty_cart_total(self):
        """空购物车总价为 0"""
        cart = ShoppingCart()
        assert cart.total() == 0
    
    def test_add_single_item(self):
        """添加单个商品"""
        cart = ShoppingCart()
        cart.add_item("Book", 20, 1)
        assert cart.total() == 20
    
    def test_add_multiple_items(self):
        """添加多个商品"""
        cart = ShoppingCart()
        cart.add_item("Book", 20, 2)
        cart.add_item("Pen", 5, 3)
        assert cart.total() == 55
    
    def test_add_item_default_quantity(self):
        """默认数量为 1"""
        cart = ShoppingCart()
        cart.add_item("Book", 20)
        assert len(cart.items) == 1
        assert cart.items[0]["quantity"] == 1
```

## 支持的测试框架

| 语言 | 框架 | 命令 |
|------|------|------|
| Python | pytest | `pytest tests/` |
| Python | unittest | `python -m unittest` |
| JavaScript | Jest | `npm test` |
| JavaScript | Mocha | `mocha tests/` |
| Java | JUnit | `mvn test` |

## 相关技能

- [code-reviewer](../code-reviewer/) - 代码审查
- [api-tester](../api-tester/) - API 测试
- [documentation-writer](../documentation-writer/) - 文档编写

---

*版本：v1.0*
*参考：anthropics/skills*
