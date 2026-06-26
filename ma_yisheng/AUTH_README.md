# 认证系统使用说明

[语言：**中文** | [English](AUTH_README.en.md)]

## 配置

在 `.env` 文件中添加以下配置：

```env
# JWT 密钥（生产环境请改为随机字符串）
JWT_SECRET=your-random-secret-key-here
JWT_EXPIRE_DAYS=30

# SMTP 邮件配置
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_NAME=码医生
```

### Gmail SMTP 配置

1. 登录 Gmail
2. 进入「管理你的 Google 账号」→「安全性」
3. 开启「两步验证」
4. 生成「应用专用密码」
5. 将生成的密码填入 `SMTP_PASSWORD`

### QQ 邮箱 SMTP 配置

```env
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_USER=your-qq-email@qq.com
SMTP_PASSWORD=授权码（在 QQ 邮箱设置中生成）
```

## API 使用

### 1. 发送验证码

```bash
POST /api/auth/send-code
Content-Type: application/json

{
  "email": "user@example.com"
}
```

响应：
```json
{
  "message": "验证码已发送，5 分钟内有效"
}
```

限流：同一邮箱 1 分钟只能发送 1 次

### 2. 注册

```bash
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "code": "123456",
  "password": "your-password"
}
```

响应：
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "email": "user@example.com"
}
```

密码要求：至少 8 位

### 3. 登录

```bash
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your-password"
}
```

响应：
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "email": "user@example.com"
}
```

### 4. 使用 Token 访问受保护接口

所有扫描相关接口都需要认证，在请求头中带上 token：

```bash
POST /api/scan
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "scan_path": "/path/to/project",
  "lang": "auto",
  "scene": "minimal"
}
```

## 数据隔离

- 每个用户的报告保存在独立目录：`yasa-reports/{user_id}/项目名/...`
- 任务查询时会校验权限，用户只能查看自己的任务
- 用户 A 无法访问用户 B 的扫描结果

## 数据库

用户数据存储在 `users.db`（SQLite），包含：
- id: 用户 ID
- email: 邮箱（唯一）
- password_hash: 密码哈希（bcrypt）
- created_at: 注册时间

## 安全建议

1. **生产环境必须修改 JWT_SECRET**，使用随机字符串（至少 32 位）
2. 使用 HTTPS 部署，避免 token 被窃取
3. 定期备份 `users.db`
4. 不要在日志中输出 token 或密码
