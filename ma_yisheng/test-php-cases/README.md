# PHP 漏洞扫描测试案例

扫描路径：

```text
/Users/infinite/Documents/yasa-rule-optimizer/ma_yisheng/test-php-cases
```

推荐参数：

```text
语言：php
引擎：YASA
规则模式：minimal 或 full
```

这个案例使用 `VulnerableController` 的 public action 方法。YASA 的 PHP 分析器会优先收集 Controller action 作为入口点，裸 PHP 脚本可能不会被当作有效入口。

预期可检测：

- `$_REQUEST['cmd'] -> system($cmd)`：命令注入
- `$_GET['id'] -> mysqli_query(...)`：SQL 注入
- `$_POST['name'] -> echo`：XSS
- `$_GET['page'] -> include`：路径遍历/文件包含
- `$_GET['url'] -> file_get_contents`：SSRF 或路径遍历，取决于规则命中路径
