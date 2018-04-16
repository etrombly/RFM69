.. include:: global.rst

Example - Redis (Advanced)
==========================

Overview
--------
In this example we are going to use Redis as a task queue. Messages we want to send will be added to a task queue and a radio management script will remove and send them. In much the same way received messages will be added to the Queue so that we can retrieve them.

Sending
-------

.. literalinclude:: ../../examples/redis_tx.py
   :language: python
   :linenos:

Receiving
---------

.. literalinclude:: ../../examples/redis_rx.py
   :language: python
   :linenos:

Radio Manager
-------------

.. literalinclude:: ../../examples/redis_manager.py
   :language: python
   :linenos:

Installing Redis on a RPI
-------------------------
Coming soon