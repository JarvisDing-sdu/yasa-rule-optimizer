# JavaScript 漏洞扫描测试案例

扫描路径：

```text
/Users/infinite/Documents/yasa-rule-optimizer/ma_yisheng/test-js-cases
```

推荐参数：

```text
语言：js
引擎：YASA
规则模式：minimal 或 full
```

预期可检测：

- `req.query.cmd -> child_process.exec(...)`：命令执行
- `req.query.id -> connection.query(...)`：SQL 注入
- `req.query.file -> fs.readFileSync(...)`：路径遍历
- `req.query.url -> axios.get(...)`：SSRF
- `req.query.cmd -> res.send(...)`：响应输出/XSS 类风险
