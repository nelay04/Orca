import os
import uvicorn
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Start the Uvicorn ASGI server (reads HOST, PORT, RELOAD from .env)"

    def add_arguments(self, parser):
        parser.add_argument("--host", default=None, help="Bind host (overrides HOST in .env)")
        parser.add_argument("--port", type=int, default=None, help="Bind port (overrides PORT in .env)")
        parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")

    def handle(self, *args, **options):
        host = options["host"] or os.environ.get("HOST", "127.0.0.1")
        port = options["port"] or int(os.environ.get("PORT", 8000))
        debug = os.environ.get("DEBUG", "True").lower() in ("true", "1", "yes")
        reload = not options["no_reload"] and debug

        self.stdout.write(
            self.style.SUCCESS(f"Starting ASGI server at http://{host}:{port}/ (reload={reload})")
        )

        uvicorn.run(
            "orca.asgi:application",
            host=host,
            port=port,
            reload=reload,
        )
