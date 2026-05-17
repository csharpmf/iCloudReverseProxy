import json, os

from pyngrok import ngrok
import hypercorn.asyncio
from hypercorn.config import Config

async def run(
    app, 
    port=5000, 
    bind="127.0.0.1"
):
    public_url = ngrok.connect(port, bind_tls=True)
    print(f" * ngrok tunnel -> {public_url}")

    inst_path = os.path.join(
        os.path.dirname(
            __file__
        ), 
        '..', 
        'instance.json'
    )
    inst_path = os.path.abspath(
        inst_path
    )
    try:
        with open(
            inst_path, 
            'r', 
            encoding='utf-8'
        ) as f:
            conf = json.load(f)
        conf['api_url'] = public_url.public_url if hasattr(
            public_url, 
            'public_url'
        ) else str(public_url)
        with open(
            inst_path, 
            'w', 
            encoding='utf-8'
        ) as f:
            json.dump(
                conf, 
                f, 
                indent=4
            )
        # print(
        #     f"updated instance 'api_url' to -> {public_url}"
        # )
    except Exception as e:
        ...

    config = Config()
    config.bind = [
        f"{bind}:{port}"
    ]
    await hypercorn.asyncio.serve(
        app, 
        config
    )
