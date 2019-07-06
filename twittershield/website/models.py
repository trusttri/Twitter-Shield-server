from django.db import models

# Create your models here.

class TwitterAccount(models.Model):
	id = models.AutoField(primary_key=True)
	screen_name = models.TextField()

	toxicity_score = models.FloatField(null=True)
	identity_attack_score = models.FloatField(null=True)
	insult_score = models.FloatField(null=True)
	profanity_score = models.FloatField(null=True)
	threat_score = models.FloatField(null=True)
	sexually_explicit_score = models.FloatField(null=True)
	flirtation_score = models.FloatField(null=True)

	recent_tweet_count = models.IntegerField(default=0)

	stored_at = models.DateTimeField(null=True)


class Tweet(models.Model):
	id = models.AutoField(primary_key=True)
	twitter_account = models.ForeignKey('TwitterAccount', on_delete=models.PROTECT)

	tweet_time = models.DateTimeField(null=True)

	cleaned_text = models.TextField()
	original_text = models.TextField()

	toxicity_score = models.FloatField(null=True)
	identity_attack_score = models.FloatField(null=True)
	insult_score = models.FloatField(null=True)
	profanity_score = models.FloatField(null=True)
	threat_score = models.FloatField(null=True)
	sexually_explicit_score = models.FloatField(null=True)
	flirtation_score = models.FloatField(null=True)