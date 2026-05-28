# Python 漏洞扫描测试案例

扫描路径：

```text
/Users/infinite/Documents/yasa-rule-optimizer/ma_yisheng/test-python-cases
```

推荐参数：

```text
语言：python
引擎：YASA
规则模式：minimal 或 full
```

预期可检测：

- `input() -> os.system(...)`：命令执行
- `input() -> subprocess.run(...)`：命令执行
- `input() -> eval(...)`：代码执行
- `input() -> cursor.execute(...)`：SQL 注入
