"""
Management command: compute_study_patterns
==========================================
Nightly batch that recomputes StudyPattern for every active user.

Usage:
    python manage.py compute_study_patterns
    python manage.py compute_study_patterns --user-id 42
    python manage.py compute_study_patterns --batch-size 50
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Compute (or refresh) peak study-time patterns for all users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            default=None,
            help="Process a single user only.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of users to process per batch (default 100).",
        )

    def handle(self, *args, **options):
        from analytics.ml.study_time import compute_pattern

        single_id  = options["user_id"]
        batch_size = options["batch_size"]

        if single_id:
            qs = User.objects.filter(pk=single_id)
        else:
            qs = User.objects.filter(is_active=True).order_by("id")

        total   = qs.count()
        ok = err = 0

        self.stdout.write(f"Processing {total} user(s) in batches of {batch_size}…")

        for offset in range(0, total, batch_size):
            batch = qs[offset : offset + batch_size]
            for user in batch:
                try:
                    pattern = compute_pattern(user.id)
                    if pattern:
                        ok += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✓ {user.username} — conf={pattern.confidence:.2f}"
                                f"  peak={pattern.peak_hour_start}–{pattern.peak_hour_end}h"
                            )
                        )
                    else:
                        err += 1
                        self.stdout.write(self.style.WARNING(f"  ⚠ {user.username} — returned None"))
                except Exception as exc:
                    err += 1
                    self.stdout.write(self.style.ERROR(f"  ✗ {user.username} — {exc}"))

        self.stdout.write(f"\nDone. {ok} succeeded, {err} failed.")
