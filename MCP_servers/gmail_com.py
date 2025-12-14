# gmail_server.py
import os
import json
import base64
from typing import List, Dict, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from mcp.server.fastmcp import FastMCP
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Gmail API scopes - full access
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.labels'
]

# Create MCP server
mcp = FastMCP("Gmail")

class GmailService:
    def __init__(self):
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Gmail API"""
        creds = None
        
        # Token file stores the user's access and refresh tokens
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    raise FileNotFoundError(
                        "credentials.json not found. Please download it from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('gmail', 'v1', credentials=creds)

# Initialize Gmail service
gmail_service = GmailService()

@mcp.tool()
def get_messages(query: str = "", max_results: int = 10, label_ids: List[str] = None) -> Dict[str, Any]:
    """
    Get Gmail messages with optional search query and filters
    
    Args:
        query: Gmail search query (e.g., "from:example@gmail.com", "is:unread", "subject:hello")
        max_results: Maximum number of messages to return (default 10)
        label_ids: List of label IDs to filter by (optional)
    """
    try:
        # Get list of messages
        results = gmail_service.service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results,
            labelIds=label_ids
        ).execute()
        
        messages = results.get('messages', [])
        
        # Get full message details
        detailed_messages = []
        for msg in messages:
            message = gmail_service.service.users().messages().get(
                userId='me', 
                id=msg['id']
            ).execute()
            
            # Extract useful information
            headers = message['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
            
            # Get message body
            body = ""
            if 'parts' in message['payload']:
                for part in message['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        if 'data' in part['body']:
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
            else:
                if message['payload']['body'].get('data'):
                    body = base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8')
            
            detailed_messages.append({
                'id': message['id'],
                'thread_id': message['threadId'],
                'subject': subject,
                'from': sender,
                'date': date,
                'snippet': message['snippet'],
                'body': body[:500] + "..." if len(body) > 500 else body,
                'labels': message.get('labelIds', [])
            })
        
        return {
            'messages': detailed_messages,
            'total_found': len(detailed_messages)
        }
        
    except HttpError as error:
        return {'error': f'An error occurred: {error}'}

@mcp.tool()
def send_email(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> Dict[str, Any]:
    """
    Send an email via Gmail
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body content
        cc: CC recipients (comma-separated, optional)
        bcc: BCC recipients (comma-separated, optional)
    """
    try:
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        
        if cc:
            message['cc'] = cc
        if bcc:
            message['bcc'] = bcc
        
        # Encode message
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Send message
        result = gmail_service.service.users().messages().send(
            userId='me',
            body={'raw': raw}
        ).execute()
        
        return {
            'success': True,
            'message_id': result['id'],
            'message': 'Email sent successfully'
        }
        
    except HttpError as error:
        return {'error': f'An error occurred: {error}', 'success': False}

@mcp.tool()
def get_labels() -> Dict[str, Any]:
    """Get all Gmail labels"""
    try:
        results = gmail_service.service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        
        return {
            'labels': [{'id': label['id'], 'name': label['name']} for label in labels]
        }
        
    except HttpError as error:
        return {'error': f'An error occurred: {error}'}

@mcp.tool()
def mark_as_read(message_ids: List[str]) -> Dict[str, Any]:
    """
    Mark messages as read
    
    Args:
        message_ids: List of message IDs to mark as read
    """
    try:
        for msg_id in message_ids:
            gmail_service.service.users().messages().modify(
                userId='me',
                id=msg_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
        
        return {
            'success': True,
            'message': f'Marked {len(message_ids)} message(s) as read'
        }
        
    except HttpError as error:
        return {'error': f'An error occurred: {error}', 'success': False}

@mcp.tool()
def mark_as_unread(message_ids: List[str]) -> Dict[str, Any]:
    """
    Mark messages as unread
    
    Args:
        message_ids: List of message IDs to mark as unread
    """
    try:
        for msg_id in message_ids:
            gmail_service.service.users().messages().modify(
                userId='me',
                id=msg_id,
                body={'addLabelIds': ['UNREAD']}
            ).execute()
        
        return {
            'success': True,
            'message': f'Marked {len(message_ids)} message(s) as unread'
        }
        
    except HttpError as error:
        return {'error': f'An error occurred: {error}', 'success': False}

@mcp.tool()
def delete_messages(message_ids: List[str]) -> Dict[str, Any]:
    """
    Delete messages (move to trash)
    
    Args:
        message_ids: List of message IDs to delete
    """
    try:
        for msg_id in message_ids:
            gmail_service.service.users().messages().trash(
                userId='me',
                id=msg_id
            ).execute()
        
        return {
            'success': True,
            'message': f'Deleted {len(message_ids)} message(s)'
        }
        
    except HttpError as error:
        return {'error': f'An error occurred: {error}', 'success': False}

@mcp.tool()
def search_emails(query: str, max_results: int = 20) -> Dict[str, Any]:
    """
    Search emails with Gmail search syntax
    
    Args:
        query: Search query (e.g., "from:someone@example.com", "subject:important", "is:unread")
        max_results: Maximum number of results
    
    Common search examples:
    - "is:unread" - unread emails
    - "from:email@example.com" - emails from specific sender
    - "subject:meeting" - emails with "meeting" in subject
    - "has:attachment" - emails with attachments
    - "after:2024/1/1" - emails after specific date
    """
    return get_messages(query=query, max_results=max_results)

@mcp.tool()
def get_thread(thread_id: str) -> Dict[str, Any]:
    """
    Get full email thread/conversation
    
    Args:
        thread_id: Gmail thread ID
    """
    try:
        thread = gmail_service.service.users().threads().get(
            userId='me',
            id=thread_id
        ).execute()
        
        messages = []
        for message in thread['messages']:
            headers = message['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
            
            # Get message body
            body = ""
            if 'parts' in message['payload']:
                for part in message['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        if 'data' in part['body']:
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
            else:
                if message['payload']['body'].get('data'):
                    body = base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8')
            
            messages.append({
                'id': message['id'],
                'subject': subject,
                'from': sender,
                'date': date,
                'snippet': message['snippet'],
                'body': body
            })
        
        return {
            'thread_id': thread_id,
            'messages': messages,
            'message_count': len(messages)
        }
        
    except HttpError as error:
        return {'error': f'An error occurred: {error}'}

# Resource for getting a specific email
@mcp.resource("gmail://message/{message_id}")
def get_email_content(message_id: str) -> str:
    """Get full content of a specific email message"""
    try:
        message = gmail_service.service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()
        
        headers = message['payload'].get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
        
        # Get full message body
        body = ""
        if 'parts' in message['payload']:
            for part in message['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    break
        else:
            if message['payload']['body'].get('data'):
                body = base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8')
        
        return f"""Email Details:
Subject: {subject}
From: {sender}
Date: {date}
Message ID: {message_id}

Body:
{body}
"""
        
    except HttpError as error:
        return f'Error retrieving email: {error}'

if __name__ == "__main__":
    mcp.run(transport='stdio')