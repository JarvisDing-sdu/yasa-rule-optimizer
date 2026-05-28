# C 漏洞扫描测试案例

扫描路径：

```text
/home/dys1013/projects/yasa-rule-optimizer/ma_yisheng/test-c-cases
```

推荐参数：

```text
语言：c
引擎：YASA
规则模式：minimal 或 full
```

预期可检测：

- `getenv() -> system(...)`：命令执行
