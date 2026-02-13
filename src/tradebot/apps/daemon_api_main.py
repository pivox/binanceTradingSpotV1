from aiohttp import web
from dotenv import load_dotenv

from tradebot.api.app import create_app
from tradebot.config.settings import Settings


def main() -> None:
    load_dotenv()
    settings = Settings()
    app = create_app(settings)
    web.run_app(app, host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    main()
