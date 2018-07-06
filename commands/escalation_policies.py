import os
import re
import json
import requests
from dotmap import DotMap
from slackclient import SlackClient

import pd
import slack_formatters
from command import Command

class Escalation_Policies(Command):

	def __init__(self):
		self.name = "eps"
		self.patterns = [re.compile(p) for p in [r"^eps", r"^escal", r"^mbeps"]]

	def slack_event(self, team, user, req):
		sc = SlackClient(team["slack_bot_token"])

		message_text = req.event.text or req.event.message.text

		eps = [{"text": ep["summary"], "value": ep["id"]} for ep in pd.fetch_escalation_policies(oauth_token=user["pd_token"])]

		sc.api_call("chat.postMessage",
			channel=req.event.channel,
			attachments=[{
				"text": "Choose an escalation policy in domain {}".format(user["pd_subdomain"]),
				"color": "#25c151",
				"attachment_type": "default",
				"callback_id": req.event.text or req.event.message.text,
				"actions": [{
					"name": "eps",
					"text": "Pick an EP",
					"type": "select",
					"data_source": "external"
				}]
			}])

	def slack_action(self, team, user, req):
		ep_id = req.actions[0].selected_options[0].value
		response_url = req.response_url

		ep = pd.request(oauth_token=user.pd_token, endpoint="/escalation_policies/{}".format(ep_id), params={"include[]": "current_oncall"})
		requests.post(response_url,
			headers={
				"Content-type": "application/json"
			},
			data=json.dumps({
				"text": slack_formatters.make_ep_text(ep.get('escalation_policy')),
				"color": "#25c151",
				"replace_original": True
			})
		)

	def slack_load_options(self, team, user, req):
		endpoint = "escalation_policies"
		query = req.value
		r = pd.request(oauth_token=user["pd_token"], endpoint=endpoint, params={"query": query})

		# Slack dialogs expect "label", interactive message select menus expect "text" :-\
		options_list = [{"text": elem["name"], "label": elem["name"], "value": elem["id"]} for elem in r[endpoint]]
		if len(options_list) == 0:
			options_list.append({"text": "Nothing found.", "value": "nothing"})
		elif len(options_list) == 25:
			options_list.insert(0, {"text": "(> 25 found, please type more letters.)", "value": "nothing"})
		return json.dumps({"options": options_list})


	def slack_command(self, team, user, form):
		response_url = form.get('response_url')

		slack_response = {
			"response_type": "ephemeral",
			"text": "",
			"attachments": [{
				"text": "Choose an escalation policy in domain {}".format(user["pd_subdomain"]),
				"color": "#25c151",
				"attachment_type": "default",
				"callback_id": "eps",
				"actions": [{
					"name": "eps",
					"text": "Pick an EP",
					"type": "select",
					"data_source": "external"
				}]
			}]
		}
		requests.post(response_url,
			json=slack_response,
			headers={'Content-type': 'application/json'}
		)

		return ('', 200)
