# -*- coding: utf-8 -*-
import pytest

from selenium_respectful import RespectfulWebdriver
from selenium_respectful import SeleniumRespectfulError, SeleniumRespectfulRateLimitedError

import redis

from selenium.webdriver.remote.webdriver import WebDriver as BaseWebDriver
from selenium.webdriver.phantomjs.webdriver import WebDriver

webdriver = WebDriver()


# Tests
def test_setup():
    driver = RespectfulWebdriver(webdriver=webdriver)
    driver.unregister_realm("TEST123")


def test_the_class_should_provide_a_default_configuration():
    assert isinstance(getattr(RespectfulWebdriver, "default_config"), dict)
    assert "redis" in RespectfulWebdriver.default_config
    assert "safety_threshold" in RespectfulWebdriver.default_config


def test_the_instance_should_have_a_property_that_holds_the_config():
    driver = RespectfulWebdriver(webdriver=webdriver)
    assert isinstance(driver.config, dict)


def test_the_instance_should_have_a_property_that_holds_a_valid_webdriver():
    driver = RespectfulWebdriver(webdriver=webdriver)
    assert BaseWebDriver in driver.webdriver.__class__.__bases__


def test_the_instance_should_reject_invalid_webdrivers():
    with pytest.raises(SeleniumRespectfulError):
        driver = RespectfulWebdriver(webdriver="Totally a webdriver!")


def test_the_instance_should_have_a_property_that_holds_a_redis_object():
    driver = RespectfulWebdriver(webdriver=webdriver)
    assert isinstance(driver.redis, redis.StrictRedis)


def test_the_instance_should_have_a_property_that_holds_a_redis_prefix():
    driver = RespectfulWebdriver(webdriver=webdriver)
    assert driver.redis_prefix == "SeleniumRequester"


def test_the_instance_should_be_able_to_generate_a_redis_key_when_provided_with_a_realm():
    driver = RespectfulWebdriver(webdriver=webdriver)

    assert driver._realm_redis_key("TEST") == "%s:REALMS:TEST" % driver.redis_prefix
    assert driver._realm_redis_key("TEST2") == "%s:REALMS:TEST2" % driver.redis_prefix
    assert driver._realm_redis_key("TEST SPACED") == "%s:REALMS:TEST SPACED" % driver.redis_prefix
    assert driver._realm_redis_key("TEST ÉÉÉ") == "%s:REALMS:TEST ÉÉÉ" % driver.redis_prefix


def test_the_instance_should_be_able_to_register_a_realm():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.register_realm("TEST123", max_requests=100, timespan=300)

    assert driver.realm_max_requests("TEST123") == 100
    assert driver.realm_timespan("TEST123") == 300
    assert driver.redis.sismember("%s:REALMS" % driver.redis_prefix, "TEST123")

    driver.unregister_realm("TEST123")


def test_the_instance_should_be_able_to_register_multiple_realms():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.register_realm("TEST123", max_requests=100, timespan=300)

    realm_tuples = [
        ["TEST123", 100, 300],
        ["TEST234", 200, 600],
        ["TEST345", 300, 900],
    ]

    driver.register_realms(realm_tuples)

    assert driver.realm_max_requests("TEST123") == 100
    assert driver.realm_timespan("TEST123") == 300
    assert driver.redis.sismember("%s:REALMS" % driver.redis_prefix, "TEST123")

    assert driver.realm_max_requests("TEST234") == 200
    assert driver.realm_timespan("TEST234") == 600
    assert driver.redis.sismember("%s:REALMS" % driver.redis_prefix, "TEST234")

    assert driver.realm_max_requests("TEST345") == 300
    assert driver.realm_timespan("TEST345") == 900
    assert driver.redis.sismember("%s:REALMS" % driver.redis_prefix, "TEST345")

    driver.unregister_realm("TEST123")
    driver.unregister_realm("TEST234")
    driver.unregister_realm("TEST345")


def test_the_instance_should_not_overwrite_when_registering_a_realm():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.register_realm("TEST123", max_requests=100, timespan=300)
    driver.register_realm("TEST123", max_requests=1000, timespan=3000)

    assert driver.realm_max_requests("TEST123") == 100
    assert driver.realm_timespan("TEST123") == 300

    driver.unregister_realm("TEST123")


def test_the_instance_should_be_able_to_update_a_registered_realm():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.register_realm("TEST123", max_requests=100, timespan=300)
    driver.update_realm("TEST123", max_requests=1000, timespan=3000)

    assert driver.realm_max_requests("TEST123") == 1000
    assert driver.realm_timespan("TEST123") == 3000

    driver.unregister_realm("TEST123")


def test_the_instance_should_be_able_to_fetch_a_list_of_registered_realms():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.register_realm("TEST123", max_requests=100, timespan=300)

    assert "TEST123" in driver.fetch_registered_realms()

    driver.unregister_realm("TEST123")


def test_the_instance_should_ignore_invalid_values_when_updating_a_realm():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.register_realm("TEST123", max_requests=100, timespan=300)
    driver.update_realm("TEST123", max_requests="FOO", timespan="BAR", fake=True)

    assert driver.realm_max_requests("TEST123") == 100
    assert driver.realm_timespan("TEST123") == 300

    driver.unregister_realm("TEST123")


def test_the_instance_should_be_able_to_unregister_a_realm():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.register_realm("TEST123", max_requests=100, timespan=300)

    driver.get("http://google.com", realms=["TEST123"])

    driver.unregister_realm("TEST123")

    assert driver.redis.get(driver._realm_redis_key("TEST123")) is None
    assert not driver.redis.sismember("%s:REALMS" % driver.redis_prefix, "TEST123")
    assert not len(driver.redis.keys("%s:REQUESTS:%s:*" % (driver.redis_prefix, "TEST123")))


def test_the_instance_should_be_able_to_unregister_multiple_realms():
    driver = RespectfulWebdriver(webdriver=webdriver)

    realm_tuples = [
        ["TEST123", 100, 300],
        ["TEST234", 200, 600],
        ["TEST345", 300, 900],
    ]

    driver.register_realms(realm_tuples)

    driver.get("http://google.com", realms=["TEST123", "TEST234", "TEST345"])

    driver.unregister_realms(["TEST123", "TEST234", "TEST345"])

    assert driver.redis.get(driver._realm_redis_key("TEST123")) is None
    assert not driver.redis.sismember("%s:REALMS" % driver.redis_prefix, "TEST123")
    assert not len(driver.redis.keys("%s:REQUESTS:%s:*" % (driver.redis_prefix, "TEST123")))

    assert driver.redis.get(driver._realm_redis_key("TEST234")) is None
    assert not driver.redis.sismember("%s:REALMS" % driver.redis_prefix, "TEST234")
    assert not len(driver.redis.keys("%s:REQUESTS:%s:*" % (driver.redis_prefix, "TEST234")))

    assert driver.redis.get(driver._realm_redis_key("TEST345")) is None
    assert not driver.redis.sismember("%s:REALMS" % driver.redis_prefix, "TEST345")
    assert not len(driver.redis.keys("%s:REQUESTS:%s:*" % (driver.redis_prefix, "TEST345")))


def test_the_instance_should_ignore_invalid_realms_when_attempting_to_unregister():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.unregister_realm("TEST123")
    driver.unregister_realm("TEST")
    driver.unregister_realm("TEST12345")


def test_the_instance_should_be_able_to_fetch_the_information_of_a_registered_realm():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.register_realm("TEST123", max_requests=100, timespan=300)

    assert b"max_requests" in driver._fetch_realm_info("TEST123")
    assert driver._fetch_realm_info("TEST123")[b"max_requests"] == b"100"

    assert b"timespan" in driver._fetch_realm_info("TEST123")
    assert driver._fetch_realm_info("TEST123")[b"timespan"] == b"300"

    driver.unregister_realm("TEST123")


def test_the_instance_should_be_able_to_return_the_max_requests_value_of_a_registered_realm():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.register_realm("TEST123", max_requests=100, timespan=300)
    assert driver.realm_max_requests("TEST123") == 100

    driver.unregister_realm("TEST123")


def test_the_instance_should_be_able_to_return_the_timespan_value_of_a_registered_realm():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.register_realm("TEST123", max_requests=100, timespan=300)
    assert driver.realm_timespan("TEST123") == 300

    driver.unregister_realm("TEST123")


def test_the_instance_should_validate_that_the_get_lambda_is_actually_a_call_to_self_webdriver():
    driver = RespectfulWebdriver(webdriver=webdriver)

    with pytest.raises(SeleniumRespectfulError):
        driver._validate_get_func("Totally a lambda!")
        
    with pytest.raises(SeleniumRespectfulError):
        driver._validate_get_func(lambda: 1 + 1)

    self = driver
    driver._validate_get_func(lambda: self.webdriver.get("http://google.com"))


def test_the_instance_should_be_able_to_determine_the_amount_of_requests_performed_in_a_timespan_for_a_registered_realm():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.register_realm("TEST123", max_requests=1000, timespan=5)

    assert driver._requests_in_timespan("TEST123") == 0
    
    self = driver
    get_func = lambda: self.webdriver.get("http://google.com")

    driver._perform_webdriver_get(get_func, realms=["TEST123"])
    driver._perform_webdriver_get(get_func, realms=["TEST123"])
    driver._perform_webdriver_get(get_func, realms=["TEST123"])

    assert driver._requests_in_timespan("TEST123") == 3

    driver.unregister_realm("TEST123")


def test_the_instance_should_be_able_to_determine_if_it_can_perform_a_request_for_a_registered_realm():
    driver = RespectfulWebdriver(webdriver=webdriver)
    
    driver.register_realm("TEST123", max_requests=1000, timespan=5)

    assert driver._can_perform_get("TEST123")

    driver.update_realm("TEST123", max_requests=0)

    assert not driver._can_perform_get("TEST123")

    driver.unregister_realm("TEST123")


def test_the_instance_should_not_allow_a_request_to_be_made_on_an_unregistered_realm():
    driver = RespectfulWebdriver(webdriver=webdriver)

    with pytest.raises(SeleniumRespectfulError):
        driver.get("http://google.com", realms=["TEST123"])


def test_the_instance_should_perform_the_request_if_it_is_allowed_to_on_a_registered_realm():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.register_realm("TEST123", max_requests=1000, timespan=5)

    driver.get("http://google.com", realms=["TEST123"])
    assert driver.find_element_by_tag_name("body") is not None

    driver.unregister_realm("TEST123")


def test_the_instance_should_perform_the_request_if_it_is_allowed_to_on_multiple_registered_realms():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.register_realm("TEST123", max_requests=1000, timespan=5)
    driver.register_realm("TEST234", max_requests=1000, timespan=5)

    driver.get("http://google.com", realms=["TEST123", "TEST234"])
    assert driver.find_element_by_tag_name("body") is not None

    driver.unregister_realm("TEST123")
    driver.unregister_realm("TEST234")


def test_the_instance_should_return_a_rate_limit_exception_if_the_request_is_not_allowed_on_a_registered_realm():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.register_realm("TEST123", max_requests=0, timespan=5)

    with pytest.raises(SeleniumRespectfulRateLimitedError):
        driver.get("http://google.com", realms=["TEST123"])

    driver.unregister_realm("TEST123")


def test_the_instance_should_return_a_rate_limit_exception_if_the_request_is_not_allowed_on_one_or_multiple_registered_realms():
    driver = RespectfulWebdriver(webdriver=webdriver)

    driver.register_realm("TEST123", max_requests=0, timespan=5)
    driver.register_realm("TEST234", max_requests=0, timespan=5)

    with pytest.raises(SeleniumRespectfulRateLimitedError):
        driver.get("http://google.com", realms=["TEST123", "TEST234"])

    driver.update_realm("TEST123", max_requests=10)

    with pytest.raises(SeleniumRespectfulRateLimitedError):
        driver.get("http://google.com", realms=["TEST123", "TEST234"])

    driver.update_realm("TEST123", max_requests=0)
    driver.update_realm("TEST234", max_requests=10)

    with pytest.raises(SeleniumRespectfulRateLimitedError):
        driver.get("http://google.com", realms=["TEST123", "TEST234"])

    driver.unregister_realm("TEST123")
    driver.unregister_realm("TEST234")


def test_the_instance_should_be_able_to_wait_for_a_request_to_be_allowed_on_a_registered_realm():
    driver = RespectfulWebdriver(webdriver=webdriver)
    driver.config["safety_threshold"] = 0

    driver.register_realm("TEST123", max_requests=1, timespan=2)

    driver.get("http://google.com", realms=["TEST123"], wait=True)
    driver.get("http://google.com", realms=["TEST123"], wait=True)
    driver.get("http://google.com", realms=["TEST123"], wait=True)

    driver.unregister_realm("TEST123")


def test_the_instance_should_be_able_to_wait_for_a_request_to_be_allowed_on_multiple_registered_realms():
    driver = RespectfulWebdriver(webdriver=webdriver)
    driver.config["safety_threshold"] = 0

    driver.register_realm("TEST123", max_requests=1, timespan=5)
    driver.register_realm("TEST234", max_requests=1, timespan=2)

    driver.get("http://google.com", realms=["TEST123", "TEST234"], wait=True)
    driver.get("http://google.com", realms=["TEST123", "TEST234"], wait=True)
    driver.get("http://google.com", realms=["TEST123", "TEST234"], wait=True)

    driver.unregister_realm("TEST123")
    driver.unregister_realm("TEST234")


def test_the_instance_should_recognize_the_webdriver_proxy_methods():
    driver = RespectfulWebdriver(webdriver=webdriver)

    getattr(driver, "get")

    getattr(driver, "find_element_by_tag_name")
    getattr(driver, "quit")

    with pytest.raises(AttributeError):
        getattr(driver, "i_totally_exist")


def test_the_safety_threshold_configuration_value_should_have_the_expected_effect():
    driver = RespectfulWebdriver(webdriver=webdriver)
    driver.config["safety_threshold"] = 10

    driver.register_realm("TEST123", max_requests=11, timespan=300)

    driver.get("http://google.com", realms=["TEST123"])

    with pytest.raises(SeleniumRespectfulRateLimitedError):
        driver.get("http://google.com", realms=["TEST123"])

    driver.unregister_realm("TEST123")


def test_teardown():
    webdriver.quit()
