import logging
import sys

from ioppytest.utils.event_bus_utils import AmqpListener
from ioppytest.utils.messages import MsgTestingToolTerminate, MsgSessionLog

logger = logging.getLogger(__name__)

MAX_LINE_LENGTH = 120

class MessageLogger(AmqpListener):
    def __init__(self, amqp_url, amqp_exchange):
        AmqpListener.__init__(self, amqp_url, amqp_exchange,
                              callback=self.process_message,
                              topics=['#'],
                              use_message_typing=True)

        self.messages_list = []
        self.messages_by_type_dict = {}

    def process_message(self, message):
   #     logger.debug('[%s]: %s' % (sys._getframe().f_code.co_name, repr(message)[:MAX_LINE_LENGTH]))
        self.messages_list.append(message)
        self.messages_by_type_dict[type(message)] = message

        if isinstance(message, MsgTestingToolTerminate):
            logger.info("Received termination message. Stopping logging")
            self.stop()




def log_all_received_messages(event_list: list):
    logger.info("Events sniffed in bus: %s" % len(event_list))
    traces_of_all_messages_in_event_bus = ""
    logs_traces_of_all_log_messages_in_event_bus = """ 

*****************************************************************
COMPLETE LOG TRACE from log messages in event bus (MsgSessionLog)
*****************************************************************
    """
    i = 0
    for ev in event_list:
        i += 1
        try:
            traces_of_all_messages_in_event_bus += "\n\tevent count: %s" % i
            traces_of_all_messages_in_event_bus += "\n\tmsg_id: %s" % ev.message_id
            traces_of_all_messages_in_event_bus += "\n\tmsg repr: %s" % repr(ev)[:MAX_LINE_LENGTH]

        except AttributeError as e:
            logger.warning("No message id in message: %s" % repr(ev))

        try:
            if isinstance(ev, MsgSessionLog):
                logs_traces_of_all_log_messages_in_event_bus += "\n[%s] %s" % (ev.component, ev.message)
        except AttributeError as e:
            logger.warning(e)

    logs_traces_of_all_log_messages_in_event_bus += """ 
*****************************************************************
                    END OF LOG TRACE  
*****************************************************************
    """
    logger.info(logs_traces_of_all_log_messages_in_event_bus)
    logger.debug(traces_of_all_messages_in_event_bus)