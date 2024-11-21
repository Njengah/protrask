from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import jwt
from datetime import datetime, timedelta
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from db import User, SessionLocal  # Import the User model and session from db.py
from passlib.context import CryptContext  # For password hashing
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware to allow requests from the frontend (Next.js on port 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow only the Next.js frontend
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

SECRET_KEY = "your-secret-key"  # Replace with your actual secret key
ALGORITHM = "HS256"  # JWT encoding algorithm

# Initialize password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Pydantic model for login request
class LoginRequest(BaseModel):
    email: str
    password: str


# Pydantic model for register request
class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str


# Pydantic model for password reset request
class ResetPasswordRequest(BaseModel):
    email: str


# Pydantic model for password reset
class ResetPassword(BaseModel):
    new_password: str
    token: str


# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Hash password
def hash_password(plain_password: str):
    return pwd_context.hash(plain_password)


# Verify password
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


# Create JWT token
def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=1)):
    to_encode = data.copy()
    expiration = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expiration})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# Register endpoint
@app.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash the password before saving it
    hashed_password = hash_password(request.password)

    # Create a new user
    new_user = User(
        email=request.email, password=hashed_password, full_name=request.full_name
    )

    # Add the new user to the database
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"success": True, "message": "User registered successfully"}


# Login endpoint
@app.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    # Query the database for the user by email
    user = db.query(User).filter(User.email == request.email).first()

    if user is None or not verify_password(request.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create JWT token on successful login
    token = create_access_token({"sub": user.email})
    return {"success": True, "token": token}


# Password reset request endpoint
@app.post("/forgot-password")
def reset_password_request(
    request: ResetPasswordRequest, db: Session = Depends(get_db)
):
    try:
        # Find the user by email
        user = db.query(User).filter(User.email == request.email).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Generate a password reset token (valid for 1 hour)
        reset_token = jwt.encode(
            {"sub": user.email, "exp": datetime.utcnow() + timedelta(hours=1)},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        # Send the reset token to the user's email
        send_email(user.email, reset_token)

        return {"message": "Password reset email sent"}

    except Exception as e:
        # Log the error and raise an internal server error
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# Function to send an email (using Mailtrap SMTP)
def send_email(email: str, reset_token: str):
    # Mailtrap credentials
    SMTP_SERVER = "sandbox.smtp.mailtrap.io"
    SMTP_PORT = 587  # You can also use 25, 465, or 2525
    SMTP_USERNAME = "1cf7a9459b3a94"
    SMTP_PASSWORD = "09419734a8017b"  # Replace with the correct password

    sender_email = "joe@example.com"  # Replace with your email or use a sender address
    receiver_email = email

    # Create the email content
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = "Password Reset Request"

    # Create the email body with the reset URL
    reset_url = f"http://localhost:3000/reset-password?token={reset_token}"
    body = f"Please use the following link to reset your password:\n\n{reset_url}\n\nThis link is valid for 1 hour."
    message.attach(MIMEText(body, "plain"))

    try:
        # Connect to Mailtrap SMTP server
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Secure the connection using STARTTLS
            server.login(SMTP_USERNAME, SMTP_PASSWORD)  # Login to the server
            server.sendmail(
                sender_email, receiver_email, message.as_string()
            )  # Send email
            print(f"Password reset email sent to {email}")
    except Exception as e:
        print(f"Error sending email to {email}: {str(e)}")


# Password reset request endpoint
# @app.post("/forgot-password")
# def reset_password_request(
#     request: ResetPasswordRequest, db: Session = Depends(get_db)
# ):
#     # Find the user by email
#     user = db.query(User).filter(User.email == request.email).first()

#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")

#     # Generate a password reset token (valid for 1 hour)
#     reset_token = jwt.encode(
#         {"sub": user.email, "exp": datetime.utcnow() + timedelta(hours=1)},
#         SECRET_KEY,
#         algorithm=ALGORITHM,
#     )

#     # Send the reset token to the user's email
#     send_email(user.email, reset_token)

#     return {"message": "Password reset email sent"}


# Helper function to send email (implement your own email logic)
# def send_email(email: str, reset_token: str):
#     # This is just an example; replace it with your email provider's logic
#     sender_email = "your-email@example.com"
#     receiver_email = email
#     subject = "Password Reset Request"
#     body = f"Please click the link below to reset your password:\n\nhttp://localhost:3000/reset-password?token={reset_token}"

#     message = MIMEMultipart()
#     message["From"] = sender_email
#     message["To"] = receiver_email
#     message["Subject"] = subject
#     message.attach(MIMEText(body, "plain"))

#     # Use your email provider settings here
#     try:
#         server = smtplib.SMTP("smtp.example.com", 587)
#         server.starttls()
#         server.login(sender_email, "your-email-password")
#         text = message.as_string()
#         server.sendmail(sender_email, receiver_email, text)
#         server.quit()
#     except Exception as e:
#         raise HTTPException(status_code=500, detail="Failed to send email")


@app.post("/reset-password")
def reset_password(request: ResetPassword, db: Session = Depends(get_db)):
    # Decode the token to get the email
    try:
        payload = jwt.decode(request.token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=400, detail="Invalid token")

    # Find the user by email
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update the password
    user.password = request.new_password  # Consider hashing the password here
    db.commit()
    db.refresh(user)

    return {"message": "Password successfully updated"}
