import os
import json
import requests
from typing import Dict, List, Any, Optional
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()  
# Create MCP server
mcp = FastMCP("Notion")

# Notion API base URL
NOTION_BASE_URL = "https://api.notion.com/v1"
    
def get_notion_headers() -> Dict[str, str]:
    """Get headers for Notion API requests"""
    api_key = os.getenv("NOTION_KEY")
    if not api_key:
        raise ValueError("NOTION_KEY environment variable not set")
    
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

def make_notion_request(method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
    """Make a request to Notion API"""
    url = f"{NOTION_BASE_URL}/{endpoint}"
    headers = get_notion_headers()
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=data)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data)
        elif method.upper() == "PATCH":
            response = requests.patch(url, headers=headers, json=data)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e), "status_code": getattr(e.response, 'status_code', None)}

# TOOLS - The actual functionality

@mcp.tool()
def search_notion(query: str, filter_type: str = "page") -> Dict:
    """
    Search across all Notion content
    
    Args:
        query: Search query string
        filter_type: Type to filter by ("page", "database", or "all")
    """
    search_data = {
        "query": query,
        "sort": {
            "direction": "descending",
            "timestamp": "last_edited_time"
        }
    }
    
    if filter_type != "all":
        search_data["filter"] = {"value": filter_type, "property": "object"}
    
    return make_notion_request("POST", "search", search_data)

@mcp.tool()
def get_databases() -> Dict:
    """List all databases accessible to the integration"""
    # Search for databases specifically
    search_data = {
        "filter": {"value": "database", "property": "object"},
        "sort": {"direction": "descending", "timestamp": "last_edited_time"}
    }
    return make_notion_request("POST", "search", search_data)

@mcp.tool()
def get_database_schema(database_id: str) -> Dict:
    """Get database structure and properties"""
    return make_notion_request("GET", f"databases/{database_id}")

@mcp.tool()
def query_database(database_id: str, filter_conditions: Optional[Dict] = None, 
                  sorts: Optional[List[Dict]] = None, page_size: int = 100) -> Dict:
    """
    Query a database with filters and sorting
    
    Args:
        database_id: The database ID
        filter_conditions: Notion filter object (optional)
        sorts: List of sort objects (optional)  
        page_size: Number of results per page (max 100)
    """
    query_data = {"page_size": min(page_size, 100)}
    
    if filter_conditions:
        query_data["filter"] = filter_conditions
    if sorts:
        query_data["sorts"] = sorts
        
    return make_notion_request("POST", f"databases/{database_id}/query", query_data)

@mcp.tool()
def create_database_entry(database_id: str, properties: Dict) -> Dict:
    """
    Create a new entry in a database
    
    Args:
        database_id: The database ID
        properties: Property values for the new page
    """
    page_data = {
        "parent": {"database_id": database_id},
        "properties": properties
    }
    return make_notion_request("POST", "pages", page_data)

@mcp.tool()
def get_page(page_id: str) -> Dict:
    """Get page metadata and properties"""
    return make_notion_request("GET", f"pages/{page_id}")

@mcp.tool()
def get_page_content(page_id: str) -> Dict:
    """Get page content (blocks)"""
    return make_notion_request("GET", f"blocks/{page_id}/children")

@mcp.tool()
def update_page(page_id: str, properties: Dict) -> Dict:
    """
    Update page properties
    
    Args:
        page_id: The page ID
        properties: Properties to update
    """
    return make_notion_request("PATCH", f"pages/{page_id}", {"properties": properties})

@mcp.tool()
def create_page(parent_id: str, title: str, content_blocks: Optional[List[Dict]] = None) -> Dict:
    """
    Create a new page
    
    Args:
        parent_id: Parent page or database ID
        title: Page title
        content_blocks: List of block objects for page content
    """
    page_data = {
        "parent": {"page_id": parent_id},
        "properties": {
            "title": {
                "title": [{"text": {"content": title}}]
            }
        }
    }
    
    if content_blocks:
        page_data["children"] = content_blocks
        
    return make_notion_request("POST", "pages", page_data)

@mcp.tool()
def add_blocks_to_page(page_id: str, blocks: List[Dict]) -> Dict:
    """
    Add content blocks to a page
    
    Args:
        page_id: The page ID
        blocks: List of block objects to add
    """
    return make_notion_request("PATCH", f"blocks/{page_id}/children", {"children": blocks})

@mcp.tool()
def get_users() -> Dict:
    """List all users in the workspace"""
    return make_notion_request("GET", "users")

@mcp.tool()
def get_user(user_id: str) -> Dict:
    """Get user details"""
    return make_notion_request("GET", f"users/{user_id}")

# RESOURCES - For browsing and discovery

@mcp.resource("notion://databases")
def list_databases() -> str:
    """List all accessible databases"""
    result = get_databases()
    if "error" in result:
        return f"Error: {result['error']}"
    
    databases = result.get("results", [])
    output = "=== Notion Databases ===\n\n"
    
    for db in databases:
        title = "Untitled"
        if db.get("title") and len(db["title"]) > 0:
            title = db["title"][0]["plain_text"]
        
        output += f"• {title}\n"
        output += f"  ID: {db['id']}\n"
        output += f"  URL: {db['url']}\n"
        output += f"  Last edited: {db['last_edited_time']}\n\n"
    
    return output

@mcp.resource("notion://database/{database_id}")
def get_database_info(database_id: str) -> str:
    """Get detailed database information"""
    result = get_database_schema(database_id)
    if "error" in result:
        return f"Error: {result['error']}"
    
    title = "Untitled Database"
    if result.get("title") and len(result["title"]) > 0:
        title = result["title"][0]["plain_text"]
    
    output = f"=== {title} ===\n\n"
    output += f"ID: {result['id']}\n"
    output += f"URL: {result['url']}\n"
    output += f"Created: {result['created_time']}\n"
    output += f"Last edited: {result['last_edited_time']}\n\n"
    
    output += "Properties:\n"
    for prop_name, prop_data in result.get("properties", {}).items():
        prop_type = prop_data.get("type", "unknown")
        output += f"  • {prop_name} ({prop_type})\n"
    
    return output

@mcp.resource("notion://page/{page_id}")
def get_page_info(page_id: str) -> str:
    """Get page information and content"""
    page_result = get_page(page_id)
    if "error" in page_result:
        return f"Error: {page_result['error']}"
    
    content_result = get_page_content(page_id)
    
    # Get page title
    title = "Untitled Page"
    properties = page_result.get("properties", {})
    for prop_name, prop_data in properties.items():
        if prop_data.get("type") == "title" and prop_data.get("title"):
            title = prop_data["title"][0]["plain_text"]
            break
    
    output = f"=== {title} ===\n\n"
    output += f"ID: {page_result['id']}\n"
    output += f"URL: {page_result['url']}\n"
    output += f"Created: {page_result['created_time']}\n"
    output += f"Last edited: {page_result['last_edited_time']}\n\n"
    
    # Add content blocks summary
    if not content_result.get("error"):
        blocks = content_result.get("results", [])
        output += f"Content blocks: {len(blocks)}\n\n"
        
        # Show first few blocks
        for i, block in enumerate(blocks[:5]):
            block_type = block.get("type", "unknown")
            output += f"Block {i+1}: {block_type}\n"
            
            # Try to get text content
            if block_type in ["paragraph", "heading_1", "heading_2", "heading_3"]:
                text_content = block.get(block_type, {}).get("rich_text", [])
                if text_content:
                    text = text_content[0].get("plain_text", "")[:100]
                    if len(text) == 100:
                        text += "..."
                    output += f"  {text}\n"
        
        if len(blocks) > 5:
            output += f"... and {len(blocks) - 5} more blocks\n"
    
    return output


if __name__ == "__main__":
    mcp.run(transport='sse')
