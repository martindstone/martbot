from dotmap import DotMap

incident_status_emoji = {
	"acknowledged": ":warning:",
	"triggered": ":octagonal_sign:",
	"resolved": ":white_check_mark:"
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