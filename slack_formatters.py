import re
import dateparser
from dotmap import DotMap

import pd

incident_status_emoji = {
	"acknowledged": ":warning:",
	"triggered": ":octagonal_sign:",
	"resolved": ":white_check_mark:"
}

service_status_emoji = {
	"active": ":white_check_mark:",
	"warning": ":warning:",
	"critical": ":octagonal_sign:",
	"maintenance": ":double_vertical_bar:",
	"disabled": ":black_square_for_stop:"
}

def make_incident_attachments(incident):
	# call with incident as whatever is in the incident body; it could be
	# response['incident'] in the case of GET /incidents/{id}, or 
	# response['incidents'][0] in the case of PUT /incidents
	incident = DotMap(incident)
	incident_id = incident.id

	incident_link = "*<{}|[#{}]>* {}".format(incident.html_url, incident.incident_number, incident.title)
	response = "{} {}".format(incident_status_emoji[incident.status], incident_link)

	assignments = ", ".join(["<{}|{}>".format(a.assignee.html_url, a.assignee.summary) for a in incident.assignments])
	fields = [
		{
			"title": "Status",
			"value": incident.status.title(),
			"short": True
		},
		{
			"title": "Service",
			"value": "<{}|{}>".format(incident.service.html_url, incident.service.summary),
			"short": True
		}
	]

	actions = []

	if incident.status == "triggered" or incident.status == "acknowledged":
		fields.append({
			"title": "Assigned To",
			"value": assignments,
			"short": True				
		})
		actions.extend([
			{
				"name": "acknowledge",
				"text": "Acknowledge",
				"type": "button",
				"value": incident_id
			},
			{
				"name": "resolve",
				"text": "Resolve",
				"type": "button",
				"value": incident_id
			}
		])
	actions.append({
		"name": "annotate",
		"text": "Add Note",
		"type": "button",
		"value": incident_id
	})

	attachments = [{
		"text": response,
		"color": "#25c151",
		"attachment_type": "default",
		"fields": fields,
		"callback_id": "incidents",
		"actions": actions
	}]
	return attachments


def make_ep_text(ep, include_intro=True):
	# call with ep as the EP body, like response.get('escalation_policy')
	ep = DotMap(ep)

	ep_link = "<{}|{}>".format(ep.html_url, ep.summary)
	subdomain = re.match(r"https://([^\.]+)", ep.html_url).groups()[0]

	response = ""

	if include_intro:
		response += ":arrow_forward: Escalation Policy *{}* in subdomain *{}*:\n\n".format(ep_link, subdomain)

	if ep.description and ep.description != ep.summary:
		response += "Description: {}\n".format(ep.description)

	for i, rule in enumerate(ep.escalation_rules):
		if i == 0:
			response += "\t*Level 1:* Immediately after an incident is triggered, notify:\n"
		else:
			response += "\t*Level {}:* Notify:\n".format(i+1)

		for oncall in rule.current_oncalls:
			if oncall.escalation_target.type == "user_reference":
				response += "\t\t:slightly_smiling_face: Always on call: *{}*\n".format(oncall.user.name)
			else:
				sch_link = "<{}|{}>".format(oncall.escalation_target.html_url, oncall.escalation_target.summary)
				user_link = "<https://{}.pagerduty.com/users/{}|{}>".format(subdomain, oncall.user.id, oncall.user.name)

				response += "\t\t:date: Schedule: *{}*\n\t\t\t\t:slightly_smiling_face: On call now: *{}* ".format(sch_link, user_link)

				start = dateparser.parse(oncall.start)
				end = dateparser.parse(oncall.end)
				startts = int(start.timestamp())
				endts = int(end.timestamp())

				response += "(<!date^{}^{{date_num}} {{time}}|{}> - <!date^{}^{{date_num}} {{time}}|{}>)\n".format(startts, start, endts, end)

		response += "\t\t_Escalates after *{} minutes*_\n\n".format(rule.escalation_delay_in_minutes)

	if ep.num_loops > 0:
		response += "\t_:arrows_counterclockwise: Repeats *{} times* if no one acknowledges incidents_".format(ep.num_loops)
	else:
		response += "\t:arrows_counterclockwise: _Does not repeat_"

	return response


def make_service_text(service, expand_ep=False, pd_token=None):
	# call with service as the service body, like response.get('service')
	service = DotMap(service)
	service_link = "<{}|{}>".format(service.html_url, service.summary)
	subdomain = re.match(r"https://([^\.]+)", service.html_url).groups()[0]
	response = ":desktop_computer: Service *{}* in subdomain *{}*:\n\n".format(service_link, subdomain)
	if service.description and service.description != service.summary:
		response += "Description: {}\n".format(service.description)
	response += "Status: {} {}\n".format(service_status_emoji.get(service.status), service.status.title())
	ep_link = "<{}|{}>".format(service.escalation_policy.html_url, service.escalation_policy.summary)
	response += "Escalation Policy: *{}*\n".format(ep_link)
	if expand_ep and pd_token:
		ep = pd.request(
			oauth_token=pd_token,
			endpoint="escalation_policies/{}".format(service.escalation_policy.id),
			method="GET",
			params={"include[]": "current_oncall"}
		)
		response += make_ep_text(ep.get('escalation_policy'), include_intro=False)

	return response

def make_services_list(services):
	# call with services endpoint output
	if not services:
		return
	subdomain = re.match(r"https://([^\.]+)", services[0].get("html_url")).groups()[0]
	response = ""
	for service in services:
		response += "\t{} <{}|{}>\n".format(service_status_emoji.get(service.get("status")), service.get("html_url"), service.get("summary"))

	return response