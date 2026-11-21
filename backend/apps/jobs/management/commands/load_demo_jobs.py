"""Load clearly-labelled FICTIONAL jobs so the UI can be tried offline. These are not real openings."""
from django.core.management.base import BaseCommand

from apps.jobs import ingest


class Command(BaseCommand):
    help = "Load fictional demo jobs (source 'demo'). Safe to run repeatedly."

    def handle(self, *args, **opts):
        stats = ingest.load_demo_jobs()
        self.stdout.write(self.style.SUCCESS(f"Demo jobs loaded: {stats}. They are fictional and have no application page."))
