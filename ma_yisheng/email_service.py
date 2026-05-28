import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr


def send_verification_email(to_email, code, smtp_config):
    try:
        host = smtp_config.get("host")
        port = smtp_config.get("port", 587)
        user = smtp_config.get("user")
        password = smtp_config.get("password")
        from_name = smtp_config.get("from_name", "马医生")

        if not all([host, user, password]):
            return False, "SMTP 配置不完整（host/user/password 缺失）"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"【马医生】邮箱验证码：{code}"
        msg["From"] = formataddr((from_name, user))
        msg["To"] = to_email

        html_body = f"""<html>
<body style="font-family: 'Microsoft YaHei', sans-serif; padding: 20px; background: #f8f9fa;">
<div style="max-width: 420px; margin: 0 auto; background: #fff; border: 3px solid #000; padding: 24px;">
  <h2 style="color: #0D9488; margin-top: 0;">🐴 马医生 · 代码安全扫描</h2>
  <p style="font-size: 14px; color: #333;">你正在注册或登录马医生代码安全扫描平台，以下是你的验证码：</p>
  <div style="text-align: center; padding: 16px; background: #fef3c7; border: 2px solid #000; margin: 16px 0;">
    <span style="font-size: 28px; font-weight: 900; letter-spacing: 6px; color: #000;">{code}</span>
  </div>
  <p style="font-size: 12px; color: #999;">5 分钟内有效，请勿转发给他人。</p>
  <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 16px 0;">
  <p style="font-size: 11px; color: #ccc;">如果这不是你本人操作，请忽略此邮件。</p>
</div>
</body>
</html>"""

        msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, to_email, msg.as_string())
        return True, ""
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP 认证失败，请检查邮箱账号和授权码是否正确"
    except smtplib.SMTPConnectError:
        return False, f"无法连接 SMTP 服务器 {host}:{port}，请检查地址和端口"
    except Exception as e:
        return False, f"发送失败：{e}"
