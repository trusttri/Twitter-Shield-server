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
import time

BUCKET_NAME = 'pretrained-models'
MODEL_FILE_NAME = 'model_politics.bin'
MODEL_LOCAL_PATH = MODEL_FILE_NAME

consumer_key = ""
consumer_secret = ""
access_key = ""
access_secret = ""
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_key, access_secret)
api = tweepy.API(auth, wait_on_rate_limit=True)


API_KEY = ""

TWEET_BATCH_NUM = 3


'''
1. Checks if tweets are in English 2. Removes links, @ 3. Checks if tweet
'''
def clean_tweets(tweets):
	cleaned_tweets = []
	# cleaned_tweets = {}
	for tweet_id, tweet in tweets.items():
		try:
			if(detect(tweet['text']) == 'en'):
				cleaned_tweet = re.sub(r'(@\S+)|(http\S+)', " ", str(tweet['text']))
				if(cleaned_tweet and cleaned_tweet.strip()):
					# print('\n')
					# print('After clean ' + tweet)
					# print('\n')s
					cleaned_tweets.append({'cleaned_tweet': cleaned_tweet, 
												'original_tweet': tweet['text'],
												'tweet_time': tweet['tweet_time']})
					# cleaned_tweets[tweet_id] = {'cleaned_tweet': cleaned_tweet, 
												# 'original_tweet': tweet['text'],
												# 'tweet_time': tweet['tweet_time']}
		except Exception as e:
			# print('Exception wheen cleaning- Tweet in response: ' + tweet['text'])
			print(e)
	# print(len(cleaned_tweets))
	return cleaned_tweets
			
def get_user(screenName):
	user = api.GetUser(None,screenName,True,True)
	return user

def get_user_timeline(screenName,tweetCount):
	try:
		statuses = api.user_timeline(screen_name = screenName,count=tweetCount, tweet_mode="extended")
	except tweepy.TweepError as e:
		return 'Not authorized.'
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
def poll_status(request):
	data = {'Fail'}
	task_id = request.GET.get('task_id')
	screen_name = request.GET.get('screen_name')
	threshold = request.GET.get('threshold')
	from website.tasks import get_score
	task = get_score.AsyncResult(task_id)
	data = {
			'state': task.state,
			'result': 'started'
			}
	print('poll--' + screen_name)
	print('task state: ' + str(task.state))

	if task.state == 'SUCCESS':
		print('SUCCESS!')
		user_perspective_scores = {}
		twitter_account = TwitterAccount.objects.filter(screen_name=screen_name)
		if len(twitter_account) > 0:
			stored_account = twitter_account[0]

			if stored_account.toxicity_score is not None:
				if stored_account.toxicity_score < 0:
					data['result'] = 'No tweets'
					print('no tweets!!!!!!!!!!!!!')
				else:
					# print(twitter_account[0].screen_name)
					# print(stored_account.toxicity_score)
					user_perspective_scores['TOXICITY'] = {'score':stored_account.toxicity_score}
					user_perspective_scores['tweets_with_scores'] = []
					user_tweets = Tweet.objects.filter(twitter_account=stored_account)
					for stored_tweet in user_tweets:
						temp_tweet_info = { 
											'tweet_scores': { 'TOXICITY': stored_tweet.toxicity_score,
												  'IDENTITY_ATTACK': stored_tweet.identity_attack_score,
												  'INSULT': stored_tweet.insult_score,
												  'PROFANITY': stored_tweet.profanity_score,
												  'THREAT': stored_tweet.threat_score,
												  'SEXUALLY_EXPLICIT': stored_tweet.sexually_explicit_score,
												  'FLIRTATION': stored_tweet.flirtation_score
										   			 },
								   			 'tweet_text': stored_tweet.original_text
											}
						user_perspective_scores['tweets_with_scores'].append(temp_tweet_info)
					
					
					if (float(stored_account.toxicity_score) >= float(threshold)):
						user_perspective_scores['visualize'] = stored_account.toxicity_score
					else:
						user_perspective_scores['visualize'] = 'Below threshold'
					
					data['result'] = user_perspective_scores
					data['state'] = 'SUCCESS'
		
			
	elif task.state == 'PENDING':
		print('PENDING....' + screen_name)
		# get stored tweet number
		twitter_account = TwitterAccount.objects.filter(screen_name=screen_name)
		data['state'] = 'PENDING'
		if twitter_account.count() > 0:
			stored_account = twitter_account[0]
			# stored_tweet_num = Tweet.objects.filter(twitter_account=stored_account).count()
			stored_tweet_count = stored_account.recent_tweet_count
			if stored_tweet_count is not None:
				data['result'] = str(stored_tweet_count)
			else:
				data['result'] = 'started'
		# print(data)

	elif task.state == 'FAILURE':
		print('FAIL')
		data['state'] = 'FAILURE'

	
	json_data = json.dumps(data)

	return HttpResponse(json_data, content_type='application/json')


# @csrf_exempt    
# def test_poll_status(task_id):
# 	print('poll status called!!')
# 	from website.tasks import get_score
# 	task = get_score.AsyncResult(task_id)
# 	print('task state: ' + str(task.state))

# 	if task.state == 'SUCCESS':
# 		print('SUCCESS!')

# 	elif task.state == 'PENDING':
# 		print('PENDING....')
# 		# get stored tweet number
# 		test_poll_status(task_id)

# 	elif task.state == 'FAILURE':
# 		print('FAIL')



@csrf_exempt
def toxicity_score(request):
	screen_name = request.GET.get('user')
	threshold = request.GET.get('threshold')
	print(screen_name)
	# print(threshold)
	from website.tasks import get_score
	task = get_score.delay(screen_name, threshold)
	# print(task)
	# print(task.id)
	# print('get first status: ' + str(task.status))

	request.session['task_id'] = task.id

	data = {'task_id': task.id, 'screen_name': screen_name, 
			'threshold': threshold, 'state': task.status}
	# print(data)

	json_data = json.dumps(data)

	return HttpResponse(json_data, content_type='application/json')


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
			# print('testing perspective score')
			# print(temp_json['score'])
		else:
			return None

		user_perspective_scores_json[model] = temp_json

	return user_perspective_scores_json



# def get_user_perspective_score(batched_tweets, models_setting_json, twitter_account):
# 	# need to add multiple keys
# 	service = discovery.build('commentanalyzer', 'v1alpha1', developerKey=API_KEY,  cache_discovery=False)
# 	tweets_with_perspective_scores = []
# 	tweet_count = 0
	
	
# 	# where we finally store the scores
# 	user_perspective_scores_json = {}
# 	temp_scores = {}
# 	for model in config.PERSPECTIVE_MODELS:
# 		temp_scores[model] = []
# 	# print(batched_tweets)
# 	for each_batch in batched_tweets:
# 		tweet_string = ''
# 		for tweet in each_batch:
# 			# print(tweet)
# 			tweet_string += tweet['cleaned_tweet'] + '\n'

# 		print('tweet string length: ' + str(len(tweet_string)))

# 		analyze_request = {
# 					  'comment': { 'text': tweet_string},
# 					  'requestedAttributes': models_setting_json}
# 		try:
# 			response = service.comments().analyze(body=analyze_request).execute()
# 			# print(response)
# 			if(response['attributeScores']):
# 				for model in config.PERSPECTIVE_MODELS:
# 					if model in response['attributeScores']:
# 						temp_scores[model].append(response['attributeScores'][model]['summaryScore']['value'])

# 		except Exception as e:
# 			print(e)
# 			print('Exception when getting perspective scores ' + twitter_account.screen_name)
# 			print(len(tweet_string))

# 	for model in config.PERSPECTIVE_MODELS:
# 		if len(temp_scores[model]) > 0:
# 			print(temp_scores[model])
# 			user_perspective_scores_json[model] = sum(temp_scores[model])/len(temp_scores[model])
# 			print(user_perspective_scores_json[model])
# 		else:
# 			user_perspective_scores_json[model] = -1


# 	return user_perspective_scores_json

def get_following(request):
	account_name = request.GET.get('user')
	print(account_name)
	following_ids = api.friends_ids(screen_name=account_name)
	print('ids ' + str(len(following_ids)))
	following_usernames = get_usernames(following_ids)
	data = {'following': list(following_usernames)}
	print(len(following_usernames))
	json_data = json.dumps(data)
	return HttpResponse(json_data, content_type='application/json')

def get_usernames(ids):
    """ can only do lookup in steps of 100;
        so 'ids' should be a list of 100 ids
    """
    total_following_usernames = set()
    batch_size = int(len(ids)/100)
    print(batch_size)
    for i in range(batch_size):
        print(i*100, (i+1)*100)
        user_objs = api.lookup_users(user_ids=ids[i*100:(i+1)*100])
        for user in user_objs:
            total_following_usernames.add(user.screen_name)
    if len(ids) > batch_size:
        user_objs = api.lookup_users(user_ids=ids[batch_size*100:])
        for user in user_objs:
            total_following_usernames.add(user.screen_name)
    return total_following_usernames

def get_tweet_perspective_scores(tweets, models_setting_json, twitter_account):
	tweets_with_perspective_scores = []
	results = []
	tweet_count = 0

	##### NEW #####
	count = 0
	limit = 100
	iteration = 0
	service = discovery.build('commentanalyzer', 'v1alpha1', developerKey=API_KEY, cache_discovery=False)
	

	def get_results(request_id, response, exception):
	    tweets_with_perspective_scores.append((request_id, response))

	batch = service.new_batch_http_request(callback=get_results)
	

	for tweet in tweets:
	    analyze_request = {
				  'comment': { 'text': tweet['cleaned_tweet']},
				  'requestedAttributes': models_setting_json}
	    count += 1
	    
	    batch.add(service.comments().analyze(body=analyze_request), request_id=str(count))
	    
	    if count >= limit:
	        batch.execute()
	        batch = service.new_batch_http_request(callback=get_results)
	        count = 0
	        print("Sleep #", iteration)
	        iteration += 1
	        time.sleep(2)
	#         break

	batch.execute()
	print("Done")

	missed_res = []
	misses = 0
	for i in range(len(tweets)):
		print(len(tweets), i)
		print(tweets_with_perspective_scores[i])
		model_response_json = {}
		if tweets_with_perspective_scores[i][1] is not None: 
			for model in config.PERSPECTIVE_MODELS:
				if model in tweets_with_perspective_scores[i][1]['attributeScores']:
					try:
						model_response_json[model] = tweets_with_perspective_scores[i][1]['attributeScores'][model]['summaryScore']['value']
					except:
						misses += 1
						model_response_json[model] = None
						missed_res.append(-1.0)
			
			temp_json = {'tweet_scores':model_response_json, 
						'cleaned_tweet_text':  tweets[i]['cleaned_tweet'],
						'original_tweet_text': tweets[i]['original_tweet'],
						'tweet_time': tweets[i]['tweet_time'], 
						}
			print(temp_json) 
			Tweet.objects.create(twitter_account=twitter_account,
						tweet_time = tweets[i]['tweet_time'],
						cleaned_text = tweets[i]['cleaned_tweet'],
						original_text = tweets[i]['original_tweet'],
						toxicity_score = model_response_json['TOXICITY'],
						identity_attack_score = model_response_json['IDENTITY_ATTACK'],
						insult_score = model_response_json['INSULT'],
						profanity_score = model_response_json['PROFANITY'],
						threat_score = model_response_json['THREAT'],
						sexually_explicit_score = model_response_json['SEXUALLY_EXPLICIT'],
						flirtation_score =  model_response_json['FLIRTATION']
						)
			results.append(temp_json)
		    
	print(results)
	print(len(tweets), len(missed_res))
	return results
	##### NEW #####
	
	# for original_tweet, cleaned_tweet in tweets.items():
	# print('length: ' + str(len(tweets)))
	# for tweet_id, tweet in tweets.items():
	# 	model_response_json ={}
	# 	analyze_request = {
	# 			  'comment': { 'text': tweet['cleaned_tweet']},
	# 			  'requestedAttributes': models_setting_json}
	# 	# print(analyze_request)
	# 	# print(modelsㅅ_setting_json)
	# 	try:
	# 		response = service.comments().analyze(body=analyze_request).execute()
	# 		# print(response)
	# 		if(response['attributeScores']):
	# 			for model in config.PERSPECTIVE_MODELS:
	# 				if model in response['attributeScores']:
	# 					model_response_json[model] = response['attributeScores'][model]['summaryScore']['value']
	# 			temp_json = {'tweet_scores':model_response_json, 
	# 						'cleaned_tweet_text':  tweet['cleaned_tweet'],
	# 						'original_tweet_text': tweet['original_tweet'],
	# 						'tweet_time': tweet['tweet_time'], 
	# 						'tweet_id': tweet_id}
	# 			print(temp_json)
	# 			Tweet.objects.create(twitter_account=twitter_account,
	# 						tweet_time = tweet['tweet_time'],
	# 						cleaned_text = tweet['cleaned_tweet'],
	# 						original_text = tweet['original_tweet'],
	# 						toxicity_score = model_response_json['TOXICITY'],
	# 						identity_attack_score = model_response_json['IDENTITY_ATTACK'],
	# 						insult_score = model_response_json['INSULT'],
	# 						profanity_score = model_response_json['PROFANITY'],
	# 						threat_score = model_response_json['THREAT'],
	# 						sexually_explicit_score = model_response_json['SEXUALLY_EXPLICIT'],
	# 						flirtation_score =  model_response_json['FLIRTATION']
	# 						)
	# 			tweets_with_perspective_scores.append(temp_json)
	# 			time.sleep(0.002)
	# 	except Exception as e:
	# 		print(e)
			# print('Exception when getting perspective scores - Tweet in response: ' +  tweet['original_tweet'])
			# print(twitter_account.screen_name)
			
		
	# print(json.dumps(tweets_with_perspective_scores,indent=2)) 
	# print('\n')

	# return tweets_with_perspective_scores
