import os
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
import uvicorn

async def homepage(request):
    port = os.getenv("PORT", "not_set")
    return JSONResponse({
        "status": "test_app_is_running",
        "PORT_env": port,
        "listening_on": 8000
    })

app = Starlette(debug=True, routes=[
    Route('/', homepage),
    Route('/sse', homepage),
])

if __name__ == "__main__":
    # Hardcode port 8000 to match Railway networking config
    uvicorn.run(app, host="0.0.0.0", port=8000)
