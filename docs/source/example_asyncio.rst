.. include:: global.rst

Example - Asynio
================
A common requirement is to forward received RFM69 packets onward to a web API. However HTTP requests can be slow and we need to consider how to manage possible delays. If we block the radio receiver loop while making the necessary HTTP request, then time critical messages will be forced to wait!

We could solve this problem in a number of ways. In this example we are going to use Asyncio. It’s worth mentioning here that although Asyncio is often touted as the wonder child of Python 3, asynchronous processing is not new to Python. More importantly, Asyncio is not a silver bullet and depending on your task may not be the best solution. I am not going to go over old ground talking about the pros and cons of async vs sync or concurrency and parallelism, Abu Ashraf Masnun has a nice article called `Async Python: The Different Forms of Concurrency <http://masnun.rocks/2016/10/06/async-python-the-different-forms-of-concurrency/>`_ which I think covers this topic well.

Install the additional dependencies
-----------------------------------

.. code::

    pip install aiohttp cchardet aiodns


Asyncio RESTful API Gateway
---------------------------
The destination url is set to http://httpbin.org/post. This is a free online service which will echo back the post data sent to the service. It has a whole host (pardon the pun) of other tools for testing HTTP clients.

.. literalinclude:: ../../tests/script_async_gateway.py
   :language: python

