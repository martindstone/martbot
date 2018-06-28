from flask import Flask, request, render_template, url_for, redirect, session, Response
from urllib.parse import urlparse
from importlib import import_module
from mongoengine import *
from dotmap import DotMap
from threading import Thread
import json
import os
import sys
import re
import requests
from slackclient import SlackClient
import pprint

import command

pd_client_id = os.environ.get('PD_CLIENT_ID') or "set your PD_CLIENT_ID environment variable"

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or os.urandom(20)

if os.environ.get('MONGODB_URI'):
	connect('pymartbot', host=os.environ['MONGODB_URI'])
else:
	connect('pymartbot')

class User(EmbeddedDocument):
	slack_userid = StringField(required=True)
	pd_userid = StringField(required=True)
	pd_token = StringField(required=True)
	pd_subdomain = StringField(required=True)

class Team(Document):
	slack_team_id = StringField(required=True)
	slack_app_token = StringField(required=True)
	slack_bot_token = StringField(required=True)
	slack_bot_userid = StringField(required=True)
	users = EmbeddedDocumentListField(User)

command_names = [re.sub(r"\.py", "", name) for name in os.listdir("commands") if name.endswith('.py') and not name.startswith('__')]
command_modules = list(map(lambda name: {"name": name.title(), "module": import_module("commands.{}".format(name))}, command_names))
command_classes = [getattr(module["module"], module["name"]) for module in command_modules]
commands = [command_class() for command_class in command_classes]


@app.route('/slack_event', methods=['POST'])
def slack_event():
	if request.json.get('type') == 'url_verification':
		return request.json.get('challenge')

	req = DotMap(request.json);
	event = req.event

	# don't talk to yourself
	event_subtype = event.message.subtype or event.subtype
	if event_subtype == 'bot_message':
		return ('', 200)

	message_text = event.text or event.message.text
	slack_channel = event.channel

	slack_team_id = req.team_id
	slack_userid = event.user or event.message.user
	team_record = Team.objects(slack_team_id=slack_team_id).first()
	if not team_record:
		print("team {} not found".format(slack_team_id))
		return ('', 200)
	user = [user for user in team_record.users if user.slack_userid == slack_userid]
	user = user[0] if user else None

	team = {
		"slack_team_id": slack_team_id,
		"slack_bot_userid": team_record.slack_bot_userid,
		"slack_bot_token": team_record.slack_bot_token,
		"slack_app_token": team_record.slack_app_token
	}

	sc = SlackClient(team_record.slack_bot_token)

	if not user or user["pd_subdomain"] == "pdt-k18":
		sc.api_call("chat.postEphemeral",
			channel=req.event.channel,
			attachments=[{
				"text": "Looks like your Slack user isn't mapped to PagerDuty. Map it now?",
				"color": "#25c151",
				"attachment_type": "default",
				"actions": [{
					"text": "OK",
					"type": "button",
					"url": url_for("me", _external=True, _scheme="https", slack_team_id=slack_team_id, slack_userid=slack_userid)
				}]
			}],
			user=user["slack_userid"])

		return ('', 200)

	for command in commands:
		if command.matches(message_text) and callable(getattr(command, "slack_event")):
			thread = Thread(target=command.slack_event, args=(team, user, req))
			thread.start()

	return ('', 200)


@app.route('/slack_action', methods=['POST'])
def slack_action():
	req = DotMap(json.loads(request.form.get('payload')))

	slack_team_id = req.team.id
	slack_userid = req.user.id
	callback_id = req.callback_id

	team_record = Team.objects(slack_team_id=slack_team_id).first()
	if not team_record:
		print("team {} not found".format(slack_team_id))
		return ('', 200)

	team = {
		"slack_team_id": slack_team_id,
		"slack_bot_userid": team_record.slack_bot_userid,
		"slack_bot_token": team_record.slack_bot_token,
		"slack_app_token": team_record.slack_app_token
	}

	user = [user for user in team_record.users if user.slack_userid == slack_userid]
	user = user[0] if user else None
	if not user:
		print("user {} not found in team {}".format(slack_userid, slack_team_id))
		return ("", 200)

	if req.type == "dialog_submission":
		for command in commands:
			if command.matches(callback_id) and hasattr(command, "validate_submission") and callable(getattr(command, "validate_submission")):
				error = command.validate_submission(team, user, req)
				if error:
					return (error, 200)

	for command in commands:
		if command.matches(callback_id) and callable(getattr(command, "slack_action")):
			thread = Thread(target=command.slack_action, args=(team, user, req))
			thread.start()

	return ('', 200)


@app.route('/slack_load_options', methods=['POST'])
def slack_load_options():
	req = DotMap(json.loads(request.form.get('payload')))

	slack_team_id = req.team.id
	slack_userid = req.user.id
	callback_id = req.callback_id

	team_record = Team.objects(slack_team_id=slack_team_id).first()
	if not team_record:
		print("team {} not found".format(slack_team_id))
		return ('', 200)

	team = {
		"slack_team_id": slack_team_id,
		"slack_bot_userid": team_record.slack_bot_userid,
		"slack_bot_token": team_record.slack_bot_token,
		"slack_app_token": team_record.slack_app_token
	}

	user = [user for user in team_record.users if user.slack_userid == slack_userid]
	user = user[0] if user else None
	if not user:
		print("user {} not found in team {}".format(slack_userid, slack_team_id))
		return ("", 200)

	for command in commands:
		if command.matches(callback_id) and callable(getattr(command, "slack_load_options")):
			r = command.slack_load_options(team, user, req)
			return Response(r, mimetype="application/json")


@app.route('/slack_command', methods=['POST'])
def slack_command():
	command_text = re.sub(r"^/", "", request.form.get('command'))
	slack_team_id = request.form.get('team_id')
	slack_userid = request.form.get('user_id')
	slack_channel = request.form.get('channel_id')

	team_record = Team.objects(slack_team_id=slack_team_id).first()
	if not team_record:
		print("team {} not found".format(slack_team_id))
		return ('', 200)

	team = {
		"slack_team_id": slack_team_id,
		"slack_bot_userid": team_record.slack_bot_userid,
		"slack_bot_token": team_record.slack_bot_token,
		"slack_app_token": team_record.slack_app_token
	}

	user = [user for user in team_record.users if user.slack_userid == slack_userid]
	user = user[0] if user else None
	if not user or user["pd_subdomain"] == "pdt-k18":
		slack_response = {
			"response_type": "ephemeral",
			"text": "",
			"attachments": [{
				"text": "Looks like your Slack user isn't mapped to PagerDuty. Map it now?",
				"color": "#25c151",
				"attachment_type": "default",
				"actions": [{
					"text": "OK",
					"type": "button",
					"url": url_for("me", _external=True, _scheme="https", slack_team_id=slack_team_id, slack_userid=slack_userid)
				}]
			}]
		}
		response_url = request.form.get('response_url')
		r = requests.post(response_url,
			json=slack_response,
			headers={'Content-type': 'application/json'}
		)
		return ('', 200)

	for command in commands:
		if command.matches(command_text) and callable(getattr(command, "slack_command")):
			return command.slack_command(team, user, request.form)

	return ('', 200)



#####################
#
# Slack install URL
#
def slack_install_url():
	return "https://slack.com/oauth/authorize?client_id={}&scope=bot,commands,chat:write:bot".format(os.environ.get('SLACK_CLIENT_ID'))

@app.route('/slack_install')
def slack_install():
	return redirect(slack_install_url())

#####################
#
# Add to Slack button
#
@app.route('/')
def index():
	session.clear()
	return render_template('index.html', slack_install_url=slack_install_url())

#####################
#
# OAuth - code coming back from slack, get token and store it in the session
#
@app.route('/code')
def code():
	host = request.host
	path = request.path
	redirect_url = "https://{}{}".format(host, path)

	headers = {
		"Content-type": "application/x-www-form-urlencoded"
	}

	try:
		params = {
			'client_id': os.environ['SLACK_CLIENT_ID'],
			'client_secret': os.environ['SLACK_CLIENT_SECRET'],
			'code': request.args['code'],
			'redirect_uri': redirect_url
		}
		r = requests.get('https://slack.com/api/oauth.access', headers=headers, params=params)
		body = r.json()

		session['slack_team_id'] = body.get('team_id')
		session['slack_userid'] = body.get('user_id')
		session['slack_app_token'] = body.get('access_token')
		bot = body.get('bot')
		session['slack_bot_token'] = bot.get('bot_access_token')
		session['slack_bot_userid'] = bot.get('bot_user_id')
	except:
		print("Unexpected error in /code:", sys.exc_info()[0])
		return redirect(url_for('index'))
	else:
		return redirect("https://app.pagerduty.com/oauth/authorize?client_id={}&redirect_uri=https://{}/pdtoken&response_type=token".format(pd_client_id, host))

#####################
#
# OAuth - token coming back from PD
#
@app.route('/pdtoken')
def pdtoken():
	if all (key in request.args for key in ('access_token', 'subdomain')):
		if all (key in session for key in ('slack_team_id', 'slack_userid', 'slack_bot_token', 'slack_bot_userid')):
			# got everything
			team = Team.objects(slack_team_id=session.get('slack_team_id')).first()
			if team == None:
				team = Team()

			team.slack_team_id = session.get('slack_team_id')
			team.slack_app_token = session.get('slack_app_token')
			team.slack_bot_token = session.get('slack_bot_token')
			team.slack_bot_userid = session.get('slack_bot_userid')
			slack_userid = session.get('slack_userid')
			pd_token = request.args.get('access_token')
			(pd_userid, pd_subdomain) = pd_me(pd_token)
			team.users = [ User(slack_userid=slack_userid, pd_userid=pd_userid, pd_token=pd_token, pd_subdomain=pd_subdomain) ]
			team.save()
			session.clear()
			return redirect("https://slack.com/app_redirect?app={}".format(os.environ['SLACK_APP_ID']))
		else:
			# got pd info but not slack info
			return redirect(slack_install_url())
	else:
		# funny hash thing from pd, server can't see it so use the browser to change the '#' to a '?'
		return render_template('pdtoken.html')


def pd_me(token):
	headers = {
		"Authorization": "Bearer {}".format(token),
		"Accept": "application/vnd.pagerduty+json;version=2"
	}
	r = requests.get("https://api.pagerduty.com/users/me", headers=headers)
	user = r.json().get('user')
	pd_userid = user.get('id');
	pd_subdomain = urlparse(user.get('html_url')).netloc.split('.')[0]

	return (pd_userid, pd_subdomain)

def update_team_user(slack_team_id, slack_userid, pd_userid, pd_token, pd_subdomain):
	team = Team.objects(slack_team_id=slack_team_id).first()
	if team == None:
		return False
	new_user = User(slack_userid=slack_userid, pd_userid=pd_userid, pd_token=pd_token, pd_subdomain=pd_subdomain)
	indices = [i for i, user in enumerate(team.users) if user.slack_userid == slack_userid]
	if len(indices) == 1:
		team.users[indices[0]] = new_user
	elif len(indices) == 0:
		team.users.append(new_user)
	else:
		return False
	team.save()
	return True

#####################
#
# Map a Slack user to PD user/domain
#
@app.route('/me')
def me():
	if all (key in request.args for key in ('slack_team_id', 'slack_userid')):
		session.clear()
		session['slack_team_id'] = request.args['slack_team_id']
		session['slack_userid'] = request.args['slack_userid']
		host = request.host
		return redirect("https://app.pagerduty.com/oauth/authorize?" + 
			"client_id={}&redirect_uri=https://{}/me&response_type=token".format(pd_client_id, host))
	if all (key in request.args for key in ('access_token', 'subdomain')):
		# got everything
		slack_team_id = session.get('slack_team_id')
		slack_userid = session.get('slack_userid')
		pd_token = request.args.get('access_token')
		(pd_userid, pd_subdomain) = pd_me(pd_token)
		session.clear()
		if update_team_user(slack_team_id, slack_userid, pd_userid, pd_token, pd_subdomain):
			return redirect("https://slack.com/app_redirect?app={}".format(os.environ['SLACK_APP_ID']))
		else:
			return "Oops, didn't update user mapping for slack user {}".format(slack_userid)
	else:
		# funny hash thing from pd, server can't see it so use the browser to change the '#' to a '?'
		return render_template('pdtoken.html')
