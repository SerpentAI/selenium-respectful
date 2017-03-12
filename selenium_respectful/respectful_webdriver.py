from .exceptions import SeleniumRespectfulError, SeleniumRespectfulRateLimitedError

from redis import StrictRedis, ConnectionError

from selenium.webdriver.remote.webdriver import WebDriver

from types import LambdaType

import yaml
import copy
import uuid
import time
import inspect

try:
    FileNotFoundError
except NameError:  # Python 2 Compatibility
    FileNotFoundError = IOError


class RespectfulWebdriver:

    default_config = {
        "redis": {
            "host": "localhost",
            "port": 6379,
            "database": 0
        },
        "safety_threshold": 0
    }

    def __init__(self, **kwargs):
        self.config = self._load_config()

        self.webdriver = kwargs.get("webdriver")

        if not WebDriver in self.webdriver.__class__.__bases__:
            raise SeleniumRespectfulError("The provided webdriver does not inherit from RemoteWebDriver")

        self.redis = StrictRedis(
            host=self.config["redis"]["host"],
            port=self.config["redis"]["port"],
            db=self.config["redis"]["database"],
        )

        try:
            self.redis.echo("Testing Connection")
        except ConnectionError:
            raise SeleniumRespectfulError("Could not establish a connection to the provided Redis server")

    def __getattr__(self, attr):
        if attr == "get":
            return getattr(self, "_selenium_webdriver_proxy_%s" % attr)
        else:
            return getattr(self.webdriver, attr)

    @property
    def redis_prefix(self):
        return "SeleniumRequester"

    def register_realm(self, realm, max_requests, timespan):
        redis_key = self._realm_redis_key(realm)

        if not self.redis.hexists(redis_key, "max_requests"):
            self.redis.hmset(redis_key, {"max_requests": max_requests, "timespan": timespan})
            self.redis.sadd("%s:REALMS" % self.redis_prefix, realm)

        return True

    def register_realms(self, realm_tuples):
        for realm_tuple in realm_tuples:
            self.register_realm(*realm_tuple)

        return True

    def update_realm(self, realm, **kwargs):
        redis_key = self._realm_redis_key(realm)
        updatable_keys = ["max_requests", "timespan"]

        for updatable_key in updatable_keys:
            if updatable_key in kwargs and type(kwargs[updatable_key]) == int:
                self.redis.hset(redis_key, updatable_key, kwargs[updatable_key])

        return True

    def unregister_realm(self, realm):
        self.redis.delete(self._realm_redis_key(realm))
        self.redis.srem("%s:REALMS" % self.redis_prefix, realm)

        request_keys = self.redis.keys("%s:REQUEST:%s:*" % (self.redis_prefix, realm))
        [self.redis.delete(k) for k in request_keys]

        return True

    def unregister_realms(self, realms):
        for realm in realms:
            self.unregister_realm(realm)

        return True

    def fetch_registered_realms(self):
        return list(map(lambda k: k.decode("utf-8"), self.redis.smembers("%s:REALMS" % self.redis_prefix)))

    def realm_max_requests(self, realm):
        realm_info = self._fetch_realm_info(realm)
        return int(realm_info["max_requests".encode("utf-8")].decode("utf-8"))

    def realm_timespan(self, realm):
        realm_info = self._fetch_realm_info(realm)
        return int(realm_info["timespan".encode("utf-8")].decode("utf-8"))

    def _load_config(self):
        try:
            with open("selenium-respectful.config.yml", "r") as f:
                config = yaml.load(f)

            if "safety_threshold" not in config:
                config["safety_threshold"] = self.__class__.default_config.get("safety_threshold")
            else:
                if not isinstance(config["safety_threshold"], int) or config["safety_threshold"] < 0:
                    raise SeleniumRespectfulError(
                        "'safety_threshold' key must be a positive integer in 'selenium-respectful.config.yml'"
                    )

            if "redis" not in config:
                raise SeleniumRespectfulError("'redis' key is missing from 'selenium-respectful.config.yml'")

            expected_redis_keys = ["host", "port", "database"]
            missing_redis_keys = list()

            for expected_redis_key in expected_redis_keys:
                if expected_redis_key not in config["redis"]:
                    missing_redis_keys.append(expected_redis_key)

            if len(missing_redis_keys):
                raise SeleniumRespectfulError(
                    "'%s' %s missing from the 'redis' configuration key in 'selenium-respectful.config.yml'" % (
                        ", ".join(missing_redis_keys),
                        "is" if len(missing_redis_keys) == 1 else "are"
                    )
                )
        except FileNotFoundError:
            return copy.deepcopy(self.__class__.default_config)

    def _can_perform_get(self, realm):
        return self._requests_in_timespan(realm) < (self.realm_max_requests(realm) - self.config["safety_threshold"])

    def _realm_redis_key(self, realm):
        return "%s:REALMS:%s" % (self.redis_prefix, realm)

    def _fetch_realm_info(self, realm):
        redis_key = self._realm_redis_key(realm)
        return self.redis.hgetall(redis_key)

    def _requests_in_timespan(self, realm):
        return len(
            self.redis.scan(
                cursor=0,
                match="%s:REQUEST:%s:*" % (self.redis_prefix, realm),
                count=self._redis_keys_in_db() + 100
            )[1]
        )

    def _redis_keys_in_db(self):
        return self.redis.info().get("db%d" % self.config["redis"]["database"]).get("keys")

    def _selenium_webdriver_proxy_get(self, *args, **kwargs):
        realms = kwargs.pop("realms", list())

        if not len(realms):
            raise SeleniumRespectfulError("'realms' is a required kwarg")

        wait = kwargs.pop("wait", False)

        return self._webdriver_get(lambda: self.webdriver.get(*args, **kwargs), realms=realms, wait=wait)

    def _webdriver_get(self, get_func, realms=None, wait=False):
        registered_realms = self.fetch_registered_realms()

        for realm in realms:
            if realm not in registered_realms:
                raise SeleniumRespectfulError("Realm '%s' hasn't been registered" % realm)

        if wait:
            while True:
                try:
                    return self._perform_webdriver_get(get_func, realms=realms)
                except SeleniumRespectfulRateLimitedError:
                    pass

                time.sleep(1)
        else:
            return self._perform_webdriver_get(get_func, realms=realms)

    def _perform_webdriver_get(self, get_func, realms=None):
        self._validate_get_func(get_func)

        rate_limited_realms = list()

        for realm in realms:
            if not self._can_perform_get(realm):
                rate_limited_realms.append(realm)

        if not len(rate_limited_realms):
            for realm in realms:
                request_uuid = str(uuid.uuid4())

                self.redis.setex(
                    name="%s:REQUEST:%s:%s" % (self.redis_prefix, realm, request_uuid),
                    time=self.realm_timespan(realm),
                    value=request_uuid
                )

            return get_func()
        else:
            raise SeleniumRespectfulRateLimitedError(
                "Currently rate-limited on Realm(s): %s" % ", ".join(rate_limited_realms))

    @staticmethod
    def _validate_get_func(get_func):
        if not isinstance(get_func, LambdaType):
            raise SeleniumRespectfulError("'get_func' is expected to be a lambda")

        get_func_string = inspect.getsource(get_func)
        post_lambda_string = get_func_string.split(":")[1].strip()

        if not post_lambda_string.startswith("self.webdriver.get"):
            raise SeleniumRespectfulError("The lambda can only contain a self.webdriver.get function call")
