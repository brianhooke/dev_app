"""
Management command to seed default Australian public holidays.
Usage: python manage.py seed_public_holidays
"""

from django.core.management.base import BaseCommand
from core.models import PublicHolidayCalendar, PublicHoliday
from datetime import date


class Command(BaseCommand):
    help = 'Seed default Australian public holidays for 2026'

    def handle(self, *args, **options):
        # National holidays for 2026
        national_holidays = [
            {'date': date(2026, 1, 1), 'name': "New Year's Day"},
            {'date': date(2026, 1, 26), 'name': 'Australia Day'},
            {'date': date(2026, 4, 3), 'name': 'Good Friday'},
            {'date': date(2026, 4, 4), 'name': 'Easter Saturday'},
            {'date': date(2026, 4, 6), 'name': 'Easter Monday'},
            {'date': date(2026, 4, 25), 'name': 'Anzac Day'},
            {'date': date(2026, 6, 8), 'name': "Queen's Birthday"},
            {'date': date(2026, 12, 25), 'name': 'Christmas Day'},
            {'date': date(2026, 12, 26), 'name': 'Boxing Day'},
            # 2027 holidays
            {'date': date(2027, 1, 1), 'name': "New Year's Day"},
            {'date': date(2027, 1, 26), 'name': 'Australia Day'},
            {'date': date(2027, 3, 26), 'name': 'Good Friday'},
            {'date': date(2027, 3, 27), 'name': 'Easter Saturday'},
            {'date': date(2027, 3, 29), 'name': 'Easter Monday'},
            {'date': date(2027, 4, 25), 'name': 'Anzac Day (observed Monday)'},
            {'date': date(2027, 6, 14), 'name': "Queen's Birthday"},
            {'date': date(2027, 12, 25), 'name': 'Christmas Day'},
            {'date': date(2027, 12, 26), 'name': 'Boxing Day (observed Monday)'},
            {'date': date(2027, 12, 27), 'name': 'Christmas Day (observed)'},
        ]

        # NSW specific holidays
        nsw_holidays = [
            {'date': date(2026, 8, 3), 'name': 'Bank Holiday'},
            {'date': date(2027, 8, 2), 'name': 'Bank Holiday'},
        ]

        # VIC specific holidays  
        vic_holidays = [
            {'date': date(2026, 3, 9), 'name': 'Labour Day'},
            {'date': date(2026, 11, 3), 'name': 'Melbourne Cup Day'},
            {'date': date(2027, 3, 8), 'name': 'Labour Day'},
            {'date': date(2027, 11, 2), 'name': 'Melbourne Cup Day'},
        ]

        # Create or get National calendar
        nat_calendar, created = PublicHolidayCalendar.objects.get_or_create(
            name='National Public Holidays',
            defaults={'state': 'NAT', 'is_default': 1}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created calendar: {nat_calendar.name}'))
        else:
            self.stdout.write(f'Calendar exists: {nat_calendar.name}')

        # Add national holidays
        for h in national_holidays:
            holiday, created = PublicHoliday.objects.get_or_create(
                calendar=nat_calendar,
                date=h['date'],
                defaults={'name': h['name']}
            )
            if created:
                self.stdout.write(f'  Added: {h["name"]} ({h["date"]})')

        # Create or get NSW calendar
        nsw_calendar, created = PublicHolidayCalendar.objects.get_or_create(
            name='NSW Public Holidays',
            defaults={'state': 'NSW', 'is_default': 0}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created calendar: {nsw_calendar.name}'))
        else:
            self.stdout.write(f'Calendar exists: {nsw_calendar.name}')

        # Add NSW holidays (national + NSW specific)
        for h in national_holidays + nsw_holidays:
            holiday, created = PublicHoliday.objects.get_or_create(
                calendar=nsw_calendar,
                date=h['date'],
                defaults={'name': h['name']}
            )
            if created:
                self.stdout.write(f'  Added: {h["name"]} ({h["date"]})')

        # Create or get VIC calendar
        vic_calendar, created = PublicHolidayCalendar.objects.get_or_create(
            name='VIC Public Holidays',
            defaults={'state': 'VIC', 'is_default': 0}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created calendar: {vic_calendar.name}'))
        else:
            self.stdout.write(f'Calendar exists: {vic_calendar.name}')

        # Add VIC holidays (national + VIC specific)
        for h in national_holidays + vic_holidays:
            holiday, created = PublicHoliday.objects.get_or_create(
                calendar=vic_calendar,
                date=h['date'],
                defaults={'name': h['name']}
            )
            if created:
                self.stdout.write(f'  Added: {h["name"]} ({h["date"]})')

        self.stdout.write(self.style.SUCCESS('Public holidays seeded successfully!'))
