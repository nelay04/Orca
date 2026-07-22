from django.core.management.base import BaseCommand

from db_connection import ensure_indexes


class Command(BaseCommand):
    help = "Create the MongoDB indexes the app depends on. Safe to re-run."

    def handle(self, *args, **options):
        self.stdout.write("Creating MongoDB indexes...")
        ensure_indexes()
        self.stdout.write(self.style.SUCCESS("MongoDB indexes are in place."))
