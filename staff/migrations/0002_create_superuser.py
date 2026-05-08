from django.db import migrations


def create_superuser(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    if not User.objects.filter(email='admin@example.com').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'Adminpass123')


class Migration(migrations.Migration):

    dependencies = [
        ('staff', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_superuser),
    ]
