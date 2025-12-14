from mcp.server.fastmcp import FastMCP
import requests

# Notion configuration
NOTION_API_KEY = "ntn_V94857732233a5ask89TSpDxnnWGnxc1WsHLqUekfnFeyK"
NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json"
}

def call_notion(path: str, method: str = "GET", json: dict = None):
    url = f"{BASE_URL}{path}"
    response = requests.request(method, url, headers=headers, json=json)
    response.raise_for_status()
    return response.json()

# Create an MCP server for Notion
mcp = FastMCP("notion", port=8080)

@mcp.tool()
def list_databases() -> dict:
    """List all databases"""
    return call_notion("/databases")

@mcp.resource("database://{database_id}")
def get_database(database_id: str) -> dict:
    """Retrieve a database by ID"""
    return call_notion(f"/databases/{database_id}")

@mcp.tool()
def query_database(database_id: str, query: dict = None) -> dict:
    """Query a database with optional filters/sorts"""
    return call_notion(f"/databases/{database_id}/query", method="POST", json=query or {})

@mcp.tool()
def search(query: str, filter: dict = None) -> dict:
    """Search across workspace"""
    payload = {"query": query}
    if filter:
        payload["filter"] = filter
    return call_notion("/search", method="POST", json=payload)

@mcp.resource("page://{page_id}")
def get_page(page_id: str) -> dict:
    """Retrieve a page by ID"""
    return call_notion(f"/pages/{page_id}")

@mcp.tool()
def create_page(parent_database_id: str, properties: dict, children: list = None) -> dict:
    """Create a new page in a database"""
    payload = {
        "parent": {"database_id": parent_database_id},
        "properties": properties
    }
    if children:
        payload["children"] = children
    return call_notion("/pages", method="POST", json=payload)

@mcp.tool()
def update_page(page_id: str, properties: dict) -> dict:
    """Update properties of an existing page"""
    return call_notion(f"/pages/{page_id}", method="PATCH", json={"properties": properties})

@mcp.tool()
def get_block_children(block_id: str) -> dict:
    """Retrieve children of a block"""
    return call_notion(f"/blocks/{block_id}/children")

@mcp.tool()
def append_block(block_id: str, children: list) -> dict:
    """Append children to a block"""
    return call_notion(f"/blocks/{block_id}/children", method="PATCH", json={"children": children})

if __name__ == "__main__":
    mcp.run(transport='sse')