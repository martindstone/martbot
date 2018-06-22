import os
import re
import json
import requests
from dotmap import DotMap
from slackclient import SlackClient

import pd
from command import Command

class Services(Command):

	def __init__(self):
		self.name = "services"
		self.patterns = [re.compile(p) for p in [r"^services"]]
		self.status_emoji = {
			"active": ":white_check_mark:",
			"warning": ":warning:",
			"critical": ":octagonal_sign:",
			"maintenance": ":double_vertical_bar:",
			"disabled": ":black_square_for_stop:"
		}

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

		service = pd.request(oauth_token=user.pd_token, endpoint="/services/{}".format(service_id))
		service = DotMap(service.get('service'))

		service_link = "<{}|{}>".format(service.html_url, service.summary)
		ep_link = "<{}|{}>".format(service.escalation_policy.html_url, service.escalation_policy.summary)
		response = ":desktop_computer: Service {} in subdomain {}:\n\n".format(service_link, user.pd_subdomain)
		if service.description and service.description != service.summary:
			response += "Description: {}\n".format(service.description)
		response += "Status: {} {}\n".format(self.status_emoji.get(service.get("status").__str__()), service.get("status").__str__().title())
		response += "Escalation Policy: {}\n".format(ep_link)

		r = requests.post(response_url,
			headers={
				"Content-type": "application/json"
			},
			data=json.dumps({
				"text": response,
				"replace_original": True
			})
		)
