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
	for tweet in tweets:
		#print('before clean ' + tweet)
		try:
			if(detect(tweet) == 'en'):
				cleaned_tweet = re.sub(r'(@\S+)|(http\S+)', " ", str(tweet))
				if(cleaned_tweet and cleaned_tweet.strip()):
					# print('\n')
					# print('After clean ' + tweet)
					# print('\n')
					# cleaned_tweets.append(tweet)
					cleaned_tweets[tweet] = cleaned_tweet
		except Exception as e:
			print('Exception wheen cleaning- Tweet in response: ' + tweet)
			print(e)
	print(len(cleaned_tweets))
	return cleaned_tweets
			
def get_user(screenName):
	user = api.GetUser(None,screenName,True,True)
	return user

def get_user_timeline(screenName,tweetCount):
	statuses = api.user_timeline(screen_name = screenName,count=tweetCount, tweet_mode="extended")

	status_texts = []
	for tweet in statuses:
		if hasattr(tweet, 'retweeted_status'):
			status_texts.append(tweet.retweeted_status.full_text)
		else:
			status_texts.append(tweet.full_text)

	#print(status_texts)
	return status_texts


def index(request):
    template = loader.get_template('website/index.html')
    context = {}
    return HttpResponse(template.render(context, request))

def status(request):
	return 1

@csrf_exempt
def toxicity_score(request):
	screen_name = request.GET.get('user')
	threshold = request.GET.get('threshold')
	print(screen_name)
	print(threshold)
	user_perspective_scores = {}

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
	
	for original_tweet, cleaned_tweet in tweets.items():
		model_response_json ={}
		analyze_request = {
				  'comment': { 'text': cleaned_tweet},
				  'requestedAttributes': models_setting_json}
		try:
			response = service.comments().analyze(body=analyze_request).execute()
			if(response['attributeScores']):
				for model in config.PERSPECTIVE_MODELS:
					if model in response['attributeScores']:
						model_response_json[model] = response['attributeScores'][model]['summaryScore']['value']
				temp_json = {'tweet_scores':model_response_json, 'cleaned_tweet_text':cleaned_tweet, 'original_tweet_text':original_tweet}
				tweets_with_perspective_scores.append(temp_json)
		except Exception as e:
			print('Exception when getting perspective scores - Tweet in response: ' +  original_tweet)
			print(e)
		
	
	# print(json.dumps(tweets_with_perspective_scores,indent=2)) 
	# print('\n')

	return tweets_with_perspective_scores
