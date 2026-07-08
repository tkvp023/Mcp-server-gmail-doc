import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_mcp_server():
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "src.server"]
    )

    print("Starting MCP Client and connecting to server...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Connected to MCP Server!\n")
            
            # --- Test 1: Send Email ---
            email_to = "tkvp023@gmail.com"
            print(f"--- Testing Tool: gmail_send_email (to {email_to}) ---")
            
            try:
                email_result = await session.call_tool(
                    "gmail_send_email", 
                    arguments={
                        "to": email_to,
                        "subject": "Test from MCP Server", 
                        "body": "Hello! This is an automated test verifying the gmail_send_email tool."
                    }
                )
                if hasattr(email_result, 'content') and len(email_result.content) > 0:
                    print(f"Email Result: {email_result.content[0].text}\n")
                else:
                    print(f"Email Result: {email_result}\n")
            except Exception as e:
                print(f"Error calling gmail_send_email: {e}\n")

            # --- Test 2: Append to Google Doc ---
            doc_id = "1KBki1sBZX5ZpatCZFGzTEK_euW8KRyBIcijb4p-HegM"
            print(f"--- Testing Tool: gdoc_append_content (Doc ID: {doc_id}) ---")
            
            try:
                doc_result = await session.call_tool(
                    "gdoc_append_content", 
                    arguments={
                        "document_id": doc_id,
                        "content": "This line was appended automatically by the MCP server test script!",
                        "add_newline_before": True
                    }
                )
                if hasattr(doc_result, 'content') and len(doc_result.content) > 0:
                    print(f"Doc Result: {doc_result.content[0].text}\n")
                else:
                    print(f"Doc Result: {doc_result}\n")
            except Exception as e:
                print(f"Error calling gdoc_append_content: {e}\n")

if __name__ == "__main__":
    asyncio.run(test_mcp_server())
