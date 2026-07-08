import os
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
import uvicorn

async def homepage(request):
    return JSONResponse({"status": "test_app_is_running"})

app = Starlette(debug=True, routes=[
    Route('/', homepage),
    Route('/sse', homepage),
])

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
