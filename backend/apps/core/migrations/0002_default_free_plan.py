from django.db import migrations


def create_free_plan(apps, schema_editor):
    Plan = apps.get_model("core", "Plan")
    Plan.objects.get_or_create(code="free", defaults={"name": "Free", "is_default": True, "daily_limits": {}, "monthly_price_inr": 0})


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(create_free_plan, migrations.RunPython.noop)]
