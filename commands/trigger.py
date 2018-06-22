import re
import json
import requests
from dotmap import DotMap
from slackclient import SlackClient

import pd
from command import Command

class Trigger(Command):

	def __init__(self):
		self.name = "trigger"
		self.patterns = [re.compile(p) for p in [r"^trig", r"^page", r"mbtrigger"]]

	def slack_action(self, team, user, req):
		req.pprint()

		sc = SlackClient(team["slack_bot_token"])

		if req.type == "dialog_submission":
			incident = {
				"incident": {
					"type": "incident",
					"title": req.submission.title,
					"service": {
						"id": req.submission.service,
						"type": "service_reference"
					}
				}
			}

			description = req.submission.description or ""
			description += "\n\nIncident opened by @{}: https://www.slack.com/messages/@{}".format(req.user.name, req.user.name)

			incident["incident"]["body"] = {
				"type": "incident_body",
				"details": description
			}

			if req.submission.user:
				incident["incident"]["assignments"] = [
					{
						"assignee": {
							"type": "user_reference",
							"id": req.submission.user
						}
					}
				]
			r = DotMap(pd.request(
				oauth_token=user["pd_token"], 
				endpoint="incidents", 
				method='POST', 
				data=incident
			))

			assignments = ", ".join(["<{}|{}>".format(a.assignee.html_url, a.assignee.summary) for a in r.incident.assignments])
			fields = [
						{
							"title": "Service",
							"value": "<{}|{}>".format(r.incident.service.html_url, r.incident.service.summary),
							"short": True
						},
						{
							"title": "Assigned to",
							"value": assignments,
							"short": True
						}

					]
			slack_response = {
				"response_type": "ephemeral",
				"text": "Created an incident in domain *{}*:".format(user["pd_subdomain"]),
				"attachments": [{
					"text": "*<{}|[#{}]>* {}".format(r.incident.html_url, r.incident.incident_number, self.slack_escape(r.incident.title)),
					"color": "#25c151",
					"attachment_type": "default",
					"fields": fields
				}]
			}
			response_url = req.response_url
			requests.post(response_url,
				json=slack_response,
				headers={'Content-type': 'application/json'}
			)
		return('', 200)


	def slack_load_options(self, team, user, req):
		# req.pprint()
		if req.name == "service":
			endpoint = "services"
		elif req.name == "user":
			endpoint = "users"
		else:
			return('', 200)

		query = req.value
		r = pd.request(oauth_token=user["pd_token"], endpoint=endpoint, params={"query": query})
		options_list = [{"text": elem["name"], "label": elem["name"], "value": elem["id"]} for elem in r[endpoint]]
		if len(options_list) == 0:
			options_list.append({"label": "Nothing found.", "value": "nothing"})
		elif len(options_list) == 25:
			options_list.insert(0, {"label": "-- More than 25 results found!. Please type more letters. --", "value": "nothing"})

		return json.dumps({"options": options_list})


	def validate_submission(self, team, user, req):
		if req.submission.user == "nothing":
			return json.dumps(
				{
					"errors": [
						{
							"name": "user",
							"error": "Please choose a user"
						}
					]
				}
			)
		elif req.submission.service == "nothing":
			return json.dumps(
				{
					"errors": [
						{
							"name": "service",
							"error": "Please choose a service"
						}
					]
				}
			)

	def slack_command(self, team, user, form):
		sc = SlackClient(team["slack_app_token"])
		channel = form.get('channel_id')
		trigger_id = form.get('trigger_id')

		call = sc.api_call("dialog.open",
			trigger_id=trigger_id,
			dialog={
				"callback_id": "trigger",
				"title": "Trigger an incident",
				"submit_label": "Trigger",
				"elements": [
					{
						"name": "service",
						"label": "Service",
						"type": "select",
						"data_source": "external",
						"placeholder": "In PD service"
					},
					{
						"name": "user",
						"label": "User",
						"type": "select",
						"data_source": "external",
						"optional": True,
						"placeholder": "For PD user"
					},
					{
						"name": "title",
						"label": "Title",
						"type": "text",
						"placeholder": "Incident title"
					},
					{
						"name": "description",
						"label": "Description",
						"type": "textarea",
						"optional": True,
						"placeholder": "Optional details"
					}
				]
			}
		)
		return ('', 200)






