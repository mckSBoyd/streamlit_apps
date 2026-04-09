import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(page_title="Email Sender", page_icon="📧")
st.title("📧 Email Sender")

# --- Configuration ---
# Fill in your SMTP details here or use st.secrets in production
SMTP_SERVER = "smtp.gmail.com"  # Change if using Outlook, Yahoo, etc.
SMTP_PORT = 587
SENDER_EMAIL = "swilerboyd2019@gmail.com"       # <-- Replace with your email
SENDER_PASSWORD = "porc ptvz zbko tjxc"        # <-- Replace with your App Password

# --- UI ---
recipient = st.text_input("Recipient Email", placeholder="sboyd@mckinneytexas.org")
subject = st.text_input("Testing Streamlit", value="Test Email from Stream#lit")
body = st.text_area("Message", value="Hello! This email was sent from a Streamlit app.")

# --- Send Logic ---
if st.button("Send Email ✉️"):
    if not recipient:
        st.error("Please enter a recipient email address.")
    else:
        try:
            msg = MIMEMultipart()
            msg["From"] = SENDER_EMAIL
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)

            st.success(f"Email sent to {recipient}!")
        except Exception as e:
            st.error(f"Failed to send email: {e}")

# --- Notes ---
st.divider()
st.caption(
    "**Setup:** Replace `SENDER_EMAIL` and `SENDER_PASSWORD` at the top of the script. "
    "For Gmail, use an [App Password](https://myaccount.google.com/apppasswords) (not your regular password)."
)
