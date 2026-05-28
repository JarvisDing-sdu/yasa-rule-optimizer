# Authentication Guide

[Language: [中文](AUTH_README.md) | **English**]

## Configuration

Add JWT and SMTP settings to `.env`:

```env
JWT_SECRET=your-random-secret-key-here
JWT_EXPIRE_DAYS=30
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_NAME=Ma Yisheng
```

## API Usage

- `POST /api/auth/send-code`: send an email verification code.
- `POST /api/auth/register`: register with email, verification code, and password.
- `POST /api/auth/login`: log in.
- Use `Authorization: Bearer <token>` for protected scan and report APIs.

## Security Notes

Change `JWT_SECRET` in production, deploy with HTTPS, back up `users.db`, and avoid logging tokens or passwords.

