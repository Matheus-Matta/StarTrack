# Generated by Django 5.2 on 2025-06-02 10:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tmsapp', '0019_rename_route_area_historicalroutecompositiondelivery_route_areas_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='historicalroutecompositiondelivery',
            old_name='route_areas',
            new_name='route_area',
        ),
        migrations.RenameField(
            model_name='routecompositiondelivery',
            old_name='route_areas',
            new_name='route_area',
        ),
    ]
