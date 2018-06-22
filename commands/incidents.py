import re
import json
import requests
from dotmap import DotMap
from slackclient import SlackClient

import pd
from command import Command

class Incidents(Command):

	def __init__(self):
		self.name = "incidents"
		self.patterns = [re.compile(p) for p in [r"^incidents", r"^mbincidents"]]
		self.status_emoji = {
			"acknowledged": ":warning:",
			"triggered": ":octagonal_sign:"
		}

	def slack_event(self, team, user, req):
		sc = SlackClient(team["slack_bot_token"])
		message_text = req.event.text or req.event.message.text
		search = re.search("^incidents( .*)$", message_text)

		incidents = pd.fetch_incidents(oauth_token=user["pd_token"])

		if not incidents:
			sc.api_call("chat.postMessage",
				channel=req.event.channel,
				text="There are currently no open incidents in domain *{}*".format(user["pd_subdomain"])
			)
			return

		attachments = [{
			"text": "{} *<{}|[#{}]>* {}".format(self.status_emoji[incident["status"]], incident["html_url"], incident["incident_number"], self.slack_escape(incident["description"])),
			"color": "#25c151",
			"attachment_type": "default"
		} for incident in pd.fetch_incidents(oauth_token=user["pd_token"])]

		sc.api_call("chat.postMessage",
			channel=req.event.channel,
			text="Open incidents in domain *{}*:".format(user["pd_subdomain"]),
			attachments=attachments
		)

	def slack_action(self, team, user, req):
		incident_id = req.actions[0].selected_options[0].value
		response_url = req.response_url

		incident = pd.request(oauth_token=user.pd_token, endpoint="/incidents/{}".format(incident_id))
		incident = DotMap(incident.get('incident'))

		incident_link = "*<{}|[#{}]>* {}".format(incident.html_url, incident.incident_number, incident.title)
		response = "{} {}".format(self.status_emoji[incident.status], incident_link)

		assignments = ", ".join(["<{}|{}>".format(a.assignee.html_url, a.assignee.summary) for a in incident.assignments])
		fields = [
			{
				"title": "Service",
				"value": "<{}|{}>".format(incident.service.html_url, incident.service.summary),
				"short": True
			},
			{
				"title": "Assigned to",
				"value": assignments,
				"short": True
			}

		]
		r = requests.post(response_url,
			headers={
				"Content-type": "application/json"
			},
			data=json.dumps({
				"text": "",
				"attachments": [{
					"text": response,
					"color": "#25c151",
					"attachment_type": "default",
					"fields": fields
				}],
				"replace_original": True
			})
		)


	def slack_load_options(self, team, user, req):
		endpoint = "incidents"
		query = req.value
		r = pd.request(oauth_token=user["pd_token"], endpoint=endpoint, params={"query": query, "statuses[]": ["triggered", "acknowledged"]})

		# Slack dialogs expect "label", interactive message select menus expect "text" :-\
		options_list = [{"text": elem["summary"], "label": elem["summary"], "value": elem["id"]} for elem in r[endpoint]]
		if len(options_list) == 0:
			options_list.append({"text": "Nothing found.", "value": "nothing"})
		elif len(options_list) == 25:
			options_list.append({"text": "See more incidents...", "value": "more:{}".format(0)})
		return json.dumps({"options": options_list})


	def slack_command(self, team, user, form):
		response_url = form.get('response_url')

		slack_response = {
			"response_type": "ephemeral",
			"text": "",
			"attachments": [{
				"text": "Choose an incident in domain *{}*:".format(user["pd_subdomain"]),
				"color": "#25c151",
				"attachment_type": "default",
				"callback_id": "incidents",
				"actions": [{
					"name": "incidents",
					"text": "Pick an incident",
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










