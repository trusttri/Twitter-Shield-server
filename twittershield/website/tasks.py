from __future__ import absolute_import
from celery import shared_task, current_task
from celery.exceptions import Ignore
from website.models import TwitterAccount, Tweet
from django.contrib.auth.models import User
from website.views import get_user_timeline, clean_tweets, get_tweet_perspective_scores, get_user_perspective_score, store_tweets
from django.utils import timezone

PERSPECTIVE_MODELS = ['TOXICITY', 'IDENTITY_ATTACK', 'INSULT', 'PROFANITY','THREAT','SEXUALLY_EXPLICIT', 'FLIRTATION']
			
@shared_task
def get_score(screen_name, threshold):
	user_perspective_scores = {}
	try:

		twitter_account = TwitterAccount.objects.filter(screen_name=screen_name)
		if twitter_account.count() == 0:
			print("NEW STORE")
		
			#models user choses  + score - probably store this in db too! 
			#set default as zero in front end 

			twitter_account = TwitterAccount.objects.create(screen_name=screen_name,
															stored_at = timezone.now(),
															recent_tweet_count=0)

			models_setting_json = {}
			for model in PERSPECTIVE_MODELS:
				print(model)
				models_setting_json[model] = {'scoreThreshold': '0'}
				# if(request.GET.get(model.lower())):
				# 	models_setting_json[model] = {'scoreThreshold': request.args.get(model.lower())}
				# else:
				# 	models_setting_json[model] = {'scoreThreshold': '0'}

			#print(models_setting_json)

			tweet_count = 200
			#get tweets on user's timeline
			print('get tweets')
			user_timeline_tweets = get_user_timeline(screen_name, tweet_count)
			cleaned_user_timeline_tweets = clean_tweets(user_timeline_tweets)	


			tweets_with_perspective_scores = get_tweet_perspective_scores(cleaned_user_timeline_tweets, models_setting_json, twitter_account)
			# insert into db
			user_perspective_scores = get_user_perspective_score(tweets_with_perspective_scores)
			# insert into db
			user_perspective_scores['username'] = screen_name
			user_perspective_scores['tweets_considered_count'] = len(tweets_with_perspective_scores)
			user_perspective_scores['tweets_with_scores'] = tweets_with_perspective_scores
			score = str(user_perspective_scores['TOXICITY']['score'])
			print('threshold' + threshold)
			print('score: ' + score)

			if (float(score) >= float(threshold)):
				print("ABOVE")
				user_perspective_scores['visualize'] = score
			else:
				print("BELOW")
				user_perspective_scores['visualize'] = 'Below threshold'
			#
			# return Response(response_text,mimetype='plain/text')
			#return jsonify({'key':'jk'})

			# print(user_perspective_scores)
			# print('-----below should return dictionary')
			# print(type(user_perspective_scores)) # this should return dictionary...

			# store the user and score


			twitter_account.toxicity_score=score
			twitter_account.identity_attack_score = user_perspective_scores['IDENTITY_ATTACK']['score']
			twitter_account.insult_score = user_perspective_scores['INSULT']['score']
			twitter_account.profanity_score = user_perspective_scores['PROFANITY']['score']
			twitter_account.threat_score = user_perspective_scores['THREAT']['score']
			twitter_account.sexually_explicit_score = user_perspective_scores['SEXUALLY_EXPLICIT']['score']
			twitter_account.flirtation_score = user_perspective_scores['FLIRTATION']['score']
			twitter_account.stored_at = timezone.now()
			twitter_account.recent_tweet_count=len(tweets_with_perspective_scores)
			twitter_account.save()

			# store_tweets(tweets_with_perspective_scores, twitter_account)

		else:
			# temp_json = {'tweet_scores':model_response_json, 
	# 						'cleaned_tweet_text':  tweet['cleaned_tweet'],
	# 						'original_tweet_text': tweet['original_tweet']
	# 						'tweet_time': tweet['tweet_time'], 
	# 						'tweet_id': tweet_id}
			# Tweet.objects.create(twitter_account=twitter_account,
			# 			tweet_time = tweet['tweet_time'],
			# 			cleaned_text = tweet['cleaned_tweet_text'],
			# 			original_text = tweet['original_tweet_text'],
			# 			toxicity_score = tweet['tweet_scores']['TOXICITY'],
			# 			identity_attack_score = tweet['tweet_scores']['IDENTITY_ATTACK'],
			# 			insult_score = tweet['tweet_scores']['INSULT'],
			# 			profanity_score = tweet['tweet_scores']['PROFANITY'],
			# 			threat_score = tweet['tweet_scores']['THREAT'],
			# 			sexually_explicit_score = tweet['tweet_scores']['SEXUALLY_EXPLICIT'],
			# 			flirtation_score =  tweet['tweet_scores']['FLIRTATION']
			# 			)
			print("ALREADY STORED!")
			stored_account = twitter_account[0]
			print(twitter_account[0])
			user_perspective_scores['TOXICITY'] = {'score':stored_account.toxicity_score}
			user_perspective_scores['tweets_with_scores'] = []
			user_tweets = Tweet.objects.filter(twitter_account=stored_account)
			for stored_tweet in user_tweets:
				temp_tweet_info = { 'cleaned_tweet_text': stored_tweet.cleaned_text,
									'original_tweet_text': stored_tweet.original_text,
									'tweet_scores': { 'TOXICITY': stored_tweet.toxicity_score,
										  'IDENTITY_ATTACK': stored_tweet.identity_attack_score,
										  'INSULT': stored_tweet.insult_score,
										  'PROFANITY': stored_tweet.profanity_score,
										  'THREAT': stored_tweet.threat_score,
										  'SEXUALLY_EXPLICIT': stored_tweet.sexually_explicit_score,
										  'FLIRTATION': stored_tweet.flirtation_score
								   			 }
									}
				user_perspective_scores['tweets_with_scores'].append(temp_tweet_info)
			if (float(stored_account.toxicity_score) >= float(threshold)):
				print("ABOVE")
				user_perspective_scores['visualize'] = score
			else:
				print("BELOW")
				user_perspective_scores['visualize'] = 'Below threshold'

	except Exception as e:
		print(e)

	# return user_perspective_scores
	# return JsonResponse(user_perspective_scores)

