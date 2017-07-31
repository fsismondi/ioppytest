from automated_IUTs.automation import UserEmulator
import pika
from coap_testing_tool import AMQP_EXCHANGE,AMQP_URL

if __name__ == '__main__':
    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    UserEmulator(connection,'coap_client').run()