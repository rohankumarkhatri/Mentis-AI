import json
import datetime
import uuid

# Global variable to store mobile app connection
mobile_connection = None

def set_mobile_connection(connection):
    """Set the mobile app TCP connection"""
    global mobile_connection
    mobile_connection = connection

def send_to_mobile_app(tcp_connection, data):
    """Send confirmation data to mobile app via TCP"""
    try:
        if tcp_connection:
            message = json.dumps(data)
            tcp_connection.sendall(message.encode('utf-8'))
            print(f"Sent confirmation to mobile app: {data['type']} - {data['id']}")
            return True
        else:
            print("No TCP connection available to send to mobile app")
            return False
    except Exception as e:
        print(f"Failed to send to mobile app: {e}")
        return False

def handle_email_confirmation_call(arguments):
    """Handle email confirmation request"""
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
        
        # Generate unique ID for this request
        request_id = str(uuid.uuid4())[:8]
        
        # Prepare data for mobile app
        email_data = {
            "type": "email_confirmation",
            "id": request_id,
            "to_email": args.get("to_email"),
            "from_email": args.get("from_email", ""),
            "subject": args.get("subject"),
            "body": args.get("body"),
            "cc": args.get("cc", ""),
            "bcc": args.get("bcc", ""),
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        print(f"Preparing to send email confirmation: {email_data}")
        # Send to mobile app if connection exists
        if mobile_connection:
            send_to_mobile_app(mobile_connection, email_data)
        
        return {
            "status": "confirmation_sent",
            "message": f"Email confirmation sent to mobile app for approval (ID: {request_id})",
            "data": email_data
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to process email confirmation: {str(e)}"
        }

def handle_calendar_confirmation_call(arguments):
    """Handle calendar confirmation request"""
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
        
        # Generate unique ID for this request
        request_id = str(uuid.uuid4())[:8]
        
        # Prepare data for mobile app
        calendar_data = {
            "type": "calendar_confirmation",
            "id": request_id,
            "event_title": args.get("event_title"),
            "event_date": args.get("event_date"),
            "event_time": args.get("event_time", ""),
            "description": args.get("description", ""),
            "location": args.get("location", ""),
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Send to mobile app if connection exists
        if mobile_connection:
            send_to_mobile_app(mobile_connection, calendar_data)
        
        return {
            "status": "confirmation_sent",
            "message": f"Calendar confirmation sent to mobile app for approval (ID: {request_id})",
            "data": calendar_data
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to process calendar confirmation: {str(e)}"
        }
