# Logging

You can view live logs using any of the links below
(requires gcloud project operator permissions).

- [Dev](https://uwiam.page.link/dev-directory-logs)
- [Eval](https://uwiam.page.link/eval-directory-logs)
- [Prod](https://uwiam.page.link/prod-directory-logs)
  
Our logs are emitted as JSON (with the exception of a few that are emitted before
the JSON handler is created). To see what and how we log, check out the 
[example payload](#log-json). When viewing the logs in google (using the links above),
the payload is in the logs `jsonPayload` field.

## Configuration 

Logging is configured in [settings](../husky_directory/settings/logging.yml).
You shouldn't need to mess with it unless you need to adjust log levels or add
some new feature.


## Emitting logs using the application logger

Dependency injection allows you to use the basic application log anywhere 
without setting up a new logger. This is the recommended way to emit logs, 
as long as you are working in an injected context:

```
from injector import inject
from logging import Logger

class MyThing:
    @inject
    def __init__(self, logger: Logger):
        self.logger = logger
       
    def do_work(self):
        self.logger.info('Hi')
```

## Creating a new logger

To create a new logger, always make it a child of the `gunicorn.error.app` logger.
Creating a new logger is useful when you want to be able to quickly filter
logs of a certain type, just by searching for those emitted by the 
logger you've created.

```
import logging

logger = logging.getLogger('gunicorn.error.app').getChild('greetings')
logger.info('hello')
```

The log statement would appear in our logs as coming from the `app.greetings` logger.

An alternative approach (using dependency injection) would be to use the application 
logger to create the child:

```
from injector import inject
from logging import Logger

class MyThing:
    @inject
    def __init__(self, app_logger: Logger):
        self.logger = app_logger.getChild('greetings')
       
    def do_work(self):
        self.logger.info('Hi')
```


## Log JSON


Here is an example payload:

```javascript
{
    // The line field shows where the log was emitted, but
    // be aware this can be misleading if you have a shared
    // function/decorator emitting logs.
    line: "pws.py#_get_search_request_output:101",
    
    // The logger field shows the name of the logger that emitted it.
    // Internally, these loggers are prefixed with `gunicorn.error`, but
    // this is filtered on the output to make it less scary to read.
    logger: "app",
   
    // This is the message supplied to the logger. Nothing more, nothing less.
    message: "Hello, world",
        
    // If the log was emitted within a request context, the request 
    // information is included.    
    request: {
        // The python-internal object id for the request, can be useful
        // in order to see all logs associated with a single request.
        // This id is not considered unique or deterministic. Don't rely
        // on it too much.
        id: 123456,
       
        // The request method. 
        method: "POST",
            
        // The IP address the request came from, to the
        // extent that it is known.     
        remoteIp: "127.0.0.1",   
       
        // The url requested by the user     
        url: "https://directory.uw.edu",
        
        // If the request was authenticated, the netid of the user
        // who made the request will be included in the payload
        uwnetid: "husky"
    }        
    // Some logs may include a timer payload that describes
    // a timer that was run, and how long it took.
    // These logs usually go to the `app.timer` logger, so
    // they can easily be filtered and searched for trends.
    timer: {
        // The hard-coded name of the timer.
        name: "search_directory",
        
        // The number of seconds the timer ran
        result: .84 ,

        // The unix epoch timestamps, the diffrence
        // of which gives the above result.
        startTime: 1630514380.506965,
        endTime: 1630514381.4943926
    },
    // Some logs include query information to make it easy to find
    // queries that take a long time.
    query: {
       includeTestIdentities: false,  // always false for now
       // Note that depending on how the user searches, 
       // certain fields may be absent; only fields that
       // were used to filter the search are included.
       // In this case, a user searched for anyone with the name 'mae' 
       name: "mae",
       // The population field will be 'employees', 'students', or 'all'
       population : "employees" 
    }
}
```
