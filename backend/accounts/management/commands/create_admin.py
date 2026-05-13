"""Create an app ``ADMINISTRATOR`` (app dashboard only, not Django ``/admin/``)."""
from django.core.management.base import BaseCommand
from accounts.models import User


class Command(BaseCommand):
    help = 'Create an app administrator (not a Django superuser; no /admin/ access). Prompts for email, username, password.'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Admin email')
        parser.add_argument('--username', type=str, help='Admin username')
        parser.add_argument('--password', type=str, help='Admin password (min 8 chars)')
        parser.add_argument('--noinput', action='store_true', help='Do not prompt; require --email, --username, --password')

    def handle(self, *args, **options):
        email = options.get('email') or input('Email: ').strip()
        username = options.get('username') or input('Username: ').strip()
        password = options.get('password')
        if not password:
            from getpass import getpass
            password = getpass('Password: ')
            password_confirm = getpass('Password (again): ')
            if password != password_confirm:
                self.stderr.write(self.style.ERROR('Passwords do not match.'))
                return
        if not email or not username:
            self.stderr.write(self.style.ERROR('Email and username are required.'))
            return
        if len(password) < 8:
            self.stderr.write(self.style.ERROR('Password must be at least 8 characters.'))
            return
        if User.objects.filter(email=email).exists():
            self.stderr.write(self.style.ERROR(f'User with email "{email}" already exists.'))
            return
        if User.objects.filter(username=username).exists():
            self.stderr.write(self.style.ERROR(f'User with username "{username}" already exists.'))
            return
        user = User.objects.create_user(
            email=email,
            username=username,
            password=password,
            role='ADMINISTRATOR',
        )
        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])
        self.stdout.write(self.style.SUCCESS(f'App administrator created: {user.email} (username: {user.username})'))
        self.stdout.write(self.style.SUCCESS('This user can log in to the app admin dashboard only (not Django /admin/).'))
