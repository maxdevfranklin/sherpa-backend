# Fashion Guide Chat - Authentication Setup

This application features a complete authentication system with email/password and Google OAuth login, including email verification.

## Features

- **Email/Password Authentication**: Traditional signup and login
- **Google OAuth**: Quick sign-in with Google accounts
- **Email Verification**: 6-digit code verification sent to user email
- **JWT Authentication**: Secure token-based authentication
- **User Management**: Complete user lifecycle management
- **Database Integration**: PostgreSQL with user data and chat history

## Backend Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `env.example` to `.env` and configure the following variables:

```bash
# Database Configuration
DATABASE_URL=postgresql://postgres:SCoi~IpdVZe6x37NCP.631X9jZubPctR@centerbeam.proxy.rlwy.net:43656/railway

# JWT Secret Key (IMPORTANT: Change this in production!)
SECRET_KEY=your-super-secret-jwt-key-change-this-in-production

# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-google-oauth-client-id

# Email Configuration (Optional - for email verification)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password

# Frontend Origins (for CORS)
ALLOWED_ORIGINS=http://localhost:3000,https://sherpa-frontend-production.up.railway.app
```

### 3. Google OAuth Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google+ API
4. Go to "Credentials" and create a new OAuth 2.0 Client ID
5. Add your domain to authorized origins:
   - `http://localhost:3000` (for development)
   - Your production frontend URL
6. Copy the Client ID to your environment files

### 4. Email Configuration (Optional)

For email verification to work, configure SMTP settings:

1. Use Gmail with App Passwords:
   - Go to Google Account settings
   - Enable 2-factor authentication
   - Generate an App Password
   - Use this password in `EMAIL_PASSWORD`

2. Or use another SMTP provider and adjust the settings accordingly

### 5. Run the Backend

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## Frontend Setup

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Environment Configuration

Copy `frontend/env.example` to `frontend/.env` and configure:

```bash
# Google OAuth Configuration
REACT_APP_GOOGLE_CLIENT_ID=your-google-oauth-client-id
```

Use the same Google Client ID from the backend setup.

### 3. Run the Frontend

```bash
npm start
```

## Database Schema

The authentication system creates the following tables:

### users
- `id` (UUID, Primary Key)
- `email` (String, Unique, Required)
- `hashed_password` (String, Nullable for Google OAuth users)
- `full_name` (String, Optional)
- `is_active` (Boolean, Default: True)
- `is_verified` (Boolean, Default: False)
- `google_id` (String, Unique, Nullable)
- `created_at` (DateTime)
- `updated_at` (DateTime)

### email_verifications
- `id` (UUID, Primary Key)
- `user_id` (String, Foreign Key to users.id)
- `verification_code` (String, 6-digit code)
- `expires_at` (DateTime, 15 minutes from creation)
- `is_used` (Boolean, Default: False)
- `created_at` (DateTime)

### history (Updated)
- `id` (UUID, Primary Key)
- `message_type` (String: 'user' or 'bot')
- `content` (String)
- `user_id` (String, Nullable, Foreign Key to users.id)
- `created_at` (DateTime)

## API Endpoints

### Authentication
- `POST /auth/register` - Register with email/password
- `POST /auth/login` - Login with email/password
- `POST /auth/google` - Login with Google OAuth token
- `POST /auth/verify-email` - Verify email with code
- `POST /auth/resend-verification` - Resend verification code
- `GET /auth/me` - Get current user info (requires authentication)

### WebSocket
- `WS /ws` - Chat WebSocket (supports optional token authentication via query parameter)

## Usage Flow

### 1. Registration with Email/Password
1. User fills registration form
2. System creates user account (unverified)
3. Verification email sent with 6-digit code
4. User enters code to verify email
5. User can now login

### 2. Google OAuth
1. User clicks "Sign in with Google"
2. Google OAuth flow completes
3. System creates/links user account (pre-verified)
4. User is automatically logged in

### 3. Chat Authentication
1. Authenticated users can access chat
2. JWT token passed to WebSocket for user identification
3. Chat history saved per user
4. Unauthenticated users see login prompt

## Security Features

- **Password Hashing**: Uses bcrypt for secure password storage
- **JWT Tokens**: Secure authentication tokens with expiration
- **Email Verification**: Prevents fake email registrations
- **CORS Protection**: Configured allowed origins
- **Input Validation**: Pydantic models for request validation
- **Rate Limiting**: Built-in protection against abuse

## Development Tips

1. **Testing Email**: Use a service like [Mailtrap](https://mailtrap.io/) for development
2. **Google OAuth**: Test with multiple Google accounts
3. **Database**: Use PostgreSQL locally or the provided remote instance
4. **Debugging**: Check browser console and backend logs for issues

## Production Deployment

1. **Environment Variables**: Set all production values
2. **HTTPS**: Ensure SSL certificates for OAuth
3. **Database**: Use a production PostgreSQL instance
4. **Email**: Configure production SMTP service
5. **Secrets**: Generate strong JWT secret keys

## Troubleshooting

### Common Issues

1. **Google OAuth fails**: Check client ID and authorized origins
2. **Email not sending**: Verify SMTP credentials and settings
3. **Database connection fails**: Check DATABASE_URL and network access
4. **CORS errors**: Verify ALLOWED_ORIGINS includes your frontend URL
5. **Token expiry**: JWT tokens expire after 30 minutes by default

### Error Messages

- "Email not verified": User needs to complete email verification
- "Invalid credentials": Wrong email/password combination
- "User already exists": Email already registered
- "Invalid verification code": Code expired or incorrect

For additional help, check the backend logs and browser console for detailed error messages. 