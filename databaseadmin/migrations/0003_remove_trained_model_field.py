# Generated by Django 5.1.6 on 2025-04-18 09:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("databaseadmin", "0002_forecastingmodel_model_file_path_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="forecastingmodel",
            name="trained_model",
        ),
    ]
