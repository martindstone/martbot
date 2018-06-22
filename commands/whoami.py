import re
from dotmap import DotMap
from slackclient import SlackClient

import pd
from command import Command

class Whoami(Command):
	def __init__(self):
		self.name = "whoami"
		self.patterns = [re.compile(p) for p in [r"^whoami", r"who am i"]]

	def slack_event(self, team, user, req):
		me = DotMap(pd.request(oauth_token=user["pd_token"], endpoint="users/me"))
		sc = SlackClient(team["slack_bot_token"])
		sc.api_call("chat.postMessage",
			channel=req.event.channel,
			text="You're *{}* in domain *{}*".format(me.user.email, user["pd_subdomain"])
		)
