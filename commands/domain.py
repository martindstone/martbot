import os
import re
import requests
from dotmap import DotMap
from slackclient import SlackClient
from app import url_for

import pd
from command import Command

class Domain(Command):

	def __init__(self):
		self.name = "domain"
		self.patterns = [re.compile(p) for p in [r"^domain", r"mbdomain"]]

	def slack_event(self, team, user, req):
		me = DotMap(pd.request(oauth_token=user["pd_token"], endpoint="users/me"))
		sc = SlackClient(team["slack_bot_token"])

		slack_team_id = team["slack_team_id"]
		slack_userid = user["slack_userid"]
		host = os.environ['SERVER_NAME'] or "localhost"

		sc.api_call("chat.postMessage",
			channel=req.event.channel,
			text="You're currently logged in to subdomain *{}* as *{}*".format(user["pd_subdomain"], me.user.email),
			attachments=[{
				"text": "",
				"color": "#25c151",
				"attachment_type": "default",
				"actions": [{
					"text": "Change PD subdomain/user",
					"type": "button",
					"url": "https://{}/me?slack_team_id={}&slack_userid={}".format(host, slack_team_id, slack_userid)
				}]
			}],
			user=slack_userid
		)

	def slack_command(self, team, user, form):
		me = DotMap(pd.request(oauth_token=user["pd_token"], endpoint="users/me"))

		response_url = form.get('response_url')
		slack_team_id = team["slack_team_id"]
		slack_userid = user["slack_userid"]

		slack_response = {
			"response_type": "ephemeral",
			"text": "You're currently logged in to subdomain *{}* as *{}*".format(user["pd_subdomain"], me.user.email),
			"attachments": [{
				"text": "",
				"color": "#25c151",
				"attachment_type": "default",
				"actions": [{
					"text": "Change PD subdomain/user",
					"type": "button",
					"url": url_for("me", _external=True, _scheme="https", slack_team_id=slack_team_id, slack_userid=slack_userid)
				}]
			}]
		}
		requests.post(response_url,
			json=slack_response,
			headers={'Content-type': 'application/json'}
		)

		return ('', 200)
