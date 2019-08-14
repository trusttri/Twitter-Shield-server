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
import requests
import threading
import queue
from socket import timeout
import urllib.parse
import pandas as pd

BUCKET_NAME = 'pretrained-models'
MODEL_FILE_NAME = 'model_politics.bin'
MODEL_LOCAL_PATH = MODEL_FILE_NAME

creds = pd.read_csv('/etc/stranger-danger-key.csv')
consumer_key = creds['consumer_key'][0]
consumer_secret = creds['consumer_secret'][0]
API_KEY = creds['googleapi'][0]

BATCH_SIZE = 50
TWEET_BATCH_NUM = 3
TOXIC_THRESHOLD = 0.7

with open('website/misinfo_urls.json') as file:
	MISINFO_URLS = json.load(file)

with open('website/url_shortener.json') as file:
	URL_SHORTENER = json.load(file)


@csrf_exempt
def authenticate(request):
	if request.is_ajax():
		print('is ajax')
		account_name = request.POST.get('username', 'None')
		oauth_token = request.POST.get('oauth_token', 'None')
		oauth_token_secret = request.POST.get('oauth_token_secret', 'None')

		print('username is ' + account_name)
		print(oauth_token, oauth_token_secret)

		following_list = get_following_list(account_name, oauth_token, oauth_token_secret)

		data = {'account_name': account_name, 'following_list': following_list}
	else:
		data = {'response': 'Not an ajax request'}
	print(data)
	json_data = json.dumps(data)
	return HttpResponse(json_data, content_type='application/json')

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
					cleaned_tweets.append({'cleaned_tweet': cleaned_tweet, 
												'original_tweet': tweet['text'],
												'tweet_time': tweet['tweet_time'], 
												'tweet_id': str(tweet_id)})
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

def get_user_timeline(screenName,tweetCount, access_key, access_secret):
	auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
	auth.set_access_token(access_key, access_secret)
	api = tweepy.API(auth, wait_on_rate_limit=True)
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
			tweet_info[tweet.id] = {'text': tweet.retweeted_status.full_text, 'tweet_time': tweet.created_at,
									'urls': extract_urls(tweet.retweeted_status)}
		else:
			tweet_info[tweet.id] = {'text': tweet.full_text, 'tweet_time': tweet.created_at,
									'urls': extract_urls(tweet)}

	return tweet_info
	# return status_texts


def extract_urls(status):
	expanded_urls = []
	urls = status.entities['urls']
	for url in urls:
		expanded_urls.append(url)
	return expanded_urls

	
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
		user_scores = {}
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
					
					
					# data['result'] = user_perspective_scores
					data['state'] = 'SUCCESS'
					
					# perspective
					user_scores['toxicity'] = user_perspective_scores
					# crediblity
					user_scores['uncrediblity'] = {'uncrediblity': stored_account.misinfo_score, 
												'tweets_with_scores':[]
												}

					for stored_tweet in user_tweets:
						temp_cred_tweet = {'tweet_text': stored_tweet.original_text, 
											'uncrediblity': stored_tweet.misinfo_score,
											'urls': stored_tweet.misinfo_urls.split(' ')}
						user_scores['uncrediblity']['tweets_with_scores'].append(temp_cred_tweet)
						
					data['result'] = user_scores
			
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
	access_key = request.GET.get('oauth_token')
	access_secret = request.GET.get('oauth_token_secret')

	print(screen_name)
	# print(threshold)
	from website.tasks import get_score
	task = get_score.delay(screen_name, threshold, access_key, access_secret)
	# print(task)
	# print(task.id)
	# print('get first status: ' + str(task.status))

	request.session['task_id'] = task.id

	data = {'task_id': task.id, 'screen_name': screen_name, 
			'threshold': threshold, 'state': task.status}
	# print(data)

	json_data = json.dumps(data)

	return HttpResponse(json_data, content_type='application/json')


def is_url_misinfo(url):
    hostname = urllib.parse.urlparse(url).hostname.replace('www.', '')
    print(hostname)
    if hostname in MISINFO_URLS:
        return True
    return False
    # for source in MISINFO_URLS:
    #     if source in url:
    #         return True
    # return False

def parse_urls(tweet_text):
    return re.findall("(?P<url>https?://[^\s]+)", tweet_text)

def fetch_parallel(tweet_to_url):
	print('PARALLEL')
	result = queue.Queue()
	threads = [threading.Thread(target=expand_url, args = (tweet_id, tweet, url,result)) for tweet_id, tweet, url in tweet_to_url]
	for t in threads:
		t.start()
	for t in threads:
		t.join()
	return result

# def read_url(tweet_id, tweet, url, queue):
# 	try:
# 		req = requests.get(url, timeout=2)
# 		data = req.url
# 		queue.put([tweet_id, tweet, data])
# 	except timeout:
# 		print('socket timed out - URL %s', url)
# 	except requests.ConnectionError:
# 		print('try again')
# 		req = requests.get(url, timeout=2)
# 		data = req.url
# 		queue.put([tweet_id, tweet, data])
# 	except Exception as e:
# 		print(url)
# 		print(e)

def is_shortened(url):
	host = urllib.parse.urlparse(url).hostname.replace('www.', '')
	if host in URL_SHORTENER:
		return True
	return False

def expand_url(tweet_id, tweet, url, queue):
	expanded_url = url['expanded_url']
	try:
		if(is_shortened(expanded_url)):
			# queue.put([tweet_id, tweet, url['expanded_url']])
			data = open_url(expanded_url)
			print('--shortened--')
			print(expanded_url)
			print(data)
			queue.put([tweet_id, tweet, data])
		else:
			print('--no need--')
			print(expanded_url)
			queue.put([tweet_id, tweet, expanded_url])
	except timeout:
		print('socket timed out - URL %s', url)
	except requests.ConnectionError:
		print('try again')
		data = open_url(expanded_url)
		queue.put([tweet_id, tweet, data])
	except Exception as e:
		print(url)
		print(e)
	

def open_url(url):
	req = requests.get(url, timeout=2)
	data = req.url
	return data

# def recursive_read_url(tweet_id, tweet, url, queue):
# 	try:
# 		req = requests.get(url, timeout=2)
# 		data = req.url
# 		if data == url:
# 			queue.put([tweet_id, tweet, data])
# 		else:
# 			recursive_read_url(tweet_id, tweet, data, queue)
# 	except timeout:
# 		print('socket timed out - URL %s', url)
# 	except requests.ConnectionError:
# 		print('try again')
# 		req = requests.get(url, timeout=2)
# 		data = req.url
# 		queue.put([tweet_id, tweet, data])
# 	except Exception as e:
# 		print(url)
# 		print(e)

def get_tweet_credibility(user_timeline_tweets,twitter_account):
	uncredible_tweets = {}
	tweet_to_urls = []
	# count = 0
	for tweet_id, tweet in user_timeline_tweets.items():
		# if count > 200:
		# 	break
		# count += 1
		print(tweet['text'])
		uncredible_urls = []
		for url in tweet['urls']:
			# tweet_to_urls.append((tweet_id, tweet['text'], url))
			tweet_to_urls.append((tweet_id, tweet, url))
		# this_tweet_urls = parse_urls(tweet['text'])
		# for url in this_tweet_urls:
		# 	tweet_to_urls.append((tweet_id, tweet['text'], url))
	
	batch_num = len(tweet_to_urls) // BATCH_SIZE
	fetched_tweet_to_url = []
	for i in range(batch_num):
		q = fetch_parallel(tweet_to_urls[i*BATCH_SIZE:(i+1)*BATCH_SIZE])
		fetched_tweet_to_url.extend(q.queue)

	if len(tweet_to_urls) > batch_num*BATCH_SIZE:
		print(len(tweet_to_urls[batch_num*BATCH_SIZE:]))
		q = fetch_parallel(tweet_to_urls[batch_num*BATCH_SIZE:])
		fetched_tweet_to_url.extend(q.queue)
	
	print(batch_num)
	print(len(tweet_to_urls))
	print(len(fetched_tweet_to_url))

	for tweet_id, tweet, url in fetched_tweet_to_url:
		uncredible_urls = []
		if is_url_misinfo(url):
			uncredible_urls.append(url)
			if tweet_id not in uncredible_tweets:
				uncredible_tweets[tweet_id] = {'text': tweet['text'], 'url': [url]}
			else:
				uncredible_tweets[tweet_id]['url'].append(url)
		if len(uncredible_urls)> 0:
			exist = Tweet.objects.filter(twitter_id=tweet_id)
			if len(exist) >0:
				exist[0].misinfo_score = len(uncredible_urls)
				exist[0].misinfo_urls = ' '.join(uncredible_urls)
				exist[0].save()
			else:
				Tweet.objects.create(twitter_account=twitter_account,
        			twitter_id = str(tweet_id),
        			tweet_time = tweet['tweet_time'],
        			original_text = tweet['text'],
        			misinfo_score = len(uncredible_urls),
        			misinfo_urls = ' '.join(uncredible_urls))
	uncredible_tweets['uncrediblity_score'] = 1.0*len(uncredible_tweets)/len(user_timeline_tweets)
	return uncredible_tweets

def get_user_perspective_score(tweets_with_perspective_scores):
	user_perspective_scores_json = {}

	for model in config.PERSPECTIVE_MODELS:
		temp_json = {}
		temp_json['total'] = 0
		temp_json['count'] = 0 
		temp_json['score'] = 0

		for obj in tweets_with_perspective_scores:
			if model in obj['tweet_scores']:
				# temp_json['total'] += obj['tweet_scores'][model]
				if(obj['tweet_scores'][model] > TOXIC_THRESHOLD):
					temp_json['count'] += 1
		if(len(tweets_with_perspective_scores)!=0):
			temp_json['score'] = 1.0*temp_json['count']/len(tweets_with_perspective_scores)
			print('testing perspective score')
			print(temp_json['score'])
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

def get_following_list(account_name, access_key, access_secret):
	auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
	auth.set_access_token(access_key, access_secret)
	api = tweepy.API(auth, wait_on_rate_limit=True)
	# get username
	# account_name = api.me().screen_name
	# get following
	print(account_name)
	following_ids = api.friends_ids(screen_name=account_name)
	print('ids ' + str(len(following_ids)))
	following_usernames = list(get_usernames(following_ids, api))
	return following_usernames

def get_following(request):
	access_key = request.GET.get('oauth_token')
	access_secret = request.GET.get('oauth_token_secret')
	print(access_key, access_secret)
	auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
	auth.set_access_token(access_key, access_secret)
	api = tweepy.API(auth, wait_on_rate_limit=True)
	# get username
	account_name = api.me().screen_name
	# get following
	print(account_name)
	following_ids = api.friends_ids(screen_name=account_name)
	print('ids ' + str(len(following_ids)))
	following_usernames = get_usernames(following_ids, api)
	data = {'following': list(following_usernames), 'account_name': str(account_name)}
	print(len(following_usernames))
	json_data = json.dumps(data)
	print(json_data)
	return HttpResponse(json_data, content_type='application/json')

def get_usernames(ids, api):
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
			# print(temp_json) 
			Tweet.objects.create(twitter_account=twitter_account,
						twitter_id = tweets[i]['tweet_id'],
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
		    
	# print(results)
	# print(len(tweets), len(missed_res))
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
