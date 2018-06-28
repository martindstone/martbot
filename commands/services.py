import os
import re
import json
import requests
from dotmap import DotMap
from slackclient import SlackClient

import pd
import slack_formatters
from command import Command

class Services(Command):

	def __init__(self):
		self.name = "services"
		self.patterns = [re.compile(p) for p in [r"^services", r"^mbserv"]]

	def slack_event(self, team, user, req):
		sc = SlackClient(team["slack_bot_token"])

		message_text = req.event.text or req.event.message.text
		search = re.search("^services( .*)$", message_text)
		services = None
		response = None
		valid_arg = False
		if search and len(search.groups()) == 1:
			arg = search.groups()[0].strip()
			if re.search("^trig|^red|^crit", arg):
				valid_arg = True
				response = "Critical services in subdomain *{}*:\n".format(user["pd_subdomain"])
				services = [service for service in pd.fetch_services(oauth_token=user["pd_token"]) if service.get("status") == "critical"]
				for service in services:
					response += "\t{} <{}|{}>\n".format(self.status_emoji.get(service.get("status")), service.get("html_url"), service.get("summary"))
			elif re.search("^ack|^orange|^amber|^warn", arg):
				valid_arg = True
				response = "Warning services in subdomain *{}*:\n".format(user["pd_subdomain"])
				services = [service for service in pd.fetch_services(oauth_token=user["pd_token"]) if service.get("status") == "warning"]
				for service in services:
					response += "\t{} <{}|{}>\n".format(self.status_emoji.get(service.get("status")), service.get("html_url"), service.get("summary"))
			elif re.search("^all|list", arg):
				valid_arg = True
				response = "All services in subdomain *{}*:\n".format(user["pd_subdomain"])
				services = pd.fetch_services(oauth_token=user["pd_token"])
				for service in services:
					response += "\t{} <{}|{}> ({})\n".format(self.status_emoji.get(service.get("status")), service.get("html_url"), service.get("summary"), service.get("status"))

			if services:
				sc.api_call("chat.postMessage",
					channel=req.event.channel,
					text=response
				)
			else:
				sc.api_call("chat.postMessage",
					channel=req.event.channel,
					text="No services found for *{}*".format(message_text)
				)
			return


		services = [{"text": service["summary"], "value": service["id"]} for service in pd.fetch_services(oauth_token=user["pd_token"])]

		sc.api_call("chat.postMessage",
			channel=req.event.channel,
			attachments=[{
				"text": "Choose a service in domain {}".format(user["pd_subdomain"]),
				"color": "#25c151",
				"attachment_type": "default",
				"callback_id": req.event.text or req.event.message.text,
				"actions": [{
					"name": "services_list",
					"text": "Pick a service",
					"type": "select",
					"options": services
				}]
			}])

	def slack_action(self, team, user, req):
		service_id = req.actions[0].selected_options[0].value
		response_url = req.response_url

		if re.search(r"brief", req.callback_id):
			expand_ep = False
		else:
			expand_ep = True

		service = pd.request(oauth_token=user.pd_token, endpoint="/services/{}".format(service_id))

		r = requests.post(response_url,
			headers={
				"Content-type": "application/json"
			},
			json={
				"text": slack_formatters.make_service_text(service.get('service'), expand_ep=expand_ep, pd_token=user["pd_token"]),
				"replace_original": True
			}
		)

	def slack_load_options(self, team, user, req):
		endpoint = "services"
		query = req.value
		r = pd.request(oauth_token=user["pd_token"], endpoint=endpoint, params={"query": query})

		# Slack dialogs expect "label", interactive message select menus expect "text" :-\
		options_list = [{"text": elem["summary"], "label": elem["summary"], "value": elem["id"]} for elem in r[endpoint]]
		if len(options_list) == 0:
			options_list.append({"text": "Nothing found.", "value": "nothing"})
		elif len(options_list) == 25:
			options_list.append({"text": "See more services...", "value": "more:{}".format(0)})
		return json.dumps({"options": options_list})


	def slack_command(self, team, user, form):
		response_url = form.get('response_url')
		command_text = form.get('text')

		if re.search(r"list|all|trig|red|crit|ack|orange|amber|warn|open", command_text):
			services = pd.fetch_services(oauth_token=user["pd_token"])
			if re.search(r"trig|red|crit", command_text):
				response_text = "Critical services"
				services = [service for service in services if service.get("status") == "critical"]
			elif re.search(r"ack|orange|amber|warn", command_text):
				response_text = "Warning services"
				services = [service for service in services if service.get("status") == "warning"]
			elif re.search(r"open", command_text):
				response_text = "Services with open incidents"
				services = [service for service in services if service.get("status") == "warning" or service.get("status") == "critical"]
			else:
				response_text = "All services"

			response_text += " in domain *{}*:\n".format(user["pd_subdomain"])

			if services:
				response_text += slack_formatters.make_services_list(services)
			else:
				response_text += "\tNo services found."

			slack_response = {
				"text": response_text,
				"replace_original": True
			}
		else:
			slack_response = {
				"response_type": "ephemeral",
				"text": "",
				"attachments": [{
					"text": "Choose a service in domain *{}*:".format(user["pd_subdomain"]),
					"color": "#25c151",
					"attachment_type": "default",
					"callback_id": "services {}".format(command_text),
					"actions": [{
						"name": "services",
						"text": "Pick a service",
						"type": "select",
						"data_source": "external"
					}	]
				}]
			}

		requests.post(response_url,
			json=slack_response,
			headers={'Content-type': 'application/json'}
		)

		return ('', 200)
