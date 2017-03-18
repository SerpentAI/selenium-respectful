# selenium-respectful

[Selenium](http://www.seleniumhq.org/) is already a well-known player when it comes to browser automation and is usually a part of any serious integration testing stack. That being said, it is also an increasingly popular choice for web scraping. Now APIs are usually the ones with detailed rate-limiting systems but if you are the type of person that understands that web scraping is sometimes necessary and you intend to be relatively gentle about it, *selenium-respectful* might be for you!

***selenium-respectful***:

* Is a minimalist wrapper for any *Selenium Webdriver* to work within rate limits of any amount of services simultaneously
* Can scale out of a single thread, single process or even a single machine
* Enables maximizing your allowed requests without ever going over set limits and having to handle the fallout
* Overloads the Webdriver's *get* method and relays any other valid calls
* Works with both Python 2 and 3 and is thoroughly tested
* Is a sister library to the already established [requests-respectful](https://github.com/SerpentAI/requests-respectful)

**Typical *Selenium* get call**

```python
from selenium.webdriver.chrome.webdriver import WebDriver
driver = WebDriver()

driver.get("http://github.com")
element = driver.find_element_by_tag_name("body")
```

**Get call with *selenium-respectful***

```python
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium_respectful import RespectfulWebdriver

driver = RespectfulWebdriver(webdriver=WebDriver())

# This can be done elsewhere but the realm needs to be registered!
driver.register_realm("Github", max_requests=100, timespan=60)

driver.get("http://github.com", realms=["Github"], wait=True)
element = driver.find_element_by_tag_name("body")  # Works as usual!
```

## Requirements

* [Redis](http://redis.io/) > 2.8.0 (See FAQ if you are rolling your eyes)

## Installation

```shell
pip install selenium-respectful
```

## Configuration

### Default Configuration Values
```python
{
    "redis": {
        "host": "localhost",
        "port": 6379,
        "database": 0
    },
    "safety_threshold": 10
}
```

### Configuration Keys

* **redis**: Provides the `host`, `port`and `database` of the Redis instance
* **safety_threshold**: A rate-limited exception will be raised at *(realm_max_requests - safety_threshold)*. Prevents going over the limit of services in scenarios where a large amount of requests are issued in parallel

### Overriding Configuration Values

#### With *selenium-respectful.config.yml*

The library auto-detects the presence of a YAML file named *selenium-respectful.config.yml* at the root of your project and will attempt to load configuration values from it.

**Example**:

selenium-respectful.config.yml
```yaml
redis:
	host: 0.0.0.0
    port: 6379
    database: 5

safety_threshold: 25
```

**The resulting active configuration would be:**
```python
RespectfulWebdriver(webdriver=WebDriver()).config

Out[1]: {
    "redis": {
        "host": "0.0.0.0",
        "port": 6379,
        "database": 5
    },
    "safety_threshold": 25
}
```


## Usage

In your quest to use *selenium-respectful*, you should only ever have to bother with one class: *RespectfulWebdriver*. Instance this class and you can perform all important operations.

Before each example, it is assumed that the following code has already been executed.
```python
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium_respectful import RespectfulWebdriver

driver = RespectfulWebdriver(webdriver=WebDriver())
```

### Realms

Realms are simply named containers that are provided with a maximum requesting rate. You are responsible of the management (i.e. CRUD) of your realms.

Realms track the HTTP requests that are performed under them and will raise a catchable rate limit exception if you are over their allowed requesting rate.

#### Fetching the list of Realms
```python
driver.fetch_registered_realms()
```

This returns a list of currently registered realm names.

#### Registering a Realm
```python
driver.register_realm("Google", max_requests=10, timespan=1)
driver.register_realm("Github", max_requests=100, timespan=60)
driver.register_realm("Twitter", max_requests=150, timespan=300)

# OR
realm_tuples = [
    ["Google", 10, 1],
    ["Github", 100, 60],
    ["Twitter", 150, 300]
]

driver.register_realms(realm_tuples)
```

Either of these registers 3 realms:
* *Google* at a maximum requesting rate of 10 requests per second
* *Github* at a maximum requesting rate of 100 requests per minute
* *Twitter* at a maximum requesting rate of 150 requests per 5 minutes

#### Updating a Realm
```python
driver.update_realm("Google", max_requests=25, timespan=5)
```

This updates the maximum requesting rate of *Google* to 25 requests per 5 seconds.

#### Getting the maximum requests value of a Realm
```python
driver.realm_max_requests("Google")
```

This would return 25.

#### Getting the timespan value of a Realm
```python
driver.realm_timespan("Google")
```

This would return 5.

#### Unregistering a Realm
```python
driver.unregister_realm("Google")
```

This would unregister the *Google* realm, preventing further queries from executing on it.

#### Unregistering multiple Realms
```python
driver.unregister_realms(["Google", "Github", "Twitter"])
```

This would unregister all 3 realms in one operation, preventing further queries from executing on them.

### Requesting

#### Using the *Selenium Webdriver* get method

To pilot your web browser to a given URL, just use the *get* method as you would normally do with your WebDriver instance. The only major difference is that a *realms* kwarg is expected. A *wait* boolean kwargs can also be provided (the behavior is explained later).


Example of a valid call:
```python
driver.get("http://github.com", realms=["GitHub"])
```

If not rate-limited, it would direct the browser to the provided URL.

#### Multiple realms per request

You can have a single request count against multiple realms if it makes sense in your use case.

```python
driver.get("http://github.com", realms=["GitHub", "GitHubUser123", "GitHubServer3"])
```

#### Handling exceptions

Executing these *get* calls will either perform the action in the browser or raise a SeleniumRespectfulRateLimitedError exception. This means that you'll likely want to catch and handle that exception.

```python
from selenium_respectful import SeleniumRespectfulRateLimitedError

try:
	driver.get("http://github.com", realm="GitHub")
except SeleniumRespectfulRateLimitedError:
	pass # Possibly requeue that call or wait.
```

#### The *wait* kwarg

Requesting with a *get* call accepts a *wait* kwarg that defaults to False. If switched on and the realm is currently rate-limited, the process will block, wait until it is safe to send requests again and perform the requests then. Waiting is perfectly fine for scripts or smaller operations but is discouraged for large, multi-realm, parallel tasks (i.e. Background Tasks like Celery workers).

## Tests

* Exist? `Yes`
* Exhaustive? `Yes`
* Facepalm tactics? `Yes -  Redis calls aren't mocked and google.com gets a few friendly calls`

Run them with `python -m pytest tests --spec`

## FAQ

### Whoa, whoa, whoa! Redis?!

Yes. The use of Redis allows for *selenium-respectful* to go multi-thread, multi-process and even multi-machine while still respecting the maximum requesting rates of registered realms. Operations like Redis' SETEX are key in designing and working with rate-limiting systems. If you are doing Python development, there is a decent chance you already work with Redis as it is one of the two options to use as Celery's backend and one of the 2 major caching options in Web development. If not, you can always keep things clean and use a [Docker Container](https://hub.docker.com/_/redis/) or even [build it from source](http://redis.io/download#installation). Redis has kept a consistent record over the years of being lightweight, solid software.