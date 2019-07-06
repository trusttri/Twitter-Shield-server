from django.shortcuts import render
from django.shortcuts import render
from annoying.decorators import render_to
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.views.decorators.csrf import csrf_exempt
import json,requests,twitter,re,os
from website import config
from langdetect import detect
from googleapiclient import discovery
import tweepy
from googleapiclient import discovery
from website.models import TwitterAccount, Tweet
from django.utils import timezone


BUCKET_NAME = 'pretrained-models'
MODEL_FILE_NAME = 'model_politics.bin'
MODEL_LOCAL_PATH = MODEL_FILE_NAME

consumer_key = "ULVFOWWRwPBG31JmCSk3pA9WY"
consumer_secret = "GkpPuajWIi8OwFNHJMnKaAvLBCQcQZdiNnEViM44eqvTvAXkf7"
access_key = "973403711518183425-CNAn0AQYiT074O0XyALXdU2LiJUzGSg"
access_secret = "s986l8COxFydEgyOCSuHrtGRSldyunsKfZh59TRyx1tVd"
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_key, access_secret)
api = tweepy.API(auth)


API_KEY='AIzaSyDlpWkkECadgt55aVD0tKIrTcjHpIBk3i8'



'''
1. Checks if tweets are in English 2. Removes links, @ 3. Checks if tweet
'''
def clean_tweets(tweets):
	# cleaned_tweets = []
	cleaned_tweets = {}
	for tweet_id, tweet in tweets.items():
		#print('before clean ' + tweet)
		try:
			if(detect(tweet['text']) == 'en'):
				cleaned_tweet = re.sub(r'(@\S+)|(http\S+)', " ", str(tweet['text']))
				if(cleaned_tweet and cleaned_tweet.strip()):
					# print('\n')
					# print('After clean ' + tweet)
					# print('\n')
					# cleaned_tweets.append(tweet)
					cleaned_tweets[tweet_id] = {'cleaned_tweet': cleaned_tweet, 
												'original_tweet': tweet['text'],
												'tweet_time': tweet['tweet_time']}
		except Exception as e:
			print('Exception wheen cleaning- Tweet in response: ' + tweet['text'])
			print(e)
	print(len(cleaned_tweets))
	return cleaned_tweets
			
def get_user(screenName):
	user = api.GetUser(None,screenName,True,True)
	return user

def get_user_timeline(screenName,tweetCount):
	statuses = api.user_timeline(screen_name = screenName,count=tweetCount, tweet_mode="extended")

	# status_texts = []
	# for tweet in statuses:
	# 	if hasattr(tweet, 'retweeted_status'):
	# 		status_texts.append(tweet.retweeted_status.full_text)
	# 	else:
	# 		status_texts.append(tweet.full_text)
	tweet_info = {}

	for tweet in statuses:
		if hasattr(tweet, 'retweeted_status'):
			tweet_info[tweet.id] = {'text': tweet.retweeted_status.full_text, 'tweet_time': tweet.created_at}
		else:
			tweet_info[tweet.id] = {'text': tweet.full_text, 'tweet_time': tweet.created_at}

	return tweet_info
	# return status_texts

	
def store_tweets(tweets, twitter_account):
	for tweet in tweets:
		Tweet.objects.create(twitter_account=twitter_account,
							tweet_time = tweet['tweet_time'],
							cleaned_text = tweet['cleaned_tweet_text'],
							original_text = tweet['original_tweet_text'],
							toxicity_score = tweet['tweet_scores']['TOXICITY'],
							identity_attack_score = tweet['tweet_scores']['IDENTITY_ATTACK'],
							insult_score = tweet['tweet_scores']['INSULT'],
							profanity_score = tweet['tweet_scores']['PROFANITY'],
							threat_score = tweet['tweet_scores']['THREAT'],
							sexually_explicit_score = tweet['tweet_scores']['SEXUALLY_EXPLICIT'],
							flirtation_score =  tweet['tweet_scores']['FLIRTATION']
							)

def index(request):
    template = loader.get_template('website/index.html')
    context = {}
    return HttpResponse(template.render(context, request))


@csrf_exempt 
def status(request):

	return 1

@csrf_exempt
def toxicity_score(request):
	screen_name = request.GET.get('user')
	threshold = request.GET.get('threshold')
	print(screen_name)
	print(threshold)
	user_perspective_scores = {}
	try:

		twitter_account = TwitterAccount.objects.filter(screen_name=screen_name)
		if twitter_account.count() == 0:
		
			#models user choses  + score - probably store this in db too! 
			#set default as zero in front end 

			models_setting_json = {}
			for model in config.PERSPECTIVE_MODELS:
				if(request.GET.get(model.lower())):
					models_setting_json[model] = {'scoreThreshold': request.args.get(model.lower())}
				else:
					models_setting_json[model] = {'scoreThreshold': '0'}

			#print(models_setting_json)

			tweet_count = 200
			#get tweets on user's timeline
			user_timeline_tweets = get_user_timeline(screen_name, tweet_count)
			cleaned_user_timeline_tweets = clean_tweets(user_timeline_tweets)	


			tweets_with_perspective_scores = get_tweet_perspective_scores(cleaned_user_timeline_tweets, models_setting_json)
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


			twitter_account = TwitterAccount.objects.create(screen_name=screen_name,
															toxicity_score=score,
															identity_attack_score = user_perspective_scores['IDENTITY_ATTACK']['score'],
															insult_score = user_perspective_scores['INSULT']['score'],
															profanity_score = user_perspective_scores['PROFANITY']['score'],
															threat_score = user_perspective_scores['THREAT']['score'],
															sexually_explicit_score = user_perspective_scores['SEXUALLY_EXPLICIT']['score'],
															flirtation_score = user_perspective_scores['FLIRTATION']['score'],
															stored_at = timezone.now(),
															recent_tweet_count=len(tweets_with_perspective_scores))
			store_tweets(tweets_with_perspective_scores, twitter_account)
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
			if (float(stored_tweet.toxicity_score) >= float(threshold)):
				print("ABOVE")
				user_perspective_scores['visualize'] = score
			else:
				print("BELOW")
				user_perspective_scores['visualize'] = 'Below threshold'
	except Exception as e:
		print(e)

	
	return JsonResponse(user_perspective_scores)


def get_user_perspective_score(tweets_with_perspective_scores):
	user_perspective_scores_json = {}


	for model in config.PERSPECTIVE_MODELS:
		temp_json = {}
		temp_json['total'] = 0
		temp_json['count'] = 0 
		temp_json['score'] = 0

		for obj in tweets_with_perspective_scores:
			if model in obj['tweet_scores']:
				temp_json['total'] += obj['tweet_scores'][model]
				temp_json['count'] += 1
		if(temp_json['count']!=0):
			temp_json['score'] = temp_json['total']/temp_json['count']
		user_perspective_scores_json[model] = temp_json

	#print(user_perspective_scores_json)
	return user_perspective_scores_json


def get_tweet_perspective_scores(tweets, models_setting_json):
	service = discovery.build('commentanalyzer', 'v1alpha1', developerKey=API_KEY)
	tweets_with_perspective_scores = []
	tweet_count = 0
	
	# for original_tweet, cleaned_tweet in tweets.items():
	for tweet_id, tweet in tweets.items():
		model_response_json ={}
		analyze_request = {
				  'comment': { 'text': tweet['cleaned_tweet']},
				  'requestedAttributes': models_setting_json}
		try:
			response = service.comments().analyze(body=analyze_request).execute()
			if(response['attributeScores']):
				for model in config.PERSPECTIVE_MODELS:
					if model in response['attributeScores']:
						model_response_json[model] = response['attributeScores'][model]['summaryScore']['value']
				temp_json = {'tweet_scores':model_response_json, 
							'cleaned_tweet_text':  tweet['cleaned_tweet'],
							'original_tweet_text': tweet['original_tweet'],
							'tweet_time': tweet['tweet_time'], 
							'tweet_id': tweet_id}
				tweets_with_perspective_scores.append(temp_json)
		except Exception as e:
			print(e)
			print('Exception when getting perspective scores - Tweet in response: ' +  tweet['original_tweet'])
			
		
	
	# print(json.dumps(tweets_with_perspective_scores,indent=2)) 
	# print('\n')

	return tweets_with_perspective_scores
