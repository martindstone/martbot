# martbot

Martbot is a Slack app that uses PD OAuth to connect to PagerDuty. Advantages of this approach are that the need to manually enter PD API tokens is eliminated, and that each Slack user in the workspace can independently log in to whatever PD domain and username they choose.

## Implementation

Martbot is implemented in Python and Flask. It's designed to be deployable to Heroku with a minimum of fuss. It needs the following environment variables to be set:

* FLASK_SECRET_KEY: Secret key for Flask session hashing
* MONGODB_URI: URI of a Mongo DB instance (defaults to localhost, Heroku sets this if you use mLab addon)
* PD_CLIENT_ID: Client ID from PagerDuty App Directory
* SERVER_NAME: The host part of the URLs the app provides
* SLACK_APP_ID: App ID from Slack app settings
* SLACK_CLIENT_ID: Client ID from Slack app settings
* SLACK_CLIENT_SECRET: Client secret from Slack app settings

You'll also need to set up an app in Slack, and one in the PD App Directory (TODO: Explain how)

Commands are in the commands/ subdirectory and extend the Command base class. The idea is to make it easy to add your own commands, but admittedly this could be easier than it is now. 

A Command subclass should set these variables in its `__init__` method:
* self.name: a single word that is the command's well-known name, e.g. "services"
* self.patterns: an array of compiled re's that, if they match the event text, means that this class wants to process the event

A Command subclass can implement the following methods:

* slack_event: called if the text of a bot mention or DM matches self.patterns
* slack_action: called from your command's interactive messages (if it uses them)
* slack_load_options: called if your command has select controls with external data sources
* slack_command: called if your app implements a slash command

For now, have a look at some of the existing commands for an idea of how to implement your own...
