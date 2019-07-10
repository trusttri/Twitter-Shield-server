# Generated by Django 2.2.3 on 2019-07-05 21:52

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='TwitterAccount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('screen_name', models.TextField()),
                ('toxicity_score', models.FloatField(null=True)),
                ('recent_tweet_count', models.IntegerField(default=0)),
            ],
        ),
    ]