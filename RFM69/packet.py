import json
from datetime import datetime

class Packet(object):
    """Object to represent received packet. Created internally and returned by radio when getPackets() is called.

    Args:
        receiver (int): Node ID of receiver
        sender (int): Node ID of sender
        RSSI (int): Received Signal Strength Indicator i.e. the power present in a received radio signal
        data (list): Raw transmitted data

    """
    
    # Declare slots to reduce memory
    __slots__ = 'received', 'receiver', 'sender', 'RSSI', 'data'
    
    def __init__(self, receiver, sender, RSSI, data):
        self.received = datetime.utcnow()
        self.receiver = receiver
        self.sender = sender
        self.RSSI = RSSI
        self.data = data
    
    def to_dict(self, dateFormat=None):
        """Returns a dictionary representation of the class data"""
        if dateFormat is None:
            return_date = self.received
        else:
            return_date = datetime.strftime(self.received, dateFormat)
        return dict(received=return_date, receiver=self.receiver, sender=self.sender, rssi=self.RSSI, data=self.data)

    @property
    def data_string(self):
        return "".join([chr(letter) for letter in self.data])

    def __str__(self):
        return json.dumps(self.to_dict('%c'))

    def __repr__(self):
        return "Radio({}, {}, {}, [data])".format(self.receiver, self.sender, self.RSSI)

