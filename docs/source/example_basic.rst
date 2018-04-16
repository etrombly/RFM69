.. include:: global.rst

Example - The Basics
====================

Initialise
----------
To initialise the radio you create a context:

.. code-block:: Python
    :emphasize-lines: 5
    :linenos:

    from RFM69Radio import Radio, FREQ_433MHZ

    this_node_id = 1
    with Radio(FREQ_433MHZ, this_node_id) as radio:
        ... your code here ...

This ensures that the necessary clean-up code is executed when you exit the context.

.. note:: 
    
    Frequency selection: FREQ_315MHZ, FREQ_433MHZ, FREQ_868MHZ or FREQ_915MHZ. Select the band appropriate to the radio you have.


Simple Receiver
---------------

.. literalinclude:: ../../examples/basic_rx.py
   :language: python
   :linenos:


Simple Transmitter
------------------

.. literalinclude:: ../../examples/basic_tx.py
   :language: python
   :linenos:
