import re
import abc
from dotmap import DotMap
from slackclient import SlackClient

class Command:

	def __init__(self):
		self.name = "command base class"
		self.patterns = []

	def get_name(self):
		return self.name

	def slack_escape(self, str):
		return str.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

	@abc.abstractmethod
	def matches(self, message_text):
		match = None
		for pattern in self.patterns:
			match = pattern.search(re.sub(r"^<[^\s]+> ", "", message_text))
			if match:
				break
		return match

	@abc.abstractmethod
	def slack_event(self, team, user, req):
		pass

	@abc.abstractmethod
	def slack_action(self, team, user, req):
		pass