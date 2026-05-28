# Go 漏洞扫描测试案例

扫描路径：

```text
/Users/infinite/Documents/yasa-rule-optimizer/ma_yisheng/test-go-cases
```

推荐参数：

```text
语言：go
引擎：YASA
规则模式：minimal 或 full
```

当前实测可检测：

- `r.FormValue("cmd") -> exec.Command(...)`：命令执行
- `r.FormValue("id") -> db.Query(...)`：SQL 注入
- `r.FormValue("url") -> http.Get(...)`：SSRF

案例中也保留了 `r.FormValue("file") -> os.Create(...)` 的路径遍历写法，但当前这版 YASA Go analyzer + minimal 规则实测没有报出 `GoPathTraversal`。
