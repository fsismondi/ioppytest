# About Automated IUTs

- You can add either clients and servers in this repository,
the structure name have to be something like:

    ```coap_client_<implementation_name>```

    or

    ```coap_server_<implementation_name>```

- Add supervisor.conf for handling all the
processes regarding the IUT and the integration scripts
(automation stuff, agent etc)


    supervisor will be used as:

    ```supervisord -c automated_IUTs/coap_client_californium/supervisor.conf```

    and

    ```supervisorctl -c automated_IUTs/coap_client_californium/supervisor.conf```


- Add a dockerfile for building & running an IUT in a docker container

    the docker container will be executed more or less like this:

    ```sudo docker run -it --env AMQP_EXCHANGE=$AMQP_EXCHANGE --env AMQP_URL=$AMQP_URL --privileged automated_iut-coap_client-coapthon-v0.1```


- Modify the build_all_docker_images.sh at the root dir of the project


- Add ansible scripts for building the IUT



